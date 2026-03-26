"""
273개 세부사업 MD 파일 파서 모듈
- 섹션 분리: 헤딩 키워드 기반
- 테이블 파싱: | 구분자 기반
- 기금/회계 용어 자동 감지
"""
import re
from typing import Optional


def clean_number(text: str) -> Optional[float]:
    """숫자 문자열을 float로 변환. △는 음수, 콤마 제거, <br> 처리."""
    if not text or text.strip() in ('-', '', '해당없음', '없음'):
        return None
    text = text.strip()
    # <br> 포함 시 첫 번째 비어있지 않은 숫자값 취함
    if '<br>' in text:
        parts = [p.strip() for p in text.split('<br>') if p.strip()]
        if parts:
            text = parts[0]
        else:
            return None
    # [] 안 내용 제거
    text = re.sub(r'\[.*?\]', '', text)
    neg = False
    if '△' in text:
        neg = True
        text = text.replace('△', '')
    text = text.replace(',', '').replace(' ', '').replace('백만원', '')
    match = re.search(r'[\d.]+', text)
    if match:
        val = float(match.group())
        return -val if neg else val
    return None


def split_sections(text: str) -> list[tuple[str, str, str]]:
    """MD 텍스트를 (heading_level, heading_text, body) 튜플 리스트로 분할."""
    pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    sections = []
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        level = m.group(1)
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((level, heading, body))
    return sections


def identify_section(heading: str) -> str:
    """헤딩 텍스트를 논리적 섹션명으로 매핑."""
    h = heading.replace(' ', '')
    patterns = [
        ('사업코드정보', '사업코드정보'),
        ('사업성격', '사업성격'),
        ('지원형태및지원율', '지원형태'),
        ('소관부처및시행주체', '소관부처'),
        ('예산총괄표', '예산총괄표'),
        ('지출계획총괄표', '예산총괄표'),
        ('예산지출계획총괄표', '예산총괄표'),
        ('기능별내역사업별', '기능별내역'),
        ('사업목적내용', '사업목적'),
        ('사업개요', '사업개요'),
        ('계획산출근거', '산출근거'),
        ('예산산출근거', '산출근거'),
        ('사업효과', '사업효과'),
        ('타당성조사', '타당성조사'),
        ('총사업비대상', '총사업비대상'),
        ('사업집행절차', '집행절차'),
        ('각종평가', '각종평가'),
        ('결산표', '결산표'),
        ('주요결산사항', '주요결산'),
        ('사업설명자료', '사업설명자료'),
        ('결산내역', '결산내역'),
    ]
    for keyword, section_name in patterns:
        if keyword in h:
            return section_name
    return 'unknown'


def parse_table_rows(text: str) -> list[list[str]]:
    """마크다운 테이블에서 행 데이터를 추출. 구분선(---|) 스킵."""
    rows = []
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('|'):
            continue
        if re.match(r'^\|[\s\-:|]+\|$', line):
            continue
        cells = [c.strip() for c in line.split('|')]
        # 앞뒤 빈 셀 제거 (| ... | 에서 발생)
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        rows.append(cells)
    return rows


def parse_code_info(body: str) -> dict:
    """사업 코드 정보 섹션 파싱."""
    result = {
        '회계구분': None, '회계_기금명': None, '소관': None,
        '실국_기관': None, '계정': None, '분야코드': None,
        '분야명': None, '부문코드': None, '부문명': None,
        '프로그램코드': None, '프로그램명': None,
        '단위사업코드': None, '단위사업명': None,
        '세부사업코드': None, '세부사업명_코드': None,
    }
    rows = parse_table_rows(body)
    # 첫 번째 테이블 (회계/기금 코드) 찾기
    for i, row in enumerate(rows):
        if len(row) >= 7 and any(k in str(row) for k in ['회계', '기금', '소관']):
            # 헤더 행 찾기
            header_row = row
            # 다음 행들에서 코드/명칭 찾기
            for j in range(i + 1, min(i + 3, len(rows))):
                r = rows[j]
                if len(r) >= 7:
                    if '코드' in str(r[0]):
                        code_row = r
                        # 회계/기금 구분
                        val = code_row[1] if len(code_row) > 1 else ''
                        if '<br>' in val:
                            parts = val.split('<br>')
                            result['회계구분'] = '기금' if '기금' in val else '회계'
                            result['회계_기금명'] = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
                        else:
                            result['회계구분'] = '회계' if '회계' in val or '일반' in val else val
                            result['회계_기금명'] = val.strip()
                        # 소관
                        result['소관'] = code_row[2].split('<br>')[-1].strip() if len(code_row) > 2 else None
                        # 실국/기관
                        result['실국_기관'] = code_row[3].split('<br>')[-1].strip() if len(code_row) > 3 else None
                        # 계정
                        result['계정'] = code_row[4].strip() if len(code_row) > 4 else None
                        # 분야
                        result['분야코드'] = code_row[5].strip() if len(code_row) > 5 else None
                        # 부문
                        result['부문코드'] = code_row[6].strip() if len(code_row) > 6 else None
                    elif '명칭' in str(r[0]):
                        if len(r) > 5:
                            result['분야명'] = r[5].strip()
                        if len(r) > 6:
                            result['부문명'] = r[6].strip()
            break

    # 두 번째 테이블 (프로그램/단위/세부사업)
    found_program = False
    for i, row in enumerate(rows):
        if len(row) >= 4 and '프로그램' in str(row) and '단위사업' in str(row):
            found_program = True
            continue
        if found_program and len(row) >= 4:
            if '코드' in str(row[0]):
                result['프로그램코드'] = row[1].strip() if len(row) > 1 else None
                result['단위사업코드'] = row[2].strip() if len(row) > 2 else None
                result['세부사업코드'] = row[3].strip() if len(row) > 3 else None
            elif '명칭' in str(row[0]):
                result['프로그램명'] = row[1].strip() if len(row) > 1 else None
                result['단위사업명'] = row[2].strip() if len(row) > 2 else None
                result['세부사업명_코드'] = row[3].strip() if len(row) > 3 else None
                break
    return result


def parse_business_nature(body: str) -> dict:
    """사업 성격 섹션 파싱."""
    result = {'사업성격': None, '예비타당성실시여부': None, '총사업비관리대상': None}
    rows = parse_table_rows(body)
    # 데이터 행 찾기 (헤더가 아닌 행)
    for row in rows:
        if len(row) >= 3:
            # 헤더가 아닌 실제 데이터 행 식별
            if '신규' in str(row[0]) and '계속' in str(row[1]):
                continue  # 헤더 행 스킵
            # ○ 마커로 사업성격 판별
            for i, cell in enumerate(row[:3]):
                if '○' in cell or 'O' in cell:
                    if i == 0:
                        result['사업성격'] = '신규'
                    elif i == 1:
                        result['사업성격'] = '계속'
                    elif i == 2:
                        result['사업성격'] = '완료'
    return result


def parse_support_type(body: str) -> dict:
    """지원 형태 섹션 파싱."""
    result = {'지원형태': None, '국고보조율': None}
    rows = parse_table_rows(body)
    types = ['직접', '출자', '출연', '보조', '융자']
    for row in rows:
        if len(row) >= 5:
            # 헤더 스킵
            if '직접' in str(row[0]) and '출자' in str(row[1]):
                continue
            found = []
            for i, cell in enumerate(row[:5]):
                if cell.strip() in ('O', '○', 'o'):
                    found.append(types[i])
            if found:
                result['지원형태'] = ';'.join(found)
            # 국고보조율
            if len(row) >= 6 and row[5].strip():
                result['국고보조율'] = row[5].strip()
    return result


def parse_agency(body: str) -> dict:
    """소관부처 및 시행주체 파싱."""
    result = {'소관부서': None, '사업시행주체': None}
    rows = parse_table_rows(body)
    for row in rows:
        if len(row) >= 3:
            if '소관부처' in str(row[1]):
                val = row[2].replace('<br>', ' ').strip()
                # 실·국·과(팀) 이후 텍스트 추출
                val = re.sub(r'실[·\s]*국[·\s]*과\([팀]\)\s*', '', val)
                result['소관부서'] = val.strip()
            if '사업시행주체' in str(row[1]):
                result['사업시행주체'] = row[2].replace('<br>', ' ').strip()
    return result


def parse_budget_summary(body: str) -> dict:
    """예산/지출계획 총괄표 파싱."""
    result = {
        '결산_2024': None, '본예산_2025': None, '추경_2025': None,
        '정부안_2026': None, '확정_2026': None,
        '증감액': None, '증감률': None,
    }
    rows = parse_table_rows(body)
    # 헤더 키워드 - 이 단어가 포함된 행은 헤더
    header_keywords = {'목명', '사업명', '결산', '예산', '계획', '정부안', '확정',
                       '당초', '본예산', '증감', '단위', 'Col'}

    # 데이터 행 찾기: 헤더가 아닌 마지막 행
    data_rows = []
    for row in rows:
        if len(row) >= 6:
            first_cell = row[0].replace('<br>', ' ')
            # 헤더 행 판별: 첫 셀이 헤더 키워드이거나, 셀에 '년' 패턴 포함
            is_header = False
            for kw in header_keywords:
                if kw in first_cell:
                    is_header = True
                    break
            # 추가 헤더 판별: 행에 '년' 패턴이 2개 이상
            year_count = sum(1 for c in row if '년' in str(c))
            if year_count >= 2:
                is_header = True
            if not is_header:
                data_rows.append(row)

    if data_rows:
        # 첫 번째 데이터 행 사용 (합계/총괄)
        row = data_rows[0]
        result['결산_2024'] = clean_number(row[1]) if len(row) > 1 else None

        # 컬럼 수에 따라 매핑
        if len(row) >= 8:
            # 8컬럼: 목명|결산|당초(A)|수정|정부안|확정(B)|증감|증감률
            result['본예산_2025'] = clean_number(row[2])
            result['추경_2025'] = clean_number(row[3])
            result['정부안_2026'] = clean_number(row[4])
            result['확정_2026'] = clean_number(row[5])
            result['증감액'] = clean_number(row[6])
            result['증감률'] = clean_number(row[7])
        elif len(row) >= 7:
            # 7컬럼: 사업명|결산|본예산(A)|정부안|확정(B)|증감|증감률
            result['본예산_2025'] = clean_number(row[2])
            result['정부안_2026'] = clean_number(row[3])
            result['확정_2026'] = clean_number(row[4])
            result['증감액'] = clean_number(row[5])
            result['증감률'] = clean_number(row[6])
        elif len(row) >= 6:
            result['본예산_2025'] = clean_number(row[2])
            result['정부안_2026'] = clean_number(row[3])
            result['확정_2026'] = clean_number(row[4])
            result['증감액'] = clean_number(row[5])

    return result


def parse_narrative_purpose(body: str) -> str:
    """사업목적 내용 텍스트 추출."""
    # 테이블 행과 빈 줄 제거
    lines = []
    for line in body.split('\n'):
        line = line.strip()
        if line and not line.startswith('|'):
            lines.append(line)
    return ' '.join(lines) if lines else None


def parse_overview(body: str) -> dict:
    """사업개요 섹션의 하위 항목 파싱 (키워드 기반)."""
    result = {
        '사업개요_법적근거': None,
        '사업개요_추진경위': None,
        '사업개요_주요내용': None,
        '수혜자': None,
        '사업시행방법': None,
        '사업시행주체_개요': None,
        '사업기간': None,
        '사업비_2022': None, '사업비_2023': None,
        '사업비_2024': None, '사업비_2025': None, '사업비_2026': None,
    }

    full_text = body

    # 법적근거 추출
    m = re.search(r'법령상\s*근거.*?(?=추진경위|주요내용|사업규모|$)', full_text, re.DOTALL)
    if m:
        result['사업개요_법적근거'] = _clean_text(m.group())

    # 추진경위 추출
    m = re.search(r'추진경위(.*?)(?=주요내용|사업규모|사업추진체계|$)', full_text, re.DOTALL)
    if m:
        result['사업개요_추진경위'] = _clean_text(m.group(1))

    # 주요내용 추출 (사업규모, 총사업비, 사업기간 등 하위 항목 포함)
    m = re.search(r'주요내용(.*?)(?=사업추진체계|기타\s*해당)', full_text, re.DOTALL)
    if m:
        result['사업개요_주요내용'] = _clean_text(m.group(1))

    # 수혜자 추출
    m = re.search(r'사업\s*수혜자\s*(.*?)(?=보조|융자|출연|$)', full_text, re.DOTALL)
    if m:
        result['수혜자'] = _clean_text(m.group(1))

    # 사업시행방법
    m = re.search(r'사업시행방법\s*(.*?)(?=사업시행주체|$)', full_text, re.DOTALL)
    if m:
        result['사업시행방법'] = _clean_text(m.group(1))

    # 사업시행주체
    m = re.search(r'사업시행주체\s*(.*?)(?=사업\s*수혜자|보조|$)', full_text, re.DOTALL)
    if m:
        result['사업시행주체_개요'] = _clean_text(m.group(1))

    # 사업기간
    m = re.search(r'사업기간\s*(.*?)(?=최근|기타|사업추진|$)', full_text, re.DOTALL)
    if m:
        result['사업기간'] = _clean_text(m.group(1))

    # 연도별 사업비 테이블
    rows = parse_table_rows(body)
    for i, row in enumerate(rows):
        if len(row) >= 6 and '연도' in str(row[0]) and '2022' in str(row[1]):
            # 헤더 행 - 다음 행이 데이터
            if i + 1 < len(rows) and len(rows[i + 1]) >= 6:
                data = rows[i + 1]
                result['사업비_2022'] = clean_number(data[1])
                result['사업비_2023'] = clean_number(data[2])
                result['사업비_2024'] = clean_number(data[3])
                result['사업비_2025'] = clean_number(data[4])
                result['사업비_2026'] = clean_number(data[5])
            break
        # 헤더와 데이터가 같은 테이블 구조
        if len(row) >= 6 and '사업비' in str(row[0]):
            result['사업비_2022'] = clean_number(row[1])
            result['사업비_2023'] = clean_number(row[2])
            result['사업비_2024'] = clean_number(row[3])
            result['사업비_2025'] = clean_number(row[4])
            result['사업비_2026'] = clean_number(row[5])
            break

    return result


def parse_settlement(body: str) -> dict:
    """결산표 파싱."""
    result = {
        '결산_계획액_2022': None, '결산_집행액_2022': None,
        '결산_집행액_2023': None, '결산_집행액_2024': None,
    }
    rows = parse_table_rows(body)
    for row in rows:
        if len(row) < 6:
            continue
        year = str(row[0]).strip()
        if year == '2022':
            result['결산_계획액_2022'] = clean_number(row[3]) or clean_number(row[1])
            result['결산_집행액_2022'] = clean_number(row[5])
        elif year == '2023':
            result['결산_집행액_2023'] = clean_number(row[5])
        elif year == '2024':
            result['결산_집행액_2024'] = clean_number(row[5])
    return result


def parse_settlement_notes(body: str) -> str:
    """주요 결산사항 텍스트 추출."""
    rows = parse_table_rows(body)
    notes = []
    for row in rows:
        if len(row) >= 2:
            year = str(row[0]).strip().replace('□', '').strip()
            note = row[-1].strip()
            if note and note != '해당없음':
                notes.append(f"{year}: {note}")
    return '; '.join(notes) if notes else None


def parse_performance(body: str) -> str:
    """사업효과 섹션에서 성과지표 이름 추출."""
    rows = parse_table_rows(body)
    indicators = []
    for row in rows:
        for cell in row:
            if '성과지표' in str(cell) and '명' not in str(cell):
                # 성과지표 이름인지 확인
                cleaned = cell.replace('<br>', ' ').strip()
                if cleaned and cleaned not in ('성과지표', '성과지표명'):
                    indicators.append(cleaned)
    # 텍스트에서도 추출
    text_indicators = re.findall(r'성과지표[:\s]*([^\n]+)', body)
    for t in text_indicators:
        t = t.strip()
        if t and t not in indicators:
            indicators.append(t)
    return '; '.join(indicators[:5]) if indicators else None


def extract_system_mentions(full_text: str, known_systems: list[str] = None) -> str:
    """전체 텍스트에서 시스템 관련 키워드 추출."""
    mentions = set()

    # 패턴 매칭
    patterns = [
        r'[가-힣A-Za-z]+시스템',
        r'[가-힣A-Za-z]+포털',
        r'[가-힣A-Za-z]+홈페이지',
        r'[가-힣A-Za-z]+플랫폼',
        r'[가-힣A-Za-z]+전산망',
        r'[가-힣]+정보화',
    ]
    for pat in patterns:
        for m in re.finditer(pat, full_text):
            mention = m.group().strip()
            # 너무 짧거나 일반적인 것 필터링
            if len(mention) >= 4:
                mentions.add(mention)

    # 알려진 시스템명 매칭
    if known_systems:
        for sys_name in known_systems:
            if sys_name in full_text:
                mentions.add(sys_name)

    # 노이즈 필터
    noise = {'예산시스템', '사업시스템', '관리시스템', '추진시스템', '운영시스템',
             '정보시스템', '보험시스템', '지원시스템', '평가시스템', '관련시스템',
             '전산시스템', '해당시스템'}
    mentions = mentions - noise

    return '; '.join(sorted(mentions)) if mentions else None


def parse_budget_detail_items(body: str) -> str:
    """기능별 내역사업별 계획/예산 내역에서 내역사업 목록 추출."""
    items = []
    rows = parse_table_rows(body)
    for row in rows:
        if not row:
            continue
        first_cell = str(row[0])
        # ○, ①, ②, ③ 등으로 시작하는 항목 추출
        if first_cell.startswith('○') or re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩]', first_cell):
            # <br>로 분리된 항목들
            sub_items = first_cell.split('<br>')
            for item in sub_items:
                item = item.strip()
                if item and not item.startswith('|'):
                    items.append(item)
    return '; '.join(items[:20]) if items else None


def _clean_text(text: str) -> Optional[str]:
    """텍스트 정리: 빈 줄 제거, 테이블 행 제거, 공백 정규화."""
    if not text:
        return None
    lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('|') and not re.match(r'^[\-\|]+$', line):
            lines.append(line)
    result = ' '.join(lines)
    result = re.sub(r'\s+', ' ', result).strip()
    return result if result else None


def parse_md_file(filepath: str, known_systems: list[str] = None) -> dict:
    """MD 파일 하나를 파싱하여 딕셔너리 반환."""
    with open(filepath, 'r', encoding='utf-8') as f:
        full_text = f.read()

    # 파일명에서 정보 추출
    import os
    filename = os.path.basename(filepath)
    m = re.match(r'(\d+)_고용노동부_(.+)\.md', filename)
    file_no = int(m.group(1)) if m else 0
    biz_name = m.group(2) if m else filename

    # 섹션 분할
    sections = split_sections(full_text)

    # 섹션별 파싱
    result = {
        '파일번호': file_no,
        '세부사업명': biz_name,
        '파일명': filename,
    }

    section_bodies = {}
    for level, heading, body in sections:
        sec_id = identify_section(heading)
        if sec_id != 'unknown':
            # 같은 섹션이 여러 번 나올 수 있으므로 첫 번째만
            if sec_id not in section_bodies:
                section_bodies[sec_id] = body

    # 코드 정보 테이블이 헤딩 없이 파일 시작부에 있는 경우 처리
    if '사업코드정보' not in section_bodies:
        # 첫 번째 헤딩 앞의 텍스트에서 코드 테이블 찾기
        first_heading = re.search(r'^#{1,6}\s+', full_text, re.MULTILINE)
        if first_heading:
            preamble = full_text[:first_heading.start()]
        else:
            preamble = full_text[:2000]
        if '코드' in preamble and ('프로그램' in preamble or '단위사업' in preamble):
            section_bodies['사업코드정보'] = preamble

    # 사업코드정보
    if '사업코드정보' in section_bodies:
        result.update(parse_code_info(section_bodies['사업코드정보']))
    else:
        result.update({
            '회계구분': None, '회계_기금명': None, '소관': None,
            '실국_기관': None, '계정': None, '분야코드': None,
            '분야명': None, '부문코드': None, '부문명': None,
            '프로그램코드': None, '프로그램명': None,
            '단위사업코드': None, '단위사업명': None,
            '세부사업코드': None, '세부사업명_코드': None,
        })

    # 사업성격
    if '사업성격' in section_bodies:
        result.update(parse_business_nature(section_bodies['사업성격']))
    else:
        result.update({'사업성격': None, '예비타당성실시여부': None, '총사업비관리대상': None})

    # 지원형태
    if '지원형태' in section_bodies:
        result.update(parse_support_type(section_bodies['지원형태']))
    else:
        result.update({'지원형태': None, '국고보조율': None})

    # 소관부처
    if '소관부처' in section_bodies:
        result.update(parse_agency(section_bodies['소관부처']))
    else:
        result.update({'소관부서': None, '사업시행주체': None})

    # 예산총괄표
    if '예산총괄표' in section_bodies:
        result.update(parse_budget_summary(section_bodies['예산총괄표']))
    else:
        result.update({
            '결산_2024': None, '본예산_2025': None, '추경_2025': None,
            '정부안_2026': None, '확정_2026': None,
            '증감액': None, '증감률': None,
        })

    # 기능별 내역
    if '기능별내역' in section_bodies:
        result['내역사업목록'] = parse_budget_detail_items(section_bodies['기능별내역'])
    else:
        result['내역사업목록'] = None

    # 사업목적
    if '사업목적' in section_bodies:
        result['사업목적'] = parse_narrative_purpose(section_bodies['사업목적'])
    else:
        result['사업목적'] = None

    # 사업개요
    if '사업개요' in section_bodies:
        result.update(parse_overview(section_bodies['사업개요']))
    else:
        result.update({
            '사업개요_법적근거': None, '사업개요_추진경위': None,
            '사업개요_주요내용': None, '수혜자': None,
            '사업시행방법': None, '사업시행주체_개요': None,
            '사업기간': None,
            '사업비_2022': None, '사업비_2023': None,
            '사업비_2024': None, '사업비_2025': None, '사업비_2026': None,
        })

    # 산출근거
    if '산출근거' in section_bodies:
        result['산출근거_요약'] = _clean_text(section_bodies['산출근거'][:500])
    else:
        result['산출근거_요약'] = None

    # 사업효과
    if '사업효과' in section_bodies:
        result['성과지표목록'] = parse_performance(section_bodies['사업효과'])
    else:
        result['성과지표목록'] = None

    # 결산표
    if '결산표' in section_bodies:
        result.update(parse_settlement(section_bodies['결산표']))
    else:
        result.update({
            '결산_계획액_2022': None, '결산_집행액_2022': None,
            '결산_집행액_2023': None, '결산_집행액_2024': None,
        })

    # 주요결산
    if '주요결산' in section_bodies:
        result['결산_주요사항'] = parse_settlement_notes(section_bodies['주요결산'])
    else:
        result['결산_주요사항'] = None

    # 시스템 관련
    result['시스템_직접언급'] = extract_system_mentions(full_text, known_systems)
    result['시스템_추론'] = None  # Phase 2에서 채움

    return result
