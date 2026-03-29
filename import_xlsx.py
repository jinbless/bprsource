"""
엑셀 파일(세부사업_DB.xlsx)을 읽어서 SQLite DB와 CSV를 덮어쓰기.

사용법:
  py -X utf8 import_xlsx.py
  py -X utf8 import_xlsx.py 수정된파일.xlsx   (다른 파일명 지정 가능)
"""
import sys
import os
import sqlite3
import pandas as pd

XLSX_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.xlsx')
DB_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.sqlite')
CSV_PATH = os.path.join(os.path.dirname(__file__), '세부사업_DB.csv')


def main():
    xlsx_path = sys.argv[1] if len(sys.argv) > 1 else XLSX_PATH

    if not os.path.exists(xlsx_path):
        print(f'오류: {xlsx_path} 파일이 없습니다.')
        return

    # 엑셀 읽기
    df = pd.read_excel(xlsx_path, engine='openpyxl')
    print(f'엑셀 로드: {len(df)}행 × {len(df.columns)}컬럼')
    print(f'  파일: {xlsx_path}')

    # SQLite 덮어쓰기
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('세부사업', conn, index=False, if_exists='replace')
    conn.close()
    print(f'SQLite 저장: {DB_PATH}')

    # CSV 내보내기
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    print(f'CSV 저장: {CSV_PATH}')

    print(f'\n완료. 대시보드를 새로고침하면 반영됩니다.')


if __name__ == '__main__':
    main()
