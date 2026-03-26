import csv
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Read CSV
with open('예산사업_시스템_매핑.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    original_fields = reader.fieldnames
    rows = list(reader)

# ============================================================
# 1. 기관유형 매핑
# ============================================================
ORG_TYPE_MAP = {
    '고용노동부': '본부',
    '고용노동부고객상담센터': '본부',
    '중앙노동위원회': '위원회',
    '최저임금위원회': '위원회',
    '산심위': '위원회',
    '한국산업인력공단': '공단',
    '근로복지공단': '공단',
    '한국장애인고용공단': '공단',
    '장애인고용공단': '공단',
    '한국산업안전보건공단': '공단',
    '한국고용정보원': '정보원',
    '한국기술교육대학교': '교육기관',
    '학교법인한국폴리텍': '교육기관',
    '한국고용노동교육원': '교육기관',
    '노사발전재단': '재단/진흥원',
    '한국사회적기업진흥원': '재단/진흥원',
    '건설근로자공제회': '공제회',
    '한국잡월드': '기타공공',
}

def get_기관유형(row):
    return ORG_TYPE_MAP.get(row['기관명'], '기타공공')

# ============================================================
# 2. 서비스대상 매핑
# ============================================================
INTERNAL_KW = ['그룹웨어', '메신저', '전자결재', '메일시스템', '웹메일', '내부포털',
               'ERP', '전사적자원관리', '경영정보시스템', '경영지원포털',
               'e-감사', '과제관리', '성과관리', '도서관리', '영상회의',
               '데이터품질관리', '지식관리', 'EA관리', '데이터관리포털',
               '통합문서관리', '통합인사급여', '통합재정정보', '통합인증',
               '개인정보접속이력', '개인정보운영지원', '침해사고종합관리',
               '망분리', 'IT-VOC', '업무지원시스템', 'kmc']

PUBLIC_KW = ['홈페이지', '포털', '워크넷', '고용24', 'Q-Net', 'Q-net', 'CQ-Net',
             '토탈서비스', '월드잡플러스', '근로복지넷', '마이스터넷',
             '건설기능플러스', '건설일드림넷', '지앤조이', '일생활균형',
             'jobplusTV', '인터IN메타', '인턴IN메타',
             'VR전용관', '미디어 현장배송', '화학물질정보',
             '화학물질 노출정보', '물질안전보건자료',
             '지역고용정보', '지역일자리맵', '임금직업정보',
             '산재판례정보', '꿈드림공작소']

MIXED_KW = ['고용보험', '노동보험', '산재보험', '가입부과', '취업지원전산망',
            '외국인고용관리', '고용허가제', '장애인고용업무', '바로원',
            '일자리사업 통합', '직업능력개발정보망', '근로감독행정',
            '노사마루', '근로복지서비스', '퇴직연금기록관리',
            '산재예방정보', '위험성평가', '하나로서비스', '퇴직공제EDI',
            '고용서비스 통합', 'STEP', '자격CBT', '출제정보',
            '원격훈련심사', '원격훈련모니터링', '부정훈련관리',
            'HRD4U', 'PDMS', '통합사업관리']

def get_서비스대상(row):
    name = row['시스템명']
    for kw in MIXED_KW:
        if kw in name:
            return '혼합'
    for kw in INTERNAL_KW:
        if kw in name:
            return '내부'
    for kw in PUBLIC_KW:
        if kw in name:
            return '대국민'
    # Fallback heuristics
    if '홈페이지' in name or '포털' in name:
        return '대국민'
    if '시스템' in name and ('관리' in name or '운영' in name):
        return '내부'
    # Additional patterns
    org = row['기관명']
    biz = row.get('세부사업명', '')
    if '상담' in name:
        return '대국민'
    if '플랫폼' in name:
        return '대국민'
    if 'LMS' in name or 'LXP' in name or '교육' in name or '이러닝' in name or 'E-러닝' in name or 'E-HRD' in name:
        return '혼합'
    # Default based on system grade
    grade = row.get('등급', '')
    if grade in ['1', '2']:
        return '혼합'  # High grade systems often serve both
    return '내부'  # Conservative default

# ============================================================
# 3. 업무도메인 매핑
# ============================================================
def get_업무도메인(row):
    name = row['시스템명']
    biz = row.get('세부사업명', '')
    org = row['기관명']

    # 장애인고용
    if '장애인' in name or '장애인' in biz or org in ['한국장애인고용공단', '장애인고용공단']:
        return '장애인고용'

    # 외국인고용
    if '외국인' in name or '고용허가제' in name or '월드잡플러스' in name:
        return '외국인고용'

    # 산업안전보건
    if org == '한국산업안전보건공단':
        if any(kw in name for kw in ['그룹웨어', '홈페이지시스템', 'APOSHO']):
            if '홈페이지' in name:
                return '정보공개·홍보'
            return '행정지원'
        return '산업안전보건'
    if any(kw in name for kw in ['산재예방', '안전보건', '위험성평가', '유해위험', '화학물질',
                                   '물질안전', '클린사업장', '작업환경', 'ePSM', 'KRAS']):
        return '산업안전보건'

    # 사회보험
    if any(kw in name for kw in ['고용보험', '노동보험', '산재보험', '가입부과', '토탈서비스',
                                   '부정수급', 'FDS', '진료비', 'EDI', '산재보상']):
        return '사회보험'
    if '고용보험적용부과' in biz or ('산재보험정보' in biz and '데이터' not in name and 'EDW' not in name):
        return '사회보험'

    # 자격·평가
    if any(kw in name for kw in ['Q-Net', 'Q-net', 'CQ-Net', '자격', '출제정보',
                                   '자격CBT', '국가직무능력표준']):
        return '자격·평가'

    # 직업훈련·교육
    if any(kw in name for kw in ['훈련', 'STEP', 'OKLMS', 'LMS', 'LXP',
                                   'HRD', '직업능력개발', '능력개발', '교육',
                                   '이러닝', 'E-러닝', 'E-HRD', '온라인교육',
                                   '일학습병행', '스마트팩토리', 'PDMS']):
        return '직업훈련·교육'
    if org in ['한국기술교육대학교', '학교법인한국폴리텍', '한국고용노동교육원']:
        if any(kw in name for kw in ['그룹웨어', '전자결재', '웹메일', 'ERP', '경영', '메일']):
            return '행정지원'
        if '홈페이지' in name:
            return '정보공개·홍보'
        return '직업훈련·교육'

    # 근로복지
    if any(kw in name for kw in ['퇴직연금', '근로복지', '복지넷', '복지서비스',
                                   '보육', '어린이집', '임금채권', '일자리안정',
                                   '기금RK', '기금운용', '비대면채널', '재정추계',
                                   '케어정보', 'EMR', 'PACS', '의료']):
        return '근로복지'
    if '근로복지정보' in biz or '근복기금' in biz or '임금채권' in biz:
        return '근로복지'

    # 노사관계
    if any(kw in name for kw in ['노사', '근로감독', '조정심판', '과태료',
                                   '일터혁신', '적극적고용개선', '공공부문 비정규직']):
        return '노사관계'
    if org in ['중앙노동위원회', '노사발전재단']:
        if any(kw in name for kw in ['그룹웨어', '전자결재', '웹메일', 'ERP', '경영', '메일']):
            return '행정지원'
        if '홈페이지' in name:
            return '정보공개·홍보'
        return '노사관계'
    if org == '최저임금위원회':
        return '노사관계'

    # 고용서비스
    if any(kw in name for kw in ['워크넷', '고용24', '취업지원', '일자리',
                                   '고용서비스', '고용복지', '바로원',
                                   '가사랑', '고용정보', '고용조사', '고용통계',
                                   '청년 일경험', '지역고용', '지역일자리',
                                   '임금직업정보', '일자리사업평가']):
        return '고용서비스'
    if '사회적기업' in biz or org == '한국사회적기업진흥원':
        if any(kw in name for kw in ['그룹웨어', '전자결재', '웹메일', 'ERP', '경영']):
            return '행정지원'
        if '홈페이지' in name:
            return '정보공개·홍보'
        return '고용서비스'

    # 행정지원
    if any(kw in name for kw in ['그룹웨어', '메신저', '전자결재', '메일', '웹메일',
                                   'ERP', '전사적자원관리', '경영정보', '경영지원',
                                   'e-감사', '과제관리', '성과관리', '도서관리',
                                   '영상회의', '데이터품질', '지식관리', 'EA관리',
                                   '데이터관리포털', '통합문서관리', '통합인사급여',
                                   '통합재정정보', '통합인증', '개인정보접속이력',
                                   '개인정보운영', '침해사고', '망분리', 'IT-VOC',
                                   '업무지원', 'kmc', '내부포털', '행정통합',
                                   '통합업무', '종합정보시스템', 'IR']):
        return '행정지원'

    # 정보공개·홍보
    if '홈페이지' in name or '포털' in name:
        return '정보공개·홍보'

    # 상담
    if '상담' in name or '1350' in name or '콜' in name:
        return '고용서비스'

    # 건설근로자공제회
    if org == '건설근로자공제회':
        if any(kw in name for kw in ['그룹웨어', '홈페이지']):
            return '행정지원' if '그룹웨어' in name else '정보공개·홍보'
        return '근로복지'

    # 한국잡월드
    if org == '한국잡월드':
        if '홈페이지' in name or '전시운영' in name:
            return '정보공개·홍보'
        return '고용서비스'

    # Default for 고용노동부 본부
    if org == '고용노동부':
        return '행정지원'

    # Default for 근로복지공단
    if org == '근로복지공단':
        return '근로복지'

    # Default for 한국고용정보원
    if org == '한국고용정보원':
        return '고용서비스'

    # Default for 한국산업인력공단
    if org == '한국산업인력공단':
        return '자격·평가'

    return '행정지원'

# ============================================================
# 4. 시스템유형 매핑
# ============================================================
def get_시스템유형(row):
    name = row['시스템명']

    # 의료정보
    if any(kw in name for kw in ['EMR', 'PACS', '의료', '진료비', '케어정보',
                                   '근로자건강센터']):
        return '의료정보'

    # 금융/기금
    if any(kw in name for kw in ['기금RK', '기금운용', '비대면채널', '재정추계',
                                   '요율시뮬레이션', '가입부과', '퇴직연금기록',
                                   '퇴직공제EDI']):
        return '금융/기금'

    # 상담/콜센터
    if any(kw in name for kw in ['상담', '1350', '콜 ']):
        return '상담/콜센터'

    # 교육/학습(LMS)
    if any(kw in name for kw in ['LMS', 'LXP', 'STEP', 'OKLMS', '이러닝', 'E-러닝',
                                   'E-HRD', '온라인교육', '교육운영', '교육포털',
                                   '안전보건교육포털', '꿈드림공작소']):
        return '교육/학습(LMS)'

    # 내부인프라
    if any(kw in name for kw in ['침해사고', '망분리', '통합인증', '개인정보접속이력',
                                   '개인정보운영', '데이터품질', 'EA관리',
                                   '측위 시스템']):
        return '내부인프라'

    # 데이터/분석
    if any(kw in name for kw in ['분석', '통계', '빅데이터', '데이터관리',
                                   'EDW', '시뮬레이션', 'IR', '지역일자리맵',
                                   '지역고용정보', '임금직업정보', '일자리사업평가',
                                   '고용서비스성과', '성과관리']):
        return '데이터/분석'

    # 홈페이지/포털
    if '홈페이지' in name or ('포털' in name and '내부포털' not in name):
        return '홈페이지/포털'

    # 업무처리시스템 (the rest of named systems)
    return '업무처리시스템'

# ============================================================
# 5. 금융관련 매핑
# ============================================================
def get_금융관련(row):
    name = row['시스템명']
    biz = row.get('세부사업명', '')
    if any(kw in name for kw in ['보험', '연금', '기금', '대부', '임금채권',
                                   '가입부과', '토탈서비스', '재정추계', '요율',
                                   '퇴직공제', '비대면채널', 'FDS', '부정수급',
                                   '진료비', 'EDI']):
        return 'Y'
    if any(kw in biz for kw in ['고용보험', '근복기금', '임금채권']):
        return 'Y'
    if '산재보험' in biz and any(kw in name for kw in ['보험', '부과', '진료', '급여', '토탈']):
        return 'Y'
    if any(kw in name for kw in ['근로복지넷', '근로복지서비스', '일자리안정']):
        return 'Y'
    return 'N'

# ============================================================
# 6. 개인정보수준 매핑
# ============================================================
def get_개인정보수준(row):
    name = row['시스템명']
    grade = row.get('등급', '')

    # 고 - 민감정보 대량 처리
    if any(kw in name for kw in ['노동보험', '고용보험', '산재보험', '가입부과',
                                   '토탈서비스', 'EMR', 'PACS', '진료비',
                                   '장애인고용업무', '외국인고용관리', '고용허가제',
                                   '취업지원전산망', '바로원', '근로복지서비스',
                                   '근로복지넷', '퇴직연금기록', '기금RK',
                                   '비대면채널', '통합인사급여', 'FDS', '부정수급',
                                   '산재보상', '케어정보', '의료']):
        return '고'

    # 중 - 일반 개인정보 처리
    if any(kw in name for kw in ['워크넷', '고용24', 'Q-Net', 'CQ-Net', '자격CBT',
                                   '일자리사업', '고용서비스', '고용복지',
                                   '직업능력개발', 'HRD', '월드잡플러스',
                                   '상담', '1350', '근로감독', '노사마루',
                                   '장애인', 'e신고', '퇴직연금홈페이지',
                                   '일자리안정', '직장보육', '가사랑',
                                   '청년 일경험', '통합포털종합정보',
                                   '종합정보시스템', '퇴직공제', '하나로서비스',
                                   '산재예방정보', '위험성평가',
                                   '과정평가형', '출제정보', '원격훈련',
                                   '통합사업관리', 'STEP', 'OKLMS']):
        return '중'

    # Grade-based fallback (but not for simple homepages)
    if grade in ['1', '2'] and '홈페이지' not in name:
        return '중'

    return '저'

# ============================================================
# 7. 서비스채널 매핑
# ============================================================
def get_서비스채널(row):
    name = row['시스템명']

    # 앱
    if '앱' in name:
        return '앱'

    # 콜
    if any(kw in name for kw in ['전화상담', '콜 상담', '콜센터', '1350']):
        return '콜'

    # 복합 - major citizen-facing systems typically have multiple channels
    if any(kw in name for kw in ['고용24', '워크넷', '토탈서비스', 'Q-Net',
                                   '노동보험', '근로복지넷']):
        return '복합'

    return '웹'

# ============================================================
# Apply all categories
# ============================================================
new_fields = ['서비스대상', '업무도메인', '시스템유형', '기관유형', '금융관련', '개인정보수준', '서비스채널']

for row in rows:
    row['서비스대상'] = get_서비스대상(row)
    row['업무도메인'] = get_업무도메인(row)
    row['시스템유형'] = get_시스템유형(row)
    row['기관유형'] = get_기관유형(row)
    row['금융관련'] = get_금융관련(row)
    row['개인정보수준'] = get_개인정보수준(row)
    row['서비스채널'] = get_서비스채널(row)

# Write output
output_fields = original_fields + new_fields
with open('예산사업_시스템_매핑.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=output_fields)
    writer.writeheader()
    writer.writerows(rows)

# Print distribution summary
print(f'=== 총 {len(rows)}건 처리 완료 ===\n')
for field in new_fields:
    print(f'--- {field} ---')
    counts = {}
    for row in rows:
        v = row[field]
        counts[v] = counts.get(v, 0) + 1
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}건')
    print()
