import asyncio
from typing import Callable, Awaitable, Literal
from core.singleton.logger import logger

class Job:
  """Job Definition Object"""
  def __init__(
    self, 
    title: str, 
    totalStepCount: int,
    jobFn: Callable[["Job"], Awaitable[None]]
  ):
    self.task: asyncio.Task | None = None
    self.title: str = title
    self.stepsTotal: int = totalStepCount
    self.stepsCompleted: int | None = None
    self.jobFn: Callable[["Job"], Awaitable[None]] = jobFn
    self.isCanceled: bool = False
    self.isErrored: bool = False
    self.error: Exception | None = None
    self.messages: list[str] = []
    self.callback_beforeJobStart: Callable[["Job"], None] | None = None
    self.callback_afterIncrementStep: Callable[["Job"], None] | None = None
    self.callback_afterJobCompleted: Callable[["Job"], None] | None = None
    self.callback_afterJobCanceled: Callable[["Job"], None] | None = None
    self.callback_afterJobErrored: Callable[["Job"], None] | None = None
    
  # prepare job
  
  def setCallback_beforeJobStart(self, callback: Callable[["Job"], None] | None):
    self.callback_beforeJobStart = callback
    
  def setCallback_afterIncrementStep(self, callback: Callable[["Job"], None] | None):
    self.callback_afterIncrementStep = callback
    
  def setCallback_afterJobCompleted(self, callback: Callable[["Job"], None] | None):
    self.callback_afterJobCompleted = callback
    
  def setCallback_afterJobCanceled(self, callback: Callable[["Job"], None] | None):
    self.callback_afterJobCanceled = callback
    
  def setCallback_afterJobErrored(self, callback: Callable[["Job"], None] | None):
    self.callback_afterJobErrored = callback
    
  # get job state
  
  def getExecutionStatus(self):
    if self.isCanceled: return "CANCELED"
    if self.isErrored: return "ERRORED"
    if self.stepsCompleted is None: return "WAITING_START"
    if self.stepsCompleted >= 0 and self.stepsCompleted < self.stepsTotal: return "RUNNING"
    return "COMPLETED"
  
  def getProgress(self):
    status = self.getExecutionStatus()
    if status == "WAITING_START": return 0
    if status == "COMPLETED": return 1
    return ((self.stepsCompleted or 0) / self.stepsTotal)
  
  # run job fn / create task
  
  def scheduleJob(self):
    self.stepsCompleted = 0
    self.isCanceled = False
    self.isErrored = False
    self.messages = []
    self.task = asyncio.create_task(self.runJobFn())
    
  async def runJobFn(self):
    try:
      if self.callback_beforeJobStart:
        self.callback_beforeJobStart(self)
      await asyncio.sleep(0.05)
      await self.jobFn(self)
      await asyncio.sleep(0.05)
      if self.callback_afterJobCompleted:
        self.callback_afterJobCompleted(self)
    except Exception as e:
      self.onJobErrored(e)
  
  def cancelExecution(self):
    if not self.task: return
    self.task.cancel()
    self.task = None
    self.isCanceled = True
    self.messages.append("CANCELED BY USER")
    if self.callback_afterJobCanceled:
      self.callback_afterJobCanceled(self)
  
  # utils used by jobFn
  
  async def incrementStepCompleted(self):
    if self.stepsCompleted is None:
      self.stepsCompleted = 0
    self.stepsCompleted += 1
    await asyncio.sleep(0.1)
    if self.callback_afterIncrementStep:
      self.callback_afterIncrementStep(self)
      
  async def captureMessage(self, kind: Literal["ERROR","INFO"], message: str):
    """Lifecycle Action - call this to signal a message"""
    self.messages.append(f"{kind}: {message}")
    
  def raiseError(self, name: str):
    """Lifecycle Action - call this to raise an error that will fail the job"""
    raise Exception(name)
  
  # job callback
  
  def onJobErrored(self, error: Exception):
    logger.error(f"Job {self.title} - exception raised from jobFn: {error}")
    self.isErrored = True
    self.error = error
    self.messages.append(str(f"ERROR: {error}"))
    if self.callback_afterJobErrored:
      self.callback_afterJobErrored(self)
    
  
    
  
  