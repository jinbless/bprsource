"""
고용노동부 세부사업-시스템 매칭 검색 대시보드
"""
import streamlit as st
import pandas as pd
import sqlite3
import csv
import os
import re

from search import keyword_search, llm_search, get_systems_for_business, get_all_businesses

DB_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.sqlite')
CSV_PATH = os.path.join(os.path.dirname(__file__), '예산사업_시스템_매핑_사람기준.csv')

st.set_page_config(page_title="고용노동부 시스템 매칭", page_icon="🔍", layout="wide")


@st.cache_data
def load_csv_data():
    """CSV 시스템 매핑 데이터 로드."""
    data = []
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


@st.cache_data
def load_db_dataframe():
    """SQLite DB를 DataFrame으로 로드."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT * FROM 세부사업 ORDER BY 파일번호', conn)
    conn.close()
    return df


def render_search_result(result: dict, csv_data: list[dict]):
    """검색 결과 카드 렌더링."""
    score = result.get('_score', 0)
    biz_name = result['세부사업명']
    budget_2026 = result.get('확정_2026')
    purpose = result.get('사업목적') or '-'
    beneficiary = result.get('수혜자') or '-'
    inference = result.get('시스템_추론') or '-'
    mentions = result.get('시스템_직접언급')

    # 기존 시스템 조회
    systems = get_systems_for_business(biz_name, csv_data)

    # 카드
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### [{result['파일번호']}] {biz_name}")
        with col2:
            if budget_2026:
                st.metric("2026 예산", f"{budget_2026:,.0f}백만원")
            else:
                st.caption("예산 정보 없음")

        st.markdown(f"**사업목적:** {purpose[:200]}{'...' if len(purpose) > 200 else ''}")
        st.markdown(f"**수혜자:** {beneficiary}")

        # 추론 시스템유형
        if inference and inference != '-':
            type_match = re.search(r'\[유형\]\s*(.+?)\s*\[근거\]', inference)
            reason_match = re.search(r'\[근거\]\s*(.+)', inference)
            if type_match:
                types = type_match.group(1).split('; ')
                st.markdown("**추론 시스템유형:** " + " ".join(f"`{t}`" for t in types))
            if reason_match:
                st.caption(f"근거: {reason_match.group(1)}")

        # 기존 시스템 목록
        if systems:
            with st.expander(f"기존 시스템 {len(systems)}개", expanded=False):
                sys_df = pd.DataFrame([{
                    '시스템명': s.get('시스템명', ''),
                    '유형': s.get('시스템유형', ''),
                    '대상': s.get('서비스대상', ''),
                    '도메인': s.get('업무도메인', ''),
                    '기관': s.get('기관명', ''),
                } for s in systems])
                st.dataframe(sys_df, use_container_width=True, hide_index=True)
        else:
            st.warning("기존 매핑 시스템 없음 — 신규 시스템 필요 가능")

        # 직접언급 시스템
        if mentions:
            with st.expander("PDF에서 언급된 시스템"):
                st.write(mentions)


def page_search():
    """검색 페이지."""
    st.header("🔍 시스템 매칭 검색")
    st.caption("필요한 시스템을 설명하면, 관련 세부사업과 기존 시스템을 찾아드립니다.")

    csv_data = load_csv_data()

    # 검색 모드
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "어떤 시스템이 필요하신가요?",
            placeholder="예: 국민을 대상으로 퇴직연금 제도 신청 시스템이 필요하다",
        )
    with col2:
        search_mode = st.radio("검색 모드", ["키워드", "LLM"], horizontal=True)

    # LLM 모드일 때 API 키: Secrets → 환경변수 → 직접 입력 순으로 탐색
    api_key = None
    if search_mode == "LLM":
        api_key = st.secrets.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            api_key = st.text_input("OpenAI API Key", type="password",
                                    help="gpt-4.1-nano를 사용합니다. Streamlit Secrets에 OPENAI_API_KEY를 설정하면 자동 적용됩니다.")

    # 검색 실행
    if query:
        with st.spinner("검색 중..."):
            if search_mode == "LLM" and api_key:
                try:
                    results = llm_search(query, api_key)
                    # LLM 분석 결과 표시
                    if results and '_llm_analysis' in results[0]:
                        analysis = results[0]['_llm_analysis']
                        with st.expander("LLM 질문 분석 결과", expanded=True):
                            cols = st.columns(4)
                            with cols[0]:
                                st.markdown(f"**서비스대상:** {analysis.get('서비스대상', '-')}")
                            with cols[1]:
                                domains = analysis.get('업무도메인', [])
                                st.markdown(f"**업무도메인:** {', '.join(domains) if domains else '-'}")
                            with cols[2]:
                                sys_types = analysis.get('시스템유형', [])
                                st.markdown(f"**시스템유형:** {', '.join(sys_types) if sys_types else '-'}")
                            with cols[3]:
                                kws = analysis.get('키워드', [])
                                st.markdown(f"**키워드:** {', '.join(kws) if kws else '-'}")
                except Exception as e:
                    st.error(f"LLM 검색 오류: {e}")
                    results = keyword_search(query)
            else:
                results = keyword_search(query)

        if results:
            st.success(f"{len(results)}건 매칭됨")
            for r in results:
                render_search_result(r, csv_data)
        else:
            st.info("매칭되는 세부사업이 없습니다. 다른 키워드로 검색해보세요.")


def page_dashboard():
    """현황 대시보드."""
    st.header("📊 현황 대시보드")

    df = load_db_dataframe()
    csv_data = load_csv_data()
    csv_df = pd.DataFrame(csv_data)

    # 상단 요약
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("세부사업", f"{len(df)}건")
    with c2:
        st.metric("시스템 매핑", f"{len(csv_df)}건")
    with c3:
        mapped_biz = csv_df['세부사업명'].nunique()
        st.metric("매핑된 세부사업", f"{mapped_biz}개 / {len(df)}개")
    with c4:
        total_budget = df['확정_2026'].sum()
        st.metric("2026 총 예산", f"{total_budget:,.0f}백만원" if pd.notna(total_budget) else "-")

    st.divider()

    # 차트 행 1: 세부사업 분석
    st.subheader("세부사업 분석 (273건)")
    col1, col2 = st.columns(2)

    with col1:
        # 회계구분 분포
        acct_counts = df['회계구분'].value_counts()
        st.bar_chart(acct_counts, horizontal=True)
        st.caption("회계구분 분포")

    with col2:
        # 시스템유형 추론 분포
        type_series = df['시스템_추론'].dropna().apply(
            lambda x: re.search(r'\[유형\]\s*(.+?)\s*\[근거\]', str(x))
        )
        all_types = []
        for m in type_series:
            if m:
                all_types.extend([t.strip() for t in m.group(1).split(';')])
        if all_types:
            type_df = pd.Series(all_types).value_counts()
            st.bar_chart(type_df, horizontal=True)
            st.caption("추론 시스템유형 분포")

    # 예산 Top 20
    st.subheader("2026 예산 규모 Top 20")
    budget_df = df[df['확정_2026'].notna()].nlargest(20, '확정_2026')[
        ['파일번호', '세부사업명', '확정_2026', '회계구분']
    ].reset_index(drop=True)
    budget_df.columns = ['No', '세부사업명', '2026확정(백만원)', '회계구분']
    st.dataframe(budget_df, use_container_width=True, hide_index=True)

    st.divider()

    # 차트 행 2: 시스템 매핑 분석
    st.subheader("시스템 매핑 분석 (197건)")
    col1, col2, col3 = st.columns(3)

    with col1:
        domain_counts = csv_df['업무도메인'].value_counts()
        st.bar_chart(domain_counts, horizontal=True)
        st.caption("업무도메인 분포")

    with col2:
        sys_counts = csv_df['시스템유형'].value_counts()
        st.bar_chart(sys_counts, horizontal=True)
        st.caption("시스템유형 분포")

    with col3:
        target_counts = csv_df['서비스대상'].value_counts()
        st.bar_chart(target_counts, horizontal=True)
        st.caption("서비스대상 분포")


def page_list():
    """세부사업 목록."""
    st.header("📋 세부사업 목록")

    df = load_db_dataframe()

    # 필터
    col1, col2, col3 = st.columns(3)
    with col1:
        acct_filter = st.multiselect("회계구분", df['회계구분'].dropna().unique())
    with col2:
        has_system = st.selectbox("시스템 언급", ["전체", "있음", "없음"])
    with col3:
        search_text = st.text_input("세부사업명 검색")

    # 필터 적용
    filtered = df.copy()
    if acct_filter:
        filtered = filtered[filtered['회계구분'].isin(acct_filter)]
    if has_system == "있음":
        filtered = filtered[filtered['시스템_직접언급'].notna() & (filtered['시스템_직접언급'] != '')]
    elif has_system == "없음":
        filtered = filtered[filtered['시스템_직접언급'].isna() | (filtered['시스템_직접언급'] == '')]
    if search_text:
        filtered = filtered[filtered['세부사업명'].str.contains(search_text, case=False, na=False)]

    st.caption(f"{len(filtered)}건 표시")

    # 테이블
    display_cols = ['파일번호', '세부사업명', '회계구분', '확정_2026', '지원형태',
                    '시스템_직접언급', '시스템_추론']
    display_df = filtered[display_cols].copy()
    display_df.columns = ['No', '세부사업명', '회계', '2026예산', '지원형태', '시스템언급', '시스템추론']

    # 시스템추론에서 유형만 추출
    display_df['시스템추론'] = display_df['시스템추론'].apply(
        lambda x: re.search(r'\[유형\]\s*(.+?)\s*\[근거\]', str(x)).group(1)
        if x and re.search(r'\[유형\]\s*(.+?)\s*\[근거\]', str(x)) else ''
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True,
                 column_config={
                     '2026예산': st.column_config.NumberColumn(format="%.0f"),
                 })

    # 상세 보기
    selected_no = st.number_input("상세 보기 (파일번호 입력)", min_value=1, max_value=273, value=None)
    if selected_no:
        row = df[df['파일번호'] == selected_no]
        if not row.empty:
            r = row.iloc[0]
            st.subheader(f"[{int(r['파일번호'])}] {r['세부사업명']}")
            st.markdown(f"**사업목적:** {r.get('사업목적', '-')}")
            st.markdown(f"**수혜자:** {r.get('수혜자', '-')}")
            st.markdown(f"**법적근거:** {r.get('사업개요_법적근거', '-')}")
            st.markdown(f"**시스템 추론:** {r.get('시스템_추론', '-')}")
            st.markdown(f"**시스템 직접언급:** {r.get('시스템_직접언급', '-')}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**예산 정보:**")
                budget_data = {
                    '2024 결산': r.get('결산_2024'),
                    '2025 본예산': r.get('본예산_2025'),
                    '2026 확정': r.get('확정_2026'),
                    '증감액': r.get('증감액'),
                    '증감률(%)': r.get('증감률'),
                }
                for k, v in budget_data.items():
                    st.write(f"  {k}: {v:,.0f}" if pd.notna(v) else f"  {k}: -")
            with col2:
                st.markdown("**분류 정보:**")
                st.write(f"  회계구분: {r.get('회계구분', '-')}")
                st.write(f"  회계/기금: {r.get('회계_기금명', '-')}")
                st.write(f"  지원형태: {r.get('지원형태', '-')}")
                st.write(f"  사업시행주체: {r.get('사업시행주체', '-')}")


# 메인
def main():
    # 사이드바 네비게이션
    st.sidebar.title("고용노동부")
    st.sidebar.caption("예산사업-시스템 매칭")

    page = st.sidebar.radio(
        "메뉴",
        ["🔍 시스템 매칭 검색", "📊 현황 대시보드", "📋 세부사업 목록"],
        label_visibility="collapsed",
    )

    if page == "🔍 시스템 매칭 검색":
        page_search()
    elif page == "📊 현황 대시보드":
        page_dashboard()
    elif page == "📋 세부사업 목록":
        page_list()


if __name__ == '__main__':
    main()
