from __future__ import annotations
from typing import Literal

from fastapi import APIRouter, HTTPException
from models.new import Settings, SettingsMutable
from core.singleton.user_config_api import userConfigReaderApi

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/", response_model=Settings)
async def getSettings():
  """Get settings from user config"""
  return userConfigReaderApi.getSettings()

@router.put("/", response_model=Literal[True])
async def updateSettings(settingsMutable: SettingsMutable):
  """Update settings in user config"""
  updated = userConfigReaderApi.updateSettings(
    newSettingsMutable=settingsMutable
  )
  if not updated:
    raise HTTPException(status_code=500, detail="Failed to update settings")
  return True