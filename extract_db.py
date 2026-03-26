"""
273개 세부사업 MD 파일에서 구조화 DB 추출
출력: 세부사업_DB.sqlite, 세부사업_DB.csv, extraction_log.txt
"""
import os
import csv
import sqlite3
import glob
import traceback
from parser_md import parse_md_file

PDF_DIR = os.path.join(os.path.dirname(__file__), 'pdf')
CSV_MAPPING = os.path.join(os.path.dirname(__file__), '예산사업_시스템_매핑.csv')
OUTPUT_DB = os.path.join(os.path.dirname(__file__), '세부사업_DB.sqlite')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), '세부사업_DB.csv')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'extraction_log.txt')

# DB 컬럼 순서 정의
COLUMNS = [
    '파일번호', '세부사업명', '파일명',
    # 코드 정보
    '회계구분', '회계_기금명', '소관', '실국_기관', '계정',
    '분야코드', '분야명', '부문코드', '부문명',
    '프로그램코드', '프로그램명', '단위사업코드', '단위사업명',
    '세부사업코드', '세부사업명_코드',
    # 사업 성격
    '사업성격', '예비타당성실시여부', '총사업비관리대상',
    # 지원 형태
    '지원형태', '국고보조율',
    # 소관부처
    '소관부서', '사업시행주체',
    # 예산 총괄
    '결산_2024', '본예산_2025', '추경_2025',
    '정부안_2026', '확정_2026', '증감액', '증감률',
    # 내역사업
    '내역사업목록',
    # 서술형
    '사업목적',
    '사업개요_법적근거', '사업개요_추진경위', '사업개요_주요내용',
    '수혜자', '사업시행방법', '사업시행주체_개요', '사업기간',
    # 연도별 사업비
    '사업비_2022', '사업비_2023', '사업비_2024', '사업비_2025', '사업비_2026',
    # 산출근거/성과
    '산출근거_요약', '성과지표목록',
    # 결산
    '결산_계획액_2022', '결산_집행액_2022', '결산_집행액_2023', '결산_집행액_2024',
    '결산_주요사항',
    # 시스템
    '시스템_직접언급', '시스템_추론',
]


def load_known_systems() -> list[str]:
    """기존 CSV에서 알려진 시스템명 로드."""
    systems = set()
    if not os.path.exists(CSV_MAPPING):
        # 다른 이름 시도
        alt = os.path.join(os.path.dirname(__file__), '예산사업_시스템_매핑_사람기준.csv')
        if os.path.exists(alt):
            csv_path = alt
        else:
            return []
    else:
        csv_path = CSV_MAPPING

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if '시스템명' in row and row['시스템명']:
                systems.add(row['시스템명'].strip())
            if '병합시스템명' in row and row['병합시스템명']:
                systems.add(row['병합시스템명'].strip())
    return list(systems)


def create_db(conn):
    """SQLite 테이블 생성."""
    numeric_cols = {
        '파일번호', '결산_2024', '본예산_2025', '추경_2025',
        '정부안_2026', '확정_2026', '증감액', '증감률',
        '사업비_2022', '사업비_2023', '사업비_2024', '사업비_2025', '사업비_2026',
        '결산_계획액_2022', '결산_집행액_2022', '결산_집행액_2023', '결산_집행액_2024',
    }
    col_defs = []
    for col in COLUMNS:
        if col == '파일번호':
            col_defs.append(f'"{col}" INTEGER PRIMARY KEY')
        elif col in numeric_cols:
            col_defs.append(f'"{col}" REAL')
        else:
            col_defs.append(f'"{col}" TEXT')

    sql = f'CREATE TABLE IF NOT EXISTS 세부사업 ({", ".join(col_defs)})'
    conn.execute(sql)
    conn.commit()


def insert_row(conn, data: dict):
    """한 행 INSERT."""
    placeholders = ', '.join(['?' for _ in COLUMNS])
    col_names = ', '.join([f'"{c}"' for c in COLUMNS])
    values = [data.get(c) for c in COLUMNS]
    conn.execute(f'INSERT OR REPLACE INTO 세부사업 ({col_names}) VALUES ({placeholders})', values)


def export_csv(conn):
    """SQLite에서 CSV 내보내기."""
    cursor = conn.execute(f'SELECT * FROM 세부사업 ORDER BY "파일번호"')
    rows = cursor.fetchall()
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow(row)


def main():
    # 알려진 시스템명 로드
    known_systems = load_known_systems()
    print(f"알려진 시스템명 {len(known_systems)}개 로드됨")

    # MD 파일 목록
    md_files = sorted(glob.glob(os.path.join(PDF_DIR, '*.md')))
    print(f"MD 파일 {len(md_files)}개 발견")

    # DB 연결
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)
    conn = sqlite3.connect(OUTPUT_DB)
    create_db(conn)

    # 로그 파일
    log = open(LOG_FILE, 'w', encoding='utf-8')
    success_count = 0
    error_count = 0
    warnings = []

    for filepath in md_files:
        filename = os.path.basename(filepath)
        try:
            data = parse_md_file(filepath, known_systems)

            # 기본 검증
            w = []
            if not data.get('사업목적'):
                w.append('사업목적 누락')
            if not data.get('확정_2026') and not data.get('본예산_2025'):
                w.append('예산 데이터 누락')
            if not data.get('회계구분'):
                w.append('회계구분 누락')

            if w:
                msg = f"WARNING [{filename}]: {', '.join(w)}"
                log.write(msg + '\n')
                warnings.append(msg)

            insert_row(conn, data)
            success_count += 1
        except Exception as e:
            msg = f"ERROR [{filename}]: {str(e)}"
            log.write(msg + '\n')
            log.write(traceback.format_exc() + '\n')
            error_count += 1

    conn.commit()

    # CSV 내보내기
    export_csv(conn)

    # 통계 출력
    summary = f"""
=== 추출 완료 ===
성공: {success_count}개
실패: {error_count}개
경고: {len(warnings)}개
출력: {OUTPUT_DB}, {OUTPUT_CSV}
"""
    print(summary)
    log.write(summary)

    # NULL 비율 통계
    log.write('\n=== 컬럼별 NULL 비율 ===\n')
    for col in COLUMNS:
        cursor = conn.execute(f'SELECT COUNT(*) FROM 세부사업 WHERE "{col}" IS NULL OR "{col}" = ""')
        null_count = cursor.fetchone()[0]
        pct = (null_count / success_count * 100) if success_count > 0 else 0
        if pct > 0:
            log.write(f'  {col}: {null_count}/{success_count} ({pct:.1f}%)\n')

    log.close()
    conn.close()
    print(f"로그: {LOG_FILE}")


if __name__ == '__main__':
    main()
