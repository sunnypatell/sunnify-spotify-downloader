from urllib.parse import urlparse


class UtilsYoutube:
  @staticmethod
  def extractYoutubeVideoIdFromUrl(youtubeUrl: str) -> str:
    # urlparse -> scheme://netloc/path;parameters?query#fragment
    # query: v=XXXXXX&other=YYYYY
    queryString = urlparse(youtubeUrl).query
    youtubeId = queryString.split("v=")[1].split("&")[0]
    return youtubeId
  
  @staticmethod
  def cleanYoutubeVideoUrl(youtubeUrl: str) -> str:
    youtubeId = UtilsYoutube.extractYoutubeVideoIdFromUrl(youtubeUrl)
    return f"https://www.youtube.com/watch?v={youtubeId}"