from datetime import date
from core.claim_time_resolver import resolve_relative_time
from schemas.claim import ClaimSchema

def claim(time,source=None):
 return ClaimSchema(claim_id='C',source_sentence=source or time,indicator='지표',value=1,unit='%',time=time,parse_status='AUTO_OK')

def test_last_month():
 r=resolve_relative_time(claim('지난달'),date(2025,11,4));assert (r.time,r.frequency)==('2025년 10월','월')
def test_relative_without_date_holds():
 r=resolve_relative_time(claim('지난달'),None);assert r.parse_status=='HOLD' and r.parse_reason=='ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME'
def test_this_year_quarter():
 r=resolve_relative_time(claim('올해 1분기'),date(2024,4,30));assert (r.time,r.frequency)==('2024년 1분기','분기')
def test_last_year_quarter():
 r=resolve_relative_time(claim('지난해 4분기'),date(2025,2,1));assert (r.time,r.frequency)==('2024년 4분기','분기')
def test_half_year_is_supported_by_kosis_parameter_api():
 r=resolve_relative_time(claim('올해 상반기'),date(2024,8,1));assert (r.time,r.frequency,r.parse_status)==('2024년 상반기','반기','AUTO_OK')
def test_named_last_month():
 r=resolve_relative_time(claim('작년 11월'),date(2025,1,22));assert r.time=='2024년 11월'
def test_last_named_month():
 r=resolve_relative_time(claim('지난 8월'),date(2025,10,29));assert r.time=='2025년 8월'
