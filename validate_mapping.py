"""
기존 CSV(24개 세부사업 → 197개 시스템) 매핑과 273개 세부사업 DB 교차 검증
"""
import csv
import sqlite3
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), '예산사업_시스템_매핑_사람기준.csv')
DB_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.sqlite')


def load_csv_mapping():
    """기존 CSV에서 세부사업별 시스템 매핑 로드."""
    mapping = {}  # 세부사업명 → [시스템 정보 리스트]
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            biz = row.get('세부사업명', '').strip()
            if not biz:
                continue
            if biz not in mapping:
                mapping[biz] = []
            mapping[biz].append({
                '기관명': row.get('기관명', ''),
                '시스템명': row.get('시스템명', ''),
                '병합시스템명': row.get('병합시스템명', ''),
                '등급': row.get('등급', ''),
                '서비스대상': row.get('서비스대상', ''),
                '업무도메인': row.get('업무도메인', ''),
                '시스템유형': row.get('시스템유형', ''),
                '금융관련': row.get('금융관련', ''),
            })
    return mapping


def load_db_businesses():
    """세부사업 DB에서 전체 사업 로드."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM 세부사업 ORDER BY 파일번호').fetchall()
    conn.close()
    return rows


def normalize_name(name):
    """세부사업명 정규화 (공백, 괄호 등 통일)."""
    return name.replace(' ', '').replace('　', '').strip()


def main():
    csv_mapping = load_csv_mapping()
    db_rows = load_db_businesses()

    print('=' * 70)
    print('기존 CSV ↔ 세부사업 DB 교차 검증 리포트')
    print('=' * 70)
    print(f'\n기존 CSV: {len(csv_mapping)}개 세부사업, 총 {sum(len(v) for v in csv_mapping.values())}개 시스템')
    print(f'세부사업 DB: {len(db_rows)}개 세부사업')

    # DB 사업명 인덱스 (정규화)
    db_index = {}
    for row in db_rows:
        norm = normalize_name(row['세부사업명'])
        db_index[norm] = row

    # 1. CSV 세부사업 → DB 매칭
    print('\n' + '-' * 70)
    print('1. CSV 세부사업 → DB 매칭')
    print('-' * 70)
    matched = 0
    unmatched_csv = []
    match_details = []
    for csv_biz, systems in sorted(csv_mapping.items()):
        norm = normalize_name(csv_biz)
        db_row = db_index.get(norm)
        if db_row:
            matched += 1
            match_details.append((csv_biz, db_row, systems))
        else:
            # 부분 매칭 시도
            found = False
            for db_norm, db_row in db_index.items():
                if norm in db_norm or db_norm in norm:
                    matched += 1
                    match_details.append((csv_biz, db_row, systems))
                    found = True
                    break
            if not found:
                unmatched_csv.append((csv_biz, len(systems)))

    print(f'  매칭 성공: {matched}/{len(csv_mapping)}')
    if unmatched_csv:
        print(f'  매칭 실패:')
        for name, count in unmatched_csv:
            print(f'    - {name} ({count}개 시스템)')

    # 2. 시스템_직접언급 vs CSV 시스템명 비교
    print('\n' + '-' * 70)
    print('2. 시스템_직접언급 vs CSV 시스템명 비교')
    print('-' * 70)
    for csv_biz, db_row, systems in match_details:
        db_mentions = set()
        if db_row['시스템_직접언급']:
            db_mentions = set(m.strip() for m in db_row['시스템_직접언급'].split(';'))

        csv_system_names = set(s['시스템명'] for s in systems if s['시스템명'])
        csv_merged_names = set(s['병합시스템명'] for s in systems if s['병합시스템명'])
        all_csv_names = csv_system_names | csv_merged_names

        # CSV에 있지만 DB에서 언급 안 된 시스템
        missing_in_db = all_csv_names - db_mentions
        # DB에서 언급되었지만 CSV에 없는 시스템
        extra_in_db = db_mentions - all_csv_names

        if missing_in_db or extra_in_db:
            print(f'\n  [{db_row["파일번호"]}] {csv_biz}')
            print(f'    CSV 시스템 수: {len(systems)}')
            print(f'    DB 직접언급 수: {len(db_mentions)}')
            if missing_in_db:
                print(f'    CSV에만 존재: {", ".join(sorted(missing_in_db)[:5])}{"..." if len(missing_in_db) > 5 else ""}')
            if extra_in_db:
                print(f'    DB에만 존재: {", ".join(sorted(extra_in_db)[:5])}{"..." if len(extra_in_db) > 5 else ""}')

    # 3. 시스템이 없는 세부사업 중 시스템 언급이 있는 것
    print('\n' + '-' * 70)
    print('3. CSV에 없지만 DB에서 시스템이 언급된 세부사업')
    print('-' * 70)
    csv_norms = set(normalize_name(k) for k in csv_mapping.keys())
    new_system_businesses = []
    for row in db_rows:
        norm = normalize_name(row['세부사업명'])
        if norm not in csv_norms and row['시스템_직접언급']:
            mentions = row['시스템_직접언급'].split(';')
            new_system_businesses.append((row['파일번호'], row['세부사업명'], mentions))

    print(f'  총 {len(new_system_businesses)}개 사업에서 시스템 언급 발견')
    for no, name, mentions in sorted(new_system_businesses)[:20]:
        print(f'    [{no}] {name}: {", ".join(m.strip() for m in mentions[:3])}{"..." if len(mentions) > 3 else ""}')
    if len(new_system_businesses) > 20:
        print(f'    ... 외 {len(new_system_businesses) - 20}건')

    # 4. 업무도메인/시스템유형 분포
    print('\n' + '-' * 70)
    print('4. CSV 시스템 분류 분포')
    print('-' * 70)
    domain_counts = {}
    type_counts = {}
    for systems in csv_mapping.values():
        for s in systems:
            d = s.get('업무도메인', '?')
            t = s.get('시스템유형', '?')
            domain_counts[d] = domain_counts.get(d, 0) + 1
            type_counts[t] = type_counts.get(t, 0) + 1

    print('  업무도메인:')
    for k, v in sorted(domain_counts.items(), key=lambda x: -x[1]):
        print(f'    {k}: {v}')
    print('  시스템유형:')
    for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f'    {k}: {v}')


if __name__ == '__main__':
    main()
