"""Transactional, idempotent seed for validated first-party C candidates."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import SessionLocal
from models import ProgrammingExercise
def seed(items):
 db=SessionLocal();added=0
 try:
  for x in items:
   if db.query(ProgrammingExercise).filter_by(source_key=x['source_key']).first():continue
   samples=[{'id':f"{x['source_key']}-public-{i}",'visibility':'public','stdin_text':a,'expected_stdout':b} for i,(a,b) in enumerate(x['cases'],1)]
   hidden=[{'id':f"{x['source_key']}-hidden-{i}",'visibility':'hidden','stdin_text':a,'expected_stdout':b} for i,(a,b) in enumerate(x['cases'],1)]
   db.add(ProgrammingExercise(slug=x['source_key'].replace(':','-'),source_key=x['source_key'],language='C',title=x['title'],title_zh=x['title'],summary_zh=x['title']+'：读取两个整数并输出计算结果。',statement_zh=x['title']+'。',input_format_zh='一行两个整数。',output_format_zh='输出一个整数。',constraints_zh='输入在 64 位整数范围内。',title_en=x['title'],statement_en=x['title'],difficulty='入门',tags_json='["C","数值运算"]',description=x['title'],starter_files_json='[{"path":"main.c","content":"#include <stdio.h>\\nint main(void){return 0;}"}]',reference_files_json=json.dumps([{'path':'main.c','content':x['reference']}]),public_tests_json=json.dumps([{'samples':samples}]),hidden_tests_json=json.dumps([{'samples':hidden}]),official_test_files_json='[]',source_repo='first_party_original',source_path=x['source_key'],source_commit='generated',license='project_owned',license_text='第一方原创',attribution='AI-assisted original content created for ai_study_platform',reference_verified=True,starter_verified=True,is_active=True,problem_family_id=x['source_key'],language_fit_reason='训练 C 的 scanf/printf 与整数运算。'));added+=1
  db.commit();return added
 except: db.rollback();raise
 finally: db.close()
