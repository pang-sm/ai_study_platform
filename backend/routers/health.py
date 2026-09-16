"""Operational health routes (FastAPI modularization wave 2)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/api/health")
def api_health():
    return health()
