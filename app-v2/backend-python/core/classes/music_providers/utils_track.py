class UtilsTrack:
  @staticmethod
  def convertDurationMsToMMSS(durationMs: int) -> str:
    seconds = durationMs / 1000
    mm = int(seconds // 60)
    ss = int(seconds % 60)
    return f"{mm:02d}:{ss:02d}"