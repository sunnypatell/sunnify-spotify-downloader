from fastapi import APIRouter
from core.singleton.logger import logger

router = APIRouter(tags=["health"])


@router.get("/")
async def home():
  return {"app": "Sunnify", "version": "2.1.0"}

@router.get("/health")
async def health_check():
  return {"status": "ok", "version": "2.1.0"}