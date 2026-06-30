from __future__ import annotations

from fastapi import APIRouter
from core.singleton.logger import logger
from core.singleton.jobs_executor import jobsExecutor
from core.classes.jobs.job_demo import JobDemo

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/job-demo/start", response_model=bool)
async def jobDemo_start():
  logger.info("/job/job-demo/start - Starting demo job")
  # create job
  jobDemo = JobDemo()
  job = jobDemo.createJob()
  # schedule job
  jobsExecutor.setAndStartNewJob(job)
  # reply
  logger.info("/job/job-demo/start - Demo job schduled and started")
  logger.info("/job/job-demo/start - Reply HTTP")
  return True
