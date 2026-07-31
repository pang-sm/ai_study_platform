"""Approved-source-only, idempotent catalog importer.

This deliberately refuses unapproved sources and does not deactivate or delete
existing exercises.  A source adapter must provide already license-reviewed
records before it can write to the catalog.
"""
from __future__ import annotations
import json, argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from database import engine
from database_schema import ensure_database_schema
REGISTRY=ROOT/'backend/data/programming_source_registry.json'
def approved_sources():
 data=json.loads(REGISTRY.read_text(encoding='utf8'))
 return {x['source_id']:x for x in data['sources'] if x.get('approved')}
def validate_record(record, approved):
 required={'source_id','language','source_key','title_zh','summary_zh','statement_zh','input_format_zh','output_format_zh','constraints_zh','title_en','statement_en','starter_files','reference_files','public_cases','hidden_cases','license','attribution','problem_family_id','language_fit_reason'}
 missing=[k for k in required if not record.get(k)]
 if missing: raise ValueError('missing fields: '+','.join(missing))
 if record['source_id'] not in approved: raise ValueError('source is not approved')
 if len(record['public_cases'])<3 or len(record['hidden_cases'])<3: raise ValueError('insufficient test cases')
 return True
def main():
 ensure_database_schema(engine)
 parser=argparse.ArgumentParser();parser.add_argument('--records');args=parser.parse_args();approved=approved_sources()
 if not args.records: print('approved sources:', ', '.join(approved));return
 records=json.loads(Path(args.records).read_text(encoding='utf8'))
 for record in records: validate_record(record,approved)
 print('validated',len(records),'licensed records')
if __name__=='__main__': main()
