"""
시스템_추론 컬럼 채우기 - Anthropic Claude API 기반

각 세부사업의 사업목적, 수혜자, 지원형태 등을 Claude에게 보내
필요한 정보시스템 유형과 검색 가능한 근거 텍스트를 생성한다.

사용법:
  set ANTHROPIC_API_KEY=sk-ant-...
  py -X utf8 infer_systems.py

시스템유형 카테고리 (8개):
  홈페이지/포털, 업무처리시스템, 데이터/분석,
  교육/학습(LMS), 내부인프라, 상담/콜센터, 금융/기금, 의료정보
"""
import sqlite3
import csv
import json
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.sqlite')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), '세부사업_DB.csv')

# 한 번의 API 호출에 몇 건을 묶을지 (비용/속도 트레이드오프)
BATCH_SIZE = 10

SYSTEM_PROMPT = """당신은 고용노동부 정보시스템 전문가입니다.
세부사업 정보를 보고, 해당 사업을 운영하기 위해 필요한 정보시스템 유형을 추론합니다.

시스템유형 카테고리 (8개 중 1~3개 선택):
1. 홈페이지/포털 - 대국민 웹사이트, 포털, 정보공개
2. 업무처리시스템 - 신청접수, 심사, 급여지급, 행정처리
3. 데이터/분석 - 통계, 모니터링, 성과관리, 분석 대시보드
4. 교육/학습(LMS) - 교육훈련, e러닝, 연수
5. 내부인프라 - IT 인프라, 그룹웨어, 보안, 전산장비
6. 상담/콜센터 - 상담서비스, 콜센터, 챗봇
7. 금융/기금 - 기금운용, 융자, 보험료, 연금, 금융거래
8. 의료정보 - 의료기록, 건강정보, 재활, 진료시스템

규칙:
- 핵심 유형 1~3개만 선택 (모두 선택하지 말 것)
- 인건비/경비 사업은 보통 업무처리시스템만 필요
- 예치/전출 사업은 금융/기금
- 의료정보는 실제 의료서비스를 다루는 사업만
- 근거는 검색 키워드로 활용되므로, 사업의 핵심 내용을 요약하여 작성

응답은 반드시 JSON 배열로만 출력하세요. 다른 텍스트 없이 JSON만 출력합니다."""


def build_user_prompt(batch: list[dict]) -> str:
    """배치 데이터를 사용자 프롬프트로 변환."""
    entries = []
    for item in batch:
        entry = f"""[{item['파일번호']}] {item['세부사업명']}
  사업목적: {(item.get('사업목적') or '-')[:200]}
  수혜자: {item.get('수혜자') or '-'}
  지원형태: {item.get('지원형태') or '-'}
  시스템직접언급: {item.get('시스템_직접언급') or '없음'}"""
        entries.append(entry)

    return f"""다음 {len(batch)}개 세부사업에 대해 필요한 시스템 유형을 추론하세요.

{chr(10).join(entries)}

JSON 형식으로 응답:
[
  {{"파일번호": 번호, "시스템유형": ["유형1", "유형2"], "근거": "15자 이내 한국어 설명"}},
  ...
]"""


def call_claude_api(system_prompt: str, user_prompt: str) -> str:
    """Anthropic Claude API 호출."""
    import anthropic

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def parse_response(text: str) -> list[dict]:
    """API 응답에서 JSON 배열 추출."""
    # JSON 블록 추출 (```json ... ``` 또는 순수 JSON)
    text = text.strip()
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
    return json.loads(text)


def load_db_rows() -> list[dict]:
    """DB에서 추론 입력 데이터 로드."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT 파일번호, 세부사업명, 사업목적, 사업개요_주요내용, 수혜자,
               지원형태, 사업시행주체, 시스템_직접언급
        FROM 세부사업 ORDER BY 파일번호
    ''').fetchall()
    conn.close()
    result = []
    for r in rows:
        item = {k: r[k] for k in r.keys()}
        # 텍스트 길이 제한
        for k in ['사업목적', '사업개요_주요내용']:
            if item[k] and len(item[k]) > 300:
                item[k] = item[k][:300]
        result.append(item)
    return result


def update_db(all_inferred: list[dict]):
    """추론 결과를 DB에 반영하고 CSV 재내보내기."""
    conn = sqlite3.connect(DB_PATH)
    updated = 0
    for item in all_inferred:
        fno = item['파일번호']
        types = '; '.join(item['시스템유형'])
        reason = item.get('근거', '')
        inference = f'[유형] {types} [근거] {reason}'
        conn.execute('UPDATE 세부사업 SET 시스템_추론 = ? WHERE 파일번호 = ?',
                     (inference, fno))
        updated += 1
    conn.commit()

    # CSV 재내보내기
    cursor = conn.execute('SELECT * FROM 세부사업 ORDER BY 파일번호')
    col_names = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        for row in rows:
            writer.writerow(row)

    conn.close()
    return updated


def main():
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('오류: ANTHROPIC_API_KEY 환경변수를 설정하세요.')
        print('  set ANTHROPIC_API_KEY=sk-ant-...')
        return

    # DB에서 데이터 로드
    all_rows = load_db_rows()
    print(f'{len(all_rows)}개 세부사업 로드')

    # 배치 분할
    batches = []
    for i in range(0, len(all_rows), BATCH_SIZE):
        batches.append(all_rows[i:i + BATCH_SIZE])
    print(f'{len(batches)}개 배치로 분할 (배치당 {BATCH_SIZE}건)')

    # API 호출
    all_inferred = []
    for i, batch in enumerate(batches):
        print(f'  배치 {i + 1}/{len(batches)} 처리 중... ({len(batch)}건)')
        user_prompt = build_user_prompt(batch)

        try:
            response_text = call_claude_api(SYSTEM_PROMPT, user_prompt)
            inferred = parse_response(response_text)
            all_inferred.extend(inferred)
            print(f'    → {len(inferred)}건 추론 완료')
        except Exception as e:
            print(f'    → 오류: {e}')
            # 오류 시 기본값 채우기
            for item in batch:
                all_inferred.append({
                    '파일번호': item['파일번호'],
                    '시스템유형': ['업무처리시스템'],
                    '근거': '추론 실패 - 기본값',
                })

        # Rate limit 방지
        if i < len(batches) - 1:
            time.sleep(1)

    print(f'\n총 {len(all_inferred)}건 추론 완료')

    # DB 업데이트
    updated = update_db(all_inferred)
    print(f'{updated}건 DB 업데이트 완료')

    # 시스템유형 분포 출력
    type_counts = {}
    for item in all_inferred:
        for t in item['시스템유형']:
            type_counts[t] = type_counts.get(t, 0) + 1

    print(f'\n=== 시스템유형 추론 분포 ===')
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f'  {t}: {c}건')

    print(f'\nDB: {DB_PATH}')
    print(f'CSV: {OUTPUT_CSV}')


if __name__ == '__main__':
    main()
