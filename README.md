# 🇰🇷 Korean Official Document Analyzer

대한민국 공문서·계획서 점검용 AI 스킬입니다.  
**Claude에서는 스킬로 등록해 쓰고, GPT·Gemini 등에서는 지침으로 붙여 넣어 쓸 수 있습니다.**

---

## 📌 개요

교육청·학교 같은 행정기관에서 작성하는 공문서를 AI가 점검합니다.  
날짜·요일·연도 오류, 맞춤법, 명칭 불일치, 연도 변경 누락, 담당자 정보를 한 번에 확인합니다.

> 이 스킬은 **자동으로 실행되지 않습니다.**  
> "공문 검토해줘", "이 스킬로 점검해줘", "작년 계획서 연도 바꿔야 할 곳 찾아줘"처럼 명시적으로 요청할 때만 적용됩니다.

### 두 가지 분석 모드

| 모드 | 사용 상황 |
|---|---|
| 🔵 **공문서 교정 모드** | 지금 작성 중인 공문의 오류 점검 |
| 🟠 **연도변경 분석 모드** | 작년 계획서를 올해 버전으로 전환 (A: 파일 1개 / B: 두 문서 비교) |

### 모드 공통 기능

- 🔗 **선행·후속 문서 교차 검증**: 같은 사안을 다루는 문서([계획] 기안문 → [신청·안내] 기안문 등)가 대화에 함께 등장하면, 신청 기간·시각·장소·담당자·연락처 같은 세부조건이 서로 맞는지 자동으로 대조합니다.
- 🏫 **기관 정식명칭 규칙**: "전남광주통합특별시교육청"은 정식 명칭으로 인정하고, 어순·글자가 달라진 변형 표기만 오류로 지적합니다.
- 👤 **인물명 확인 요청**: 문서 속 담당자·책임자 이름을 뽑아 실제 해당자가 맞는지 사용자에게 확인을 요청합니다. 전화번호는 기본으로 일부를 가려서 보여 줍니다.

---

## 📁 파일 구성

```
korean-official-doc-analyzer/
├── SKILL.md               ← AI에게 전달하는 스킬 정의 (핵심)
├── README.md              ← 이 파일
├── LICENSE                ← MIT License
├── index.html             ← 스킬 소개 페이지
├── agents/
│   └── openai.yaml        ← Codex(OpenAI) 에이전트용 스킬 메타데이터
└── scripts/
    ├── section_parser.py  ← 문서 섹션 분류 (CURRENT / PAST / ATTACH / REF_NUM)
    ├── verify_dates.py    ← 날짜 존재·요일·연도 정확성 검증
    ├── check_naming.py    ← 명칭 일관성 검증
    ├── extract_persons.py ← 인물명(책임자·담당자·연락처) 추출
    └── compare_docs.py    ← 두 문서 비교 (연도변경 모드 B)
```

---

## 🚀 사용 방법

### Claude (Claude Desktop / Claude Code)

1. 저장소를 내려받습니다.
2. 폴더를 스킬 경로에 복사합니다.

```bash
git clone https://github.com/yundaldal/korean-official-doc-analyzer.git
cp -r korean-official-doc-analyzer ~/.claude/skills/
```

3. 문서를 올리고 "공문 검토해줘"처럼 요청합니다.

claude.ai에서는 폴더를 zip으로 묶어 스킬 설정 화면에서 업로드할 수 있습니다.

### Codex (OpenAI)

`agents/openai.yaml`이 들어 있으므로 폴더를 Codex 스킬 경로(예: `~/.agents/skills/`)에 복사하면 됩니다.

### ChatGPT / Gemini (지침 붙여넣기)

1. `SKILL.md` 내용을 모두 복사합니다.
2. 대화 첫 메시지(또는 Gemini의 System Instruction)에 붙여 넣습니다.
3. 점검할 문서를 올리고 요청합니다.

```
다음 지침을 따라 공문서를 점검해줘:

[SKILL.md 내용 전체]

---
점검할 문서: [파일 업로드 또는 텍스트 입력]
```

> 스크립트 실행 환경이 없는 서비스에서는 날짜·요일 계산을 AI가 직접 해야 하므로 정확도가 떨어질 수 있습니다.

---

## ✅ 지원 입력 형식

| 형식 | 교정 모드 | 연도변경 모드 |
|---|---|---|
| `.hwpx` (한글) | ✅ | ✅ |
| `.docx` (Word) | ✅ | ✅ |
| `.pdf` | ✅ | ✅ |
| `.txt` / `.md` | ✅ | ✅ |
| 이미지 (캡처본) | ✅ (OCR) | ❌ |
| 텍스트 직접 입력 | ✅ | ❌ |

파일에서 텍스트를 뽑는 일은 사용하는 AI 환경의 문서 추출 도구가 맡습니다.

---

## 🔍 점검 항목

### 🔵 공문서 교정 모드
- 한국어 맞춤법·어법 (위치 → 현재 표기 → 올바른 표기 → 근거 순서로 제시)
- 날짜 존재·요일·연도 정확성 (Python으로 계산)
- 단어 누락·반복·비정상 표현
- 인물명 확인 요청
- 선행·후속 문서 교차 검증 (해당 시)

### 🟠 연도변경 분석 모드
- 🔴 기존 문서 자체 오류
- 🟠 연도 필수 변경 항목
- 🟡 날짜 전면 재설정 필요 항목
- 🟢 내용 갱신 필요 항목 (인사·예산·실적)
- 🟣 명칭 불일치
- 👤 인물명 확인
- 🔵 사용자 직접 확인 필요 항목
- 🔗 문서 간 세부조건 불일치

---

## 💡 요청 예시

```
공문 검토해줘
이 공문 날짜·요일 맞는지 확인해줘
작년 계획서 분석해줘
2025 문서를 2026으로 바꿔야 할 곳 찾아줘
두 문서 비교해서 바뀌지 않은 곳 찾아줘
```

---

## ⚙️ 스크립트 직접 실행

- **Python 3.8 이상**이 필요합니다.
- 외부 패키지 없이 표준 라이브러리만 씁니다.
- 긴 문서는 셸 인자 길이 제한 때문에 실패할 수 있으니 **텍스트 파일 경로(`--input-file`)로 넘기는 방식**을 권장합니다. `--text`는 짧은 텍스트에만 씁니다.

```bash
# 섹션 분류
python3 scripts/section_parser.py --input-file doc.txt --current-year 2026

# 날짜·요일·연도 검증
python3 scripts/verify_dates.py --input-file doc.txt --current-year 2026

# 명칭 일관성 검증
python3 scripts/check_naming.py --input-file doc.txt --current-year 2026

# 인물명 추출
python3 scripts/extract_persons.py --input-file doc.txt

# 두 문서 비교 (연도변경 모드 B)
python3 scripts/compare_docs.py --old-file old.txt --new-file new.txt --source-year 2025 --target-year 2026
```

---

## ⚠️ 한계

- AI가 판단할 수 없는 정보(담당자 실명, 예산, 프로그램 내용 등)는 "확인 필요"로 표시하고 사용자에게 확인을 요청합니다.
- 이미지 입력은 OCR 오류가 생길 수 있습니다.
- 맞춤법 점검은 AI의 한국어 능력에 기대므로, 최종 판단은 작성자가 해야 합니다.

---

## 📝 라이선스

[MIT License](./LICENSE) — 자유롭게 사용·수정·배포할 수 있습니다.  
교육 현장의 선생님들이 편하게 쓸 수 있도록 만들었습니다.

---

## 🙋 만든 이

특수교육 현장에서 공문서 작성 부담을 줄이려고 개발했습니다.  
개선 아이디어나 버그 제보는 [Issues](https://github.com/yundaldal/korean-official-doc-analyzer/issues)에 남겨 주세요.
