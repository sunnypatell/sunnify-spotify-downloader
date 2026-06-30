from functools import reduce
    
class UtilsDict:
  @staticmethod
  def getNested(
    obj: dict, 
    path: str, 
    default=None
  ):
    # Trasforma "user.profile.name" o "user/profile/name" in una lista di chiavi
    keys = path.replace('[', '.').replace(']', '').split('.')
    try:
        return reduce(
          lambda d, key: d[int(key)] if isinstance(d, list) else d.get(key),
          keys,
          obj
        )
    except (AttributeError, KeyError, ValueError, IndexError):
        return default