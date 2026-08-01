"""Export the verified active 120-item recovery catalog for deployment."""
from __future__ import annotations
import gzip, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from database import SessionLocal, engine
from database_schema import ensure_database_schema
from models import ProgrammingExercise
OUTPUT=ROOT/'backend/data/programming_catalog_approved_120.json.gz'
def main():
    ensure_database_schema(engine); db=SessionLocal()
    try:
        fields=[c.name for c in ProgrammingExercise.__table__.columns if c.name not in {'id','created_at','updated_at'}]
        rows=db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True),ProgrammingExercise.quality_status=='approved',ProgrammingExercise.source_key.like('recovery-2026:%')).order_by(ProgrammingExercise.language,ProgrammingExercise.id).all()
        counts={lang:sum(r.language==lang for r in rows) for lang in ('C','C++','Python','Java')}
        if len(rows)!=120 or counts!={'C':30,'C++':30,'Python':30,'Java':30}: raise RuntimeError(f'invalid recovery counts: {counts}')
        if len({r.source_key for r in rows})!=len(rows): raise RuntimeError('duplicate source_key')
        payload={'schema_version':1,'validated':True,'counts':counts,'exercises':[{f:getattr(r,f) for f in fields} for r in rows]}
    finally: db.close()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(OUTPUT,'wt',encoding='utf-8',compresslevel=9) as h: json.dump(payload,h,ensure_ascii=False,separators=(',',':'))
    print(json.dumps({'output':str(OUTPUT),'counts':counts,'bytes':OUTPUT.stat().st_size},ensure_ascii=False))
if __name__=='__main__': main()
