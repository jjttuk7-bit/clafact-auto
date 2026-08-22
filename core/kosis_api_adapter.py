"""Adapter from complete EvidenceCell coordinates to KOSIS Parameter API."""
import re
from core.kosis_value_transport import get_parameter_data

_FREQUENCY={'월':'M','monthly':'M','month':'M','년':'Y','year':'Y','yearly':'Y','annual':'Y','분기':'Q','반기':'H'}

class KosisApiLookup:
 def __init__(self,api_key,*,retries=2,timeout_seconds=10):
  self._api_key=api_key;self._retries=max(1,retries);self._timeout_seconds=max(.1,timeout_seconds)
 def __call__(self,cell):return self.fetch_many([cell])
 def fetch_many(self,cells):
  if not cells:return []
  first=cells[0];coordinate=(first.org_id,first.tbl_id,first.itm_id,first.prd_se,tuple(_ordered_codes(first)))
  if not coordinate[-1]:raise ValueError('KOSIS_COORDINATE_CODES_REQUIRED')
  if any((c.org_id,c.tbl_id,c.itm_id,c.prd_se,tuple(_ordered_codes(c)))!=coordinate for c in cells[1:]):raise ValueError('KOSIS_RANGE_COORDINATE_MISMATCH')
  periods=sorted(api_period(c.prd_de) for c in cells);kind=_FREQUENCY.get(first.prd_se.casefold(),first.prd_se)
  return get_parameter_data(self._api_key,first.org_id,first.tbl_id,first.itm_id,kind,periods[0],periods[-1],list(coordinate[-1]),retries=self._retries,timeout_seconds=self._timeout_seconds)

def build_kosis_api_lookup(api_key,*,retries=2,timeout_seconds=10):return KosisApiLookup(api_key,retries=retries,timeout_seconds=timeout_seconds)
def api_period(value):
 if m:=re.fullmatch(r'(\d{4})-?Q([1-4])',value,re.I):return f'{m.group(1)}0{m.group(2)}'
 return value.replace('-','')
_api_period = api_period

def _ordered_codes(cell):
 codes=[]
 for i in range(1,9):
  code=cell.dimension_codes.get(f'C{i}')
  if code is None:break
  codes.append(code)
 return codes or list(cell.dimension_codes.values())
