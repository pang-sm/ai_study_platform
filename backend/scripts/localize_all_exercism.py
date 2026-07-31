"""Idempotently fill stable Chinese display fields for imported Exercism rows."""
from __future__ import annotations
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import SessionLocal
from models import ProgrammingExercise

# Existing curated card copy remains the title/summary source; source English
# is preserved separately and never rendered as the primary description.
COPY = Path(__file__).resolve().parents[2] / 'frontend/src/components/programmingExerciseCopy.js'
OVERRIDES = {'electric-bill': ('电费计算', '根据用电量和分段费率计算电费。')}
def curated():
 text=COPY.read_text(encoding='utf-8')
 return {m.group(1): (m.group(2),m.group(3)) for m in re.finditer(r'^[ \t]*["\']?([\w-]+)["\']?\s*:\s*\["([^"]+)",\s*"([^"]+)"\]',text,re.M)}
def main():
 data=curated(); db=SessionLocal()
 try:
  rows=db.query(ProgrammingExercise).filter(ProgrammingExercise.source_repo!='first_party_original',ProgrammingExercise.is_active.is_(True)).all()
  for r in rows:
   key=r.slug.replace('python-','').replace('cpp-','').replace('java-','').replace('c-','')
   title,summary=data.get(key,OVERRIDES.get(key,(r.title, '请根据函数签名完成题目要求，并通过随题测试。')))
   r.title_en=r.title_en or r.title; r.statement_en=r.statement_en or r.description
   r.title_zh=r.title_zh or title; r.summary_zh=r.summary_zh or summary
   r.statement_zh=r.statement_zh or f'实现题目提供的函数接口，完成“{title}”要求。函数名、参数、返回值及边界行为以 starter code 和测试为准。{summary}'
   r.input_format_zh=r.input_format_zh or '通过测试调用题目提供的函数；参数、类型与顺序以函数签名为准。'
   r.output_format_zh=r.output_format_zh or '返回测试接口要求的结果；不使用标准输入输出。'
   r.constraints_zh=r.constraints_zh or '输入范围、边界条件与异常行为以随题测试接口为准。'
  db.commit(); print('localized',len(rows))
 finally: db.close()
if __name__=='__main__': main()
