import asyncio
from models.new import WsBackendEventPayloadTypeMessage, WsBackendEventPayloadTypeJobProgress
from core.singleton.logger import logger
from core.singleton.websocket_event_emitter import webSocketEventEmitter
from core.classes.jobs.job import Job
from core.classes.utils.utils_time import UtilsTime

class JobsExecutor:
  """In-Memory Job Executor. Used to execute jobs and share the current job state between threads and python functions"""
  job: None | Job = None
  
  def getCurrentJob(self):
    return self.job
  
  # main api
  
  def setAndStartNewJob(self, job: Job):
    # cancel existing job (if any)
    runningJob = self.getCurrentJob()
    if runningJob and runningJob.getExecutionStatus() == "RUNNING":
      logger.info("JobsExecutor - setAndStartNewJob - canceling existing job")
      runningJob.cancelExecution()
    # set new job and start
    self.job = job
    self.job.setCallback_beforeJobStart(self.onBeforeJobStart)
    self.job.setCallback_afterIncrementStep(self.onAfterIncrementStep)
    self.job.setCallback_afterJobCompleted(self.onAfterJobCompleted)
    self.job.setCallback_afterJobCanceled(self.onAfterJobCanceled)
    self.job.setCallback_afterJobErrored(self.onAfterJobErrored)
    self.job.scheduleJob()
    
  # lifecycle callbacks
    
  def onBeforeJobStart(self, job: Job):
    logger.info(f"JobsExecutor - onBeforeJobStart - Job {job.title} started")
    self.notifyJobStarted(job)
    self.notifyJobProgress()
    
  def onAfterIncrementStep(self, job: Job):
    logger.info(f"JobsExecutor - onAfterIncrementStep - Job {job.title} step {job.stepsCompleted}/{job.stepsTotal} completed")
    self.notifyJobProgress()
    
  def onAfterJobCompleted(self, job: Job):
    logger.info(f"JobsExecutor - onAfterJobDone - Job {job.title} completed")
    self.notifyJobCompleted(job)
    self.notifyJobProgress()
    # self.job = None
    
  def onAfterJobCanceled(self, job: Job):
    logger.info(f"JobsExecutor - onAfterJobCanceled - Job {job.title} canceled")
    self.notifyJobCanceled(job)
    self.notifyJobProgress()
    # self.job = None
    
  def onAfterJobErrored(self, job: Job):
    logger.info(f"JobsExecutor - onAfterJobErrored - Job {job.title} errored")
    self.notifyJobErrored(job)
    self.notifyJobProgress()
    # self.job = None
    
  # notifications
  
  def notifyJobStarted(self, job: Job):
    asyncio.create_task(
      webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeMessage(
          text=f"Job \"{job.title}\" started",
        )
      )
    )
  
  def notifyJobCompleted(self, job: Job):
    asyncio.create_task(
      webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeMessage(
          text=f"Job \"{job.title}\" completed",
          severity="SUCCESS"
        )
      )
    )
  
  def notifyJobCanceled(self, job: Job):
    asyncio.create_task(
      webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeMessage(
          text=f"Job \"{job.title}\" canceled",
          severity="WARNING"
        )
      )
    )
  
  def notifyJobErrored(self, job: Job):
    asyncio.create_task(
      webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeMessage(
          text=f"Job \"{job.title}\" errored.\nERROR\n{job.error}",
          severity="ERROR"
        )
      )
    )
  
  def notifyJobProgress(self):
    if not self.job:
      asyncio.create_task(
        webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeJobProgress(
            dateTimeISO=UtilsTime.getCurrentDateTimeIso(),
            jobs=[]
          )
        )
      )
      return
    
    asyncio.create_task(
      webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeJobProgress(
          dateTimeISO=UtilsTime.getCurrentDateTimeIso(),
          jobs=[
            {
              "title": self.job.title,
              "executionStatus": self.job.getExecutionStatus(),
              "stepsTotal": self.job.stepsTotal,
              "stepsCompleted": self.job.stepsCompleted or 0,
              "progress": self.job.getProgress(),
              "messages": self.job.messages,
            }
          ]
        )
      )
    )