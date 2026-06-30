import datetime
from typing import TypedDict

class UtilsTime:
  @staticmethod
  def getCurrentDateTimeIso():
    """Return current date and time in ISO format (2020-01-01T00:00:00.000Z)"""
    return datetime.datetime.now().isoformat()
  
  @staticmethod
  def formatDurationInSecondsToMMSS(durationInSeconds: float):
    """Return duration in seconds as a string in the format "mm:ss"."""
    mm = int(durationInSeconds // 60)
    ss = int(durationInSeconds % 60)
    return f"{mm:02d}:{ss:02d}"


class UtilsTimeExecutionTimer:
  _type_Output = TypedDict('_type_Output', {
    'fullMs': float,
    'str_ss': str,
    'str_mmss': str
  })
  startTime: datetime.datetime | None = None
  def __init__(self):
    self.startTime = datetime.datetime.now()
  def end(self):
    if not self.startTime: raise Exception("Execution timer not started")
    delta = datetime.datetime.now() - self.startTime
    output = self._type_Output({
      "fullMs": float(delta.total_seconds() * 1000),
      "str_ss": f"{delta.total_seconds():.6f}",
      "str_mmss": UtilsTime.formatDurationInSecondsToMMSS(delta.total_seconds()),
    })
    return output