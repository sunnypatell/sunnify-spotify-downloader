from fastapi import APIRouter
from models.new import ApiRouteUtilDiskRevealInFinderPayload
from core.singleton.logger import logger
from core.classes.utils.utils_disk import UtilsDisk

router = APIRouter(prefix="/utils",tags=["utils"])

@router.post("/disk/reveal-in-finder")
async def disk_revealInFinder(payload: ApiRouteUtilDiskRevealInFinderPayload):
  UtilsDisk.revealInFinder(dirOrFilePath=payload.path)
  return True
