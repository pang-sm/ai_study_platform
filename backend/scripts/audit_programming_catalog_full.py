from __future__ import annotations
import json,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import SessionLocal
from models import ProgrammingExercise
ROOT=Path(__file__).resolve().parents[2]
def samples(raw):
 try:return sum(len(x.get('samples',[])) for x in json.loads(raw or '[]') if isinstance(x,dict))
 except:return 0
def main():
 db=SessionLocal()
 try:
  rows=db.query(ProgrammingExercise).all();out=[]; families=defaultdict(list)
  for r in rows:
   active=bool(r.is_active); fam=r.problem_family_id or (r.source_key.rsplit(':',1)[-1] if r.source_key and 'chinese_oj_pilot' in r.source_key else '')
   if active and fam:families[fam].append(r)
   out.append({'language':r.language,'source':r.source_repo,'source_key':r.source_key,'license':r.license,'source_url':r.source_repo,'attribution':r.attribution,'is_active':active,'problem_family_id':fam,'language_fit_reason':r.language_fit_reason,'title_zh':r.title_zh,'summary_zh':r.summary_zh,'statement_zh':r.statement_zh,'input_format_zh':r.input_format_zh,'output_format_zh':r.output_format_zh,'constraints_zh':r.constraints_zh,'title_en':r.title_en,'statement_en':r.statement_en,'starter_code':bool(r.starter_files_json),'public_cases':samples(r.public_tests_json),'hidden_cases':samples(r.hidden_tests_json),'reference_solution':bool(r.reference_files_json),'difficulty':r.difficulty,'knowledge_tags':json.loads(r.tags_json or '[]')})
  active=[x for x in out if x['is_active']];summary={'active_by_language':dict(Counter(x['language'] for x in active)),'chinese_complete':sum(all(x[k] for k in ('title_zh','summary_zh','statement_zh','input_format_zh','output_format_zh','constraints_zh')) for x in active),'missing_statement':sum(not x['statement_zh'] for x in active),'missing_tests':sum(not x['public_cases'] or not x['hidden_cases'] for x in active),'duplicate_families':sum(len({r.language for r in v})>1 for v in families.values()),'license_distribution':dict(Counter(x['license'] for x in active))}
  payload={'summary':summary,'results':out}; target=ROOT/'verification-results';target.mkdir(exist_ok=True);(target/'programming-catalog-full-audit.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8');(target/'programming-catalog-full-audit.md').write_text('# 编程题库全量审计\n\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 finally:db.close()
if __name__=='__main__':main()
