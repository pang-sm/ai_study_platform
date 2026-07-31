"""Generate candidate files only; candidates must pass validator before seed."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for lang in ('c','cpp','python','java'):(ROOT/'backend/data/programming_catalog'/lang).mkdir(parents=True,exist_ok=True)
print('catalog directories ready')
