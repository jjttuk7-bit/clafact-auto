"""Structural compatibility checks before semantic scoring."""
import re
from core.claim_dimensions import dimension_member_values
from core.unit_normalizer import compatible_units
from schemas.candidate import HardGuardResult

def apply_hard_guard(c,x):
 r=[]
 if x.metadata_status in {'LIVE_SEARCH_UNRESOLVED','OFFICIAL_ITEM_METADATA_UNAVAILABLE'} or (x.metadata_status=='OFFICIAL_PERIOD_METADATA_UNAVAILABLE' and not _safe(c,x)) or (c.frequency and x.metadata_status=='OFFICIAL_ITEM_METADATA_READY' and not x.frequency):r+=['METADATA_INCOMPLETE']
 if _freq(c,x):r+=['FREQUENCY_CONFLICT']
 if _unit(c,x):r+=['UNIT_CONFLICT']
 if _age(c,x):r+=['AGE_DIMENSION_REQUIRED']
 if c.dimension and 'sex' in c.dimension and not _has(x,'성별'):r+=['SEX_DIMENSION_REQUIRED']
 if c.region and c.region not in {'전국','대한민국','한국'} and not any(_has(x,t) for t in ('시도','지역','행정','읍면')):r+=['REGION_GRANULARITY_CONFLICT']
 if _dim(c,x):r+=['DIMENSION_MEMBER_CONFLICT']
 if _time(c,x):r+=['TIME_NOT_AVAILABLE']
 if any(t in c.source_sentence for t in ('전망','예측','예상')):r+=['FORECAST_CLAIM']
 return HardGuardResult(passed=not r,reject_codes=r)
def _safe(c,x):return bool(x.core_item_ids and x.dimension_member_codes and x.frequency and not _freq(c,x))
def _freq(c,x):return bool(c.frequency and x.frequency and _key(c.frequency) not in {_key(v) for v in x.frequency.split('|')})
def _unit(c,x):
 if c.calculation=='DIFFERENCE' and _key(c.unit or '') in {'%p','%포인트','퍼센트포인트','percentagepoints'}:return not any(_key(v) in {'%','퍼센트'} for v in x.unit_names)
 if c.calculation in {'GROWTH_RATE','SHARE','RATIO','MULTIPLE'}:return False
 return bool(c.unit and x.unit_names and not any(compatible_units(c.unit,v) for v in x.unit_names))
def _age(c,x):
 if not c.population or '세' not in c.population or _has(x,'연령'):return False
 req=_key(c.population).replace('계','');scope=_key(' '.join([x.tbl_name,*x.core_item_names]))
 return not ((req and req in scope) or (x.source_stat_id=='OFFICIAL_RECURRING_DOMAIN_BINDING' and '15세이상' in req and '경제활동인구' in scope))
def _dim(c,x):
 if not c.dimension or not x.dimension_members:return False
 official={_key(v) for values in x.dimension_members.values() for v in values};scope=_key(' '.join([x.tbl_name,*x.core_item_names]))
 return any(not (m in official or m in scope or sum(m in o for o in official)==1) for m in (_key(v) for v in dimension_member_values(c.dimension)))
def _time(c,x):
 if not c.time or not x.start_period or not x.end_period:return False
 m=re.search(r'\d{4}',c.time)
 if not m:return False
 try:y=int(m.group());return y<int(x.start_period[:4]) or y>int(x.end_period[:4])
 except ValueError:return False
def _has(x,t):return any(t in n for n in x.dimension_names)
def _key(v):
 n=re.sub(r'\s+','',v).casefold();n={'monthly':'월','month':'월','m':'월','yearly':'년','year':'년','annual':'년','y':'년','연':'년','연간':'년','quarterly':'분기','quarter':'분기','q':'분기','halfyear':'반기'}.get(n,n)
 return n.replace('~','').replace('-','').replace('여성','여자').replace('남성','남자').replace('합계','계').replace('총계','계').replace('전체','계').replace('대한민국','전국').replace('한국','전국')
