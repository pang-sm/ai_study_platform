"""Idempotently merge the verified recovery catalog without deactivating other rows."""
from __future__ import annotations
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from database import SessionLocal,engine
from database_schema import ensure_database_schema
from models import ProgrammingExercise
SNAPSHOT=ROOT/'backend/data/programming_catalog_approved_120.json.gz'
def load():
    with gzip.open(SNAPSHOT,'rt',encoding='utf-8') as h: p=json.load(h)
    if p.get('validated') is not True or p.get('counts')!={'C':30,'C++':30,'Python':30,'Java':30} or len(p.get('exercises',[]))!=120: raise RuntimeError('invalid approved 120 snapshot')
    if any(x.get('quality_status')!='approved' or not x.get('is_active') for x in p['exercises']): raise RuntimeError('snapshot contains inactive/unapproved row')
    return p['exercises']
def main():
    ensure_database_schema(engine); rows=load(); db=SessionLocal(); inserted=updated=0
    try:
        for data in rows:
            row=db.query(ProgrammingExercise).filter_by(source_key=data['source_key']).first()
            if row is None: row=ProgrammingExercise(); db.add(row); inserted+=1
            elif row.quality_status=='rejected': raise RuntimeError('refusing to re-enable rejected source_key '+str(row.source_key))
            else: updated+=1
            for field,value in data.items():
                if field not in {'id','created_at','updated_at'}: setattr(row,field,value)
        db.commit()
        active=db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True),ProgrammingExercise.quality_status=='approved').count()
        print(json.dumps({'inserted':inserted,'updated':updated,'active_approved_total':active},ensure_ascii=False))
    except Exception: db.rollback(); raise
    finally: db.close()
if __name__=='__main__': main()
