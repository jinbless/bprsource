"""
세부사업-시스템 검색 모듈
- keyword_search: 키워드 기반 검색
- llm_search: OpenAI 기반 검색
- get_systems_for_business: 세부사업에 매핑된 시스템 조회
"""
import sqlite3
import json
import os
import re

DB_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.sqlite')

# 검색 대상 컬럼
SEARCH_COLUMNS = ['세부사업명', '사업목적', '시스템_추론', '시스템_직접언급',
                   '수혜자', '사업개요_주요내용', '단위사업명', '프로그램명']


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def keyword_search(query: str, limit: int = 20) -> list[dict]:
    """키워드 기반 검색. 공백으로 분리된 각 키워드가 하나 이상의 컬럼에 매칭되면 결과에 포함."""
    keywords = [k.strip() for k in query.split() if k.strip()]
    if not keywords:
        return []

    conn = get_db_connection()

    # 전체 행 로드 후 Python에서 스코어링 (273건이라 충분히 빠름)
    rows = conn.execute('SELECT * FROM 세부사업 ORDER BY 파일번호').fetchall()
    conn.close()

    results = []
    for row in rows:
        score = score_relevance(keywords, row)
        if score > 0:
            results.append({**dict(row), '_score': score})

    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:limit]


def score_relevance(keywords: list[str], row) -> float:
    """키워드 매칭 관련도 점수 계산."""
    score = 0.0
    # 컬럼별 가중치
    weights = {
        '세부사업명': 5.0,
        '사업목적': 3.0,
        '시스템_추론': 3.0,
        '시스템_직접언급': 2.0,
        '수혜자': 2.0,
        '사업개요_주요내용': 1.0,
        '단위사업명': 1.5,
        '프로그램명': 1.0,
    }

    matched_keywords = 0
    for kw in keywords:
        kw_matched = False
        for col, weight in weights.items():
            val = str(row[col] or '')
            count = val.count(kw)
            if count > 0:
                score += weight * min(count, 3)  # 같은 컬럼 반복 매칭은 3회까지
                kw_matched = True
        if kw_matched:
            matched_keywords += 1

    # 모든 키워드가 매칭되면 보너스
    if matched_keywords == len(keywords) and len(keywords) > 1:
        score *= 1.5

    # 키워드 하나도 안 맞으면 0점
    if matched_keywords == 0:
        score = 0

    return score


def llm_search(query: str, api_key: str, limit: int = 20) -> list[dict]:
    """OpenAI API를 사용한 LLM 기반 검색."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    # Step 1: 질문 분석
    analysis_prompt = f"""사용자가 정보시스템 필요성을 설명하고 있습니다. 다음 질문을 분석하세요.

질문: "{query}"

다음 JSON 형식으로만 응답하세요:
{{
  "서비스대상": "대국민" 또는 "내부" 또는 "혼합" 또는 null,
  "업무도메인": ["고용서비스", "사회보험", "산업안전보건", "직업훈련·교육", "자격·평가", "근로복지", "노사관계", "외국인고용", "장애인고용", "행정지원", "정보공개·홍보"] 중 관련된 것들,
  "시스템유형": ["홈페이지/포털", "업무처리시스템", "데이터/분석", "교육/학습(LMS)", "내부인프라", "상담/콜센터", "금융/기금", "의료정보"] 중 관련된 것들,
  "키워드": ["핵심", "검색", "키워드", "목록"]
}}"""

    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": analysis_prompt}],
        temperature=0,
    )
    response_text = response.choices[0].message.content.strip()

    # JSON 파싱
    if response_text.startswith('```'):
        response_text = response_text.split('```')[1]
        if response_text.startswith('json'):
            response_text = response_text[4:]
    analysis = json.loads(response_text)

    # Step 2: 분석 결과로 검색
    keywords = analysis.get('키워드', [])
    domains = analysis.get('업무도메인', [])
    sys_types = analysis.get('시스템유형', [])
    target = analysis.get('서비스대상')

    # 키워드 검색 + 도메인/유형 매칭 통합
    all_search_terms = keywords + domains + sys_types
    if target:
        all_search_terms.append(target)

    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM 세부사업 ORDER BY 파일번호').fetchall()
    conn.close()

    results = []
    for row in rows:
        score = score_relevance(all_search_terms, row)
        # 원래 키워드로도 추가 스코어링
        if keywords:
            score += score_relevance(keywords, row) * 0.5
        if score > 0:
            results.append({**dict(row), '_score': score})

    results.sort(key=lambda x: x['_score'], reverse=True)

    # LLM 분석 결과도 함께 반환
    for r in results[:limit]:
        r['_llm_analysis'] = analysis

    return results[:limit]


def get_systems_for_business(세부사업명: str, csv_data: list[dict]) -> list[dict]:
    """CSV에서 세부사업명에 매핑된 시스템 목록 조회."""
    norm = 세부사업명.replace(' ', '')
    systems = []
    for row in csv_data:
        csv_biz = (row.get('세부사업명') or '').replace(' ', '')
        if csv_biz == norm or norm in csv_biz or csv_biz in norm:
            systems.append(row)
    return systems


def get_all_businesses(limit: int = None) -> list[dict]:
    """전체 세부사업 목록 조회."""
    conn = get_db_connection()
    query = 'SELECT * FROM 세부사업 ORDER BY 파일번호'
    if limit:
        query += f' LIMIT {limit}'
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]
