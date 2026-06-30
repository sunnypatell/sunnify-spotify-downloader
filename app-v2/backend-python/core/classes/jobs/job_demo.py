import asyncio
import random
from models.new import WsBackendEventPayloadTypeMessage
from core.singleton.logger import logger
from core.singleton.websocket_event_emitter import webSocketEventEmitter
from core.classes.jobs.job import Job
    
class JobDemo:
  def createJob(self):
    logger.info("JobDemo - Creating demo job")
    
    # create job fn
    totalStep = 3
    
    def doStep():
      isError = random.random() > 0.75
      isErrorThatFailJob = random.random() > 0.5
      if isError and isErrorThatFailJob:
        return (False, "UNEXPECTED_ERROR_THAT_FAIL_JOB")
      if isError:
        return (False, "EXPECTED_ERROR_THAT_DOES_NOT_FAIL_JOB")
      return (True, None)
    
    async def jobFn(job:Job):
      # constants
      delay = 2
      # notify job start
      logger.info("JobDemo - jobFn - start")
      # do each step
      for i in range(totalStep):
        # notify step start
        logger.info(f"JobDemo - jobFn - Step {i+1}/{totalStep}: doing...")
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(
            text=f"Job \"{job.title}\" step {i+1}/{totalStep}: doing..."
          )
        )
        # do step
        await asyncio.sleep(delay)
        isSuccess, errorCode = doStep()
        
        # - if error
        if not isSuccess and errorCode == 'UNEXPECTED_ERROR_THAT_FAIL_JOB':
          raise Exception("UNEXPECTED_ERROR_THAT_FAIL_JOB")
        elif not isSuccess and errorCode == 'EXPECTED_ERROR_THAT_DOES_NOT_FAIL_JOB':
          await job.captureMessage(kind="ERROR",message="EXPECTED_ERROR_THAT_DOES_NOT_FAIL_JOB")
        # - if success
        else: 
          await job.captureMessage(kind="INFO",message=f"Step {i+1}/{totalStep} done")
        
        # increment step
        await job.incrementStepCompleted()
        # notify step done
        logger.info(f"JobDemo - jobFn - Step {i+1}/{totalStep}: done!")
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(
            text=f"Job \"{job.title}\" step {i+1}/{totalStep}: done!"
          )
        )
      # after each step done -> notify job done
      logger.info(f"JobDemo - jobFn - Job completed")
      
    # create job
    job = Job(
      title="Demo Job",
      totalStepCount=totalStep,
      jobFn=jobFn
    )
    logger.info(f"JobDemo - Job created: {job}")
    
    return job