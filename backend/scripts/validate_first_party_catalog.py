from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REQUIRED={'source_key','language','title_zh','summary_zh','statement_zh','starter_code','reference_solution','public_cases','hidden_cases','problem_family_id','language_fit_reason'}
def validate(item):
 missing=[k for k in REQUIRED if not item.get(k)]
 if missing: raise ValueError(','.join(missing))
 if item.get('source')!='first_party_original' or item.get('license')!='project_owned': raise ValueError('invalid first-party provenance')
 if len(item['public_cases'])<3 or len(item['hidden_cases'])<3: raise ValueError('test count')
 return True
if __name__=='__main__':
 items=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'));[validate(x) for x in items];print('validated',len(items))
