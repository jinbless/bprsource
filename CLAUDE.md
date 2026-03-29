# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
고용노동부 273건 세부사업의 예산 데이터를 PDF→MD→SQLite로 구조화하고, 197건 정보시스템과의 매핑 현황을 분석하는 프로젝트. Streamlit 대시보드로 검색·시각화 제공.

## 명령어

```bash
# Streamlit 대시보드 실행
py -X utf8 -m streamlit run app.py

# PDF→MD 파싱 후 DB 재생성 (273건 세부사업)
py -X utf8 extract_db.py

# 시스템 카테고리 분류 (197건 시스템에 7개 컬럼 추가)
py -X utf8 categorize.py

# 카테고리 수정 반영 (29건 수동 보정)
py -X utf8 apply_corrections.py

# CSV↔DB 교차 검증
py -X utf8 validate_mapping.py

# Claude API로 시스템유형 추론 (ANTHROPIC_API_KEY 필요)
set ANTHROPIC_API_KEY=sk-ant-...
py -X utf8 infer_systems.py

# 엑셀→SQLite/CSV 임포트
py -X utf8 import_xlsx.py

# 의존성 설치
pip install -r requirements.txt
```

## 아키텍처

### 데이터 파이프라인
```
pdf/*.md (273개) → parser_md.py → extract_db.py → 세부사업_DB.sqlite + .csv
                                                        ↓
                                              infer_systems.py (Claude API)
                                                        ↓
                                              시스템_추론 컬럼 채움
```

### 시스템 분류 파이프라인
```
예산사업_시스템_매핑.csv (197건) → categorize.py → 7개 카테고리 컬럼 추가
                                                        ↓
                                              apply_corrections.py (29건 수동 보정)
                                                        ↓
                                              예산사업_시스템_매핑_사람기준.csv (최종)
```

### 대시보드 (app.py)
- **search.py**: 키워드 검색(Python 스코어링) + LLM 검색(OpenAI gpt-4.1-nano로 질문 분석 후 검색)
- 3개 페이지: 시스템 매칭 검색, 현황 대시보드, 세부사업 목록
- 데이터 소스: `세부사업_DB.sqlite` (273건) + `예산사업_시스템_매핑_사람기준.csv` (197건)

### 핵심 모듈
- **parser_md.py**: MD 파일 섹션 분리(헤딩 기반) → 테이블/서술형 데이터 파싱. `parse_md_file()`이 진입점
- **categorize.py**: 시스템명/기관명 키워드 매칭으로 7개 카테고리 자동 분류
- **infer_systems.py**: Claude API 배치 호출(10건/배치)로 시스템유형 추론, 결과를 `[유형] ...; ... [근거] ...` 형식으로 저장

## 데이터 구조

### 세부사업_DB.sqlite — `세부사업` 테이블
273건 세부사업. 주요 컬럼: 파일번호(PK), 세부사업명, 회계구분(회계/기금), 확정_2026, 사업목적, 시스템_직접언급, 시스템_추론

### 예산사업_시스템_매핑_사람기준.csv
197건 시스템. 원본 10개 컬럼(기관명, 시스템명, 등급 등) + 카테고리 7개 컬럼(서비스대상, 업무도메인, 시스템유형, 기관유형, 금융관련, 개인정보수준, 서비스채널)

### 카테고리 값 체계
| 컬럼명 | 값 목록 |
|--------|---------|
| 서비스대상 | 대국민, 내부, 혼합 |
| 업무도메인 | 고용서비스, 사회보험, 산업안전보건, 직업훈련·교육, 자격·평가, 근로복지, 노사관계, 외국인고용, 장애인고용, 행정지원, 정보공개·홍보 |
| 시스템유형 | 홈페이지/포털, 업무처리시스템, 데이터/분석, 교육/학습(LMS), 내부인프라, 상담/콜센터, 금융/기금, 의료정보 |
| 기관유형 | 본부, 위원회, 공단, 정보원, 교육기관, 재단/진흥원, 공제회, 기타공공 |

## 코딩 규칙
- CSV 인코딩: **utf-8-sig** (BOM 포함)
- Python 실행: **`py -X utf8`** (Windows 환경 필수)
- 세부사업 연결 키: CSV `세부사업명` ↔ pdf/ 폴더 MD 파일명 `{번호}_고용노동부_{세부사업명}.md`
