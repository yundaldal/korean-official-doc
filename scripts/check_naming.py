#!/usr/bin/env python3
"""
문서 내 명칭 일관성 검증 스크립트

같은 행사·프로그램·기관을 지칭하는 명칭이 문서 안에서 혼용되고 있는지 탐지한다.

사용법 (v2 — --input-file 우선 사용, 구버전 위치인자도 하위 호환):
    python3 check_naming.py --input-file "<텍스트_파일_경로>" --current-year <target_year>
    python3 check_naming.py "<텍스트>" <target_year>            # 구버전 방식(짧은 텍스트만)

주의: v1은 파일 경로를 넘겨도 "경로 문자열 자체"를 텍스트로 분석해버리는 조용한 실패가
있었다(P0-5). --input-file을 쓰면 반드시 해당 경로의 파일 내용을 읽어 분석한다.

출력(JSON):
    {
        "groups": [
            {
                "canonical": "가장 많이 등장한 명칭 (주의: 확정된 공식명이 아니라 최빈값 추정치일 뿐이다.
                              오타가 여러 번 반복된 문서에서는 오타가 canonical로 잡힐 수 있으므로,
                              문서 제목·최초 정의·공식 출처로 확정되지 않았다면 사용자에게
                              '어느 쪽이 공식명인지' 반드시 확인받을 것 — 이 스크립트 자체가
                              확정해주지는 않는다)",
                "variants": ["다른 표기 A", "다른 표기 B"],
                "issue_type": "연도혼용|축약혼용|유사명혼용|띄어쓰기",
                "occurrences": {"명칭A": 5, "명칭B": 2},
                "recommendation": "통일 권장 명칭 및 이유"
            }
        ],
        "total_issues": N
    }

알려진 한계(다음 단계 개선 예정, 이번 업데이트에는 미포함):
    - issue_type에 기관명 전용 태그가 아직 없어 기관명 혼용도 다른 유형과 섞여 분류될 수 있음
    - 띄어쓰기 변형 탐지가 약해 일부 띄어쓰기 오류를 놓칠 수 있음
    - 섹션(CURRENT/PAST) 맥락을 모르므로 과거/현재 행사명이 각각 정상 존재해도 '연도 혼용'으로
      오탐할 수 있음 — 결과를 그대로 확정 짓지 말고 반드시 사람이 한 번 더 확인할 것
"""

from __future__ import annotations

import argparse
import os
import sys
import re
import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher


# ==============================
# 명칭 후보 추출 패턴
# ==============================

# 한글 공문서에서 고유명사처럼 보이는 패턴들
EVENT_NAME_PATTERNS = [
    # "2026 ○○○한마당" 형태 — 연도 포함 행사명
    r'(?:20\d{2}\s+)?[가-힣]{2,15}(?:한마당|행사|대회|연수|워크숍|포럼|캠프|축제|발표회|공모전|교육|연구회)',
    # "제N회 ○○○" 형태
    r'제\s*\d+\s*회\s*[가-힣\s]{2,20}',
    # 연도 포함 사업·프로그램명
    r'(?:20\d{2}년?\s+)?[가-힣]{2,20}(?:사업|프로그램|운영|계획|지원)',
]

ORG_NAME_PATTERNS = [
    # 부서명: ○○교육청, ○○과, ○○팀
    r'[가-힣]{2,10}(?:교육청|교육지원청|교육원|학교|연구원)',
    r'[가-힣]{2,8}(?:특수교육과|특수교육지원과|교육과|지원과|기획과)',
    # "○○부" "○○처" 형태는 제외 (너무 일반적)
]


# 확정된 공식 명칭 — 문서에 정확히 이 표기로 등장하면 정답으로 보고 canonical로 고정한다.
# 특정 기관명을 코드에 넣지 않는다. 값은 실행 시 아래 두 경로로 채워진다.
#   1) --official-name 인자 (여러 번 지정 가능)
#   2) 스킬 폴더의 user_config.json → "official_org_names" 목록
OFFICIAL_NAMES: list[str] = []

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'user_config.json')


def load_official_names(cli_names: list[str] | None) -> list[str]:
    """CLI 인자와 user_config.json에서 정식 기관명 목록을 모은다 (없으면 빈 목록)."""
    names = [n.strip() for n in (cli_names or []) if n and n.strip()]
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            cfg = json.load(f)
        for n in cfg.get('official_org_names', []) or []:
            if isinstance(n, str) and n.strip() and n.strip() not in names:
                names.append(n.strip())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return names


def extract_candidates(text: str) -> list[str]:
    """명칭 후보를 텍스트에서 추출

    서로 다른 패턴이 같은 위치의 문자열을 겹쳐서 잡으면(예: '…교육청'을 ORG 패턴이,
    그 앞부분 '…교육'을 EVENT 패턴이 동시에 추출) 실제로는 한 번 등장한 명칭이
    '축약 혼용'으로 오탐된다. 그래서 다른 후보의 위치 범위에 완전히 포함되는
    짧은 후보는 버리고, 가장 긴 후보만 남긴다.
    """
    spans = []
    for pattern in EVENT_NAME_PATTERNS + ORG_NAME_PATTERNS:
        for m in re.finditer(pattern, text):
            raw = m.group(0)
            stripped = raw.strip()
            if len(stripped) < 4:
                continue
            start = m.start() + (len(raw) - len(raw.lstrip()))
            end = start + len(stripped)
            spans.append((start, end, stripped))

    # 긴 것부터 확정하고, 이미 확정된 범위 안에 완전히 들어가는 후보는 제외
    spans.sort(key=lambda s: (-(s[1] - s[0]), s[0]))
    kept = []
    for start, end, name in spans:
        if any(ks <= start and end <= ke for ks, ke, _ in kept):
            continue
        kept.append((start, end, name))

    kept.sort(key=lambda s: s[0])
    return [name for _, _, name in kept]


# ==============================
# 유사도 판단
# ==============================

def similarity(a: str, b: str) -> float:
    """두 문자열의 유사도 (0~1)"""
    return SequenceMatcher(None, a, b).ratio()


def normalize(name: str) -> str:
    """비교를 위한 정규화: 연도·공백·특수문자 제거"""
    n = re.sub(r'20\d{2}', '', name)   # 연도 제거
    n = re.sub(r'\s+', '', n)           # 공백 제거
    n = re.sub(r'[^\w가-힣]', '', n)    # 특수문자 제거
    return n.strip()


def group_similar(names: list[str], threshold: float = 0.72) -> list[list[str]]:
    """유사한 명칭끼리 묶기 (Union-Find 방식)"""
    parent = list(range(len(names)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ni, nj = normalize(names[i]), normalize(names[j])
            if not ni or not nj:
                continue
            # 완전 포함 관계 또는 높은 유사도
            if ni in nj or nj in ni or similarity(ni, nj) >= threshold:
                union(i, j)

    groups = defaultdict(list)
    for i, name in enumerate(names):
        groups[find(i)].append(name)

    return [sorted(set(g), key=len, reverse=True) for g in groups.values() if len(set(g)) > 1]


# ==============================
# 연도 혼용 전용 탐지
# ==============================

def detect_year_mixing(text: str, target_year: str) -> list[dict]:
    """같은 행사명인데 연도 표기가 다른 경우 탐지"""
    issues = []

    # 연도 포함 명칭 추출: "20XX ○○○" 패턴
    year_name_pattern = r'(20\d{2})\s+([가-힣]{3,20}(?:한마당|행사|대회|연수|워크숍|포럼|캠프|축제|발표회|교육|사업|프로그램))'
    matches = re.findall(year_name_pattern, text)

    # 행사 기반명(연도 제거) 별로 연도들 수집
    base_years = defaultdict(set)
    for year, base_name in matches:
        key = normalize(base_name)
        if key:
            base_years[key].add(year)

    for base_key, years in base_years.items():
        if len(years) > 1:
            # 여러 연도가 같은 행사명에 등장
            year_list = sorted(years)
            # 실제 표기 원본 복원
            original_forms = []
            for yr in year_list:
                pattern = rf'{yr}\s+[가-힣]*{re.escape(base_key[:4])}[가-힣]*'
                found = re.findall(pattern, text)
                original_forms.extend(found[:2])

            issues.append({
                "canonical": f"{target_year} {base_key}",
                "variants": list(set(original_forms)) if original_forms else [f"{y} {base_key}" for y in year_list],
                "issue_type": "연도혼용",
                "occurrences": {yr: text.count(yr + ' ') for yr in year_list},
                "recommendation": f"'{target_year} {base_key}'로 통일. 다른 연도 표기 ({', '.join(y for y in year_list if y != target_year)}) 잔존 여부 확인"
            })

    return issues


# ==============================
# 띄어쓰기 불일치 탐지
# ==============================

def detect_spacing_variants(text: str, candidates: list[str], counts: Counter) -> list[dict]:
    """같은 명칭인데 띄어쓰기만 다른 경우"""
    issues = []
    processed = set()

    for name in candidates:
        if name in processed:
            continue
        # 공백 유무 두 가지 형태 모두 검색
        no_space = name.replace(' ', '')
        with_space_variants = []

        # 2~3글자 단위로 공백 삽입 시도
        if ' ' not in name and len(name) >= 4:
            # 흔한 한국어 띄어쓰기 경계 (2·2, 2·3, 3·2, 3·3)
            for split in [2, 3]:
                variant = name[:split] + ' ' + name[split:]
                if variant in text and variant != name:
                    with_space_variants.append(variant)

        for variant in with_space_variants:
            if counts.get(name, 0) > 0 and counts.get(variant, 0) > 0:
                canonical = name if counts[name] >= counts[variant] else variant
                other = variant if canonical == name else name
                issues.append({
                    "canonical": canonical,
                    "variants": [other],
                    "issue_type": "띄어쓰기",
                    "occurrences": {name: counts[name], variant: counts[variant]},
                    "recommendation": f"띄어쓰기 통일 필요: '{canonical}' 또는 '{other}' 중 공식 표기로 통일"
                })
                processed.add(name)
                processed.add(variant)

    return issues


# ==============================
# 메인 분석
# ==============================

def analyze_naming(text: str, target_year: str) -> dict:
    all_issues = []

    # ① 연도 혼용 탐지 (가장 중요)
    year_issues = detect_year_mixing(text, target_year)
    all_issues.extend(year_issues)

    # ② 유사 명칭 군집 탐지
    candidates_raw = extract_candidates(text)
    counts = Counter(candidates_raw)
    unique_candidates = list(counts.keys())

    similar_groups = group_similar(unique_candidates)
    for group in similar_groups:
        if len(group) < 2:
            continue

        # 확정된 공식 명칭이 그룹에 있으면 그것을 canonical로 고정, 없으면 최빈값으로 추정
        official = [g for g in group if g in OFFICIAL_NAMES]
        canonical = official[0] if official else max(group, key=lambda x: counts.get(x, 0))
        variants = [v for v in group if v != canonical]

        # 이슈 타입 판단
        norms = [normalize(v) for v in group]
        if all(n in normalize(canonical) or normalize(canonical) in n for n in norms):
            issue_type = "축약혼용"
            recommendation = f"'{canonical}'이 가장 많이 등장하는 공식명으로 추정됩니다. 축약 표기({', '.join(variants)})를 공식명으로 통일하세요."
        else:
            issue_type = "유사명혼용"
            recommendation = f"'{canonical}'과 유사한 명칭이 혼용됩니다. 공식 명칭을 확인하고 통일하세요."

        if official:
            recommendation = (f"'{canonical}'은 확정된 정식 명칭입니다. "
                              f"변형 표기({', '.join(variants)})를 '{canonical}'으로 통일하세요.")

        # 이미 연도혼용으로 처리된 그룹과 중복 방지
        if not any(canonical in str(yi.get('variants', '')) or canonical == yi.get('canonical', '') for yi in year_issues):
            all_issues.append({
                "canonical": canonical,
                "variants": variants,
                "issue_type": issue_type,
                "occurrences": {v: counts.get(v, 0) for v in group},
                "recommendation": recommendation
            })

    # ③ 띄어쓰기 불일치
    spacing_issues = detect_spacing_variants(text, unique_candidates, counts)
    all_issues.extend(spacing_issues)

    return {
        "groups": all_issues,
        "total_issues": len(all_issues)
    }


# ==============================
# 메인
# ==============================

def main():
    cli_official = []
    # 구버전 하위 호환: check_naming.py <텍스트> <target_year>
    if len(sys.argv) >= 3 and not sys.argv[1].startswith('--'):
        text = sys.argv[1]
        target_year = sys.argv[2]
    else:
        parser = argparse.ArgumentParser(description='문서 내 명칭 일관성 검증')
        parser.add_argument('--input-file', help='텍스트 파일 경로 (긴 문서는 반드시 이 옵션을 사용)')
        parser.add_argument('--text', help='텍스트 직접 입력 (짧은 경우에만 사용)')
        parser.add_argument('--current-year', dest='target_year', required=True, help='기준연도')
        parser.add_argument('--official-name', action='append', default=[],
                            help='확정된 정식 기관명 (여러 번 지정 가능). user_config.json 값과 합쳐진다.')
        args = parser.parse_args()
        cli_official = args.official_name

        if args.input_file:
            with open(args.input_file, encoding='utf-8') as f:
                text = f.read()
        elif args.text is not None:
            text = args.text
        else:
            print('입력이 없습니다: --input-file 또는 --text 중 하나를 지정하세요.', file=sys.stderr)
            sys.exit(1)
        target_year = args.target_year

    OFFICIAL_NAMES[:] = load_official_names(cli_official)
    result = analyze_naming(text, target_year)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
