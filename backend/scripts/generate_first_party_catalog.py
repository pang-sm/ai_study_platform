"""Generate candidate files only; candidates must pass validator before seed."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'backend'))
from database import engine
from database_schema import ensure_database_schema
print('schema',ensure_database_schema(engine))
for lang in ('c','cpp','python','java'):(ROOT/'backend/data/programming_catalog'/lang).mkdir(parents=True,exist_ok=True)
print('catalog directories ready')
