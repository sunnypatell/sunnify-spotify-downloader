"""External tools Sunnify drives: FFmpeg, a JavaScript runtime, YouTube cookies."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile


def ffmpeg_install_hint() -> str:
    """The one-line install command for the platform we're running on."""
    if sys.platform == "win32":
        return "winget install Gyan.FFmpeg  (or: choco install ffmpeg)"
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    return "sudo apt install ffmpeg"


def get_ffmpeg_path():
    """Get path to FFmpeg - checks bundled first, then system paths."""
    # Check bundled FFmpeg first (for PyInstaller builds)
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", "")
        if sys.platform == "win32":
            ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg.exe")
        else:
            ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg")
        if os.path.exists(ffmpeg):
            return os.path.join(base_path, "ffmpeg")

    # Check common system paths (for homebrew/system installs)
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    common_paths = [
        "/opt/homebrew/bin",  # macOS ARM homebrew
        "/usr/local/bin",  # macOS Intel homebrew / Linux
        "/usr/bin",  # Linux system
    ]
    if sys.platform == "win32":
        # package managers put these on PATH, so shutil.which below usually
        # wins first; these cover the install-then-same-shell case, and are
        # read from each tool's own env var so a relocated install still hits
        choco = os.environ.get("CHOCOLATEYINSTALL") or r"C:\ProgramData\chocolatey"
        scoop = os.environ.get("SCOOP") or os.path.join(os.path.expanduser("~"), "scoop")
        common_paths += [
            os.path.join(choco, "bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
            os.path.join(scoop, "shims"),
            r"C:\ffmpeg\bin",  # the unzip convention, the one that never lands on PATH
        ]

    for path in common_paths:
        ffmpeg = os.path.join(path, ffmpeg_name)
        if os.path.exists(ffmpeg):
            return path

    # Check if ffmpeg is in PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return os.path.dirname(ffmpeg_in_path)

    # On Windows, check user/machine environment in case PATH was modified recently
    if sys.platform == "win32":
        with contextlib.suppress(ImportError):
            import winreg

            for hkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                sub = (
                    r"Environment"
                    if hkey == winreg.HKEY_CURRENT_USER
                    else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
                )
                try:
                    with winreg.OpenKey(hkey, sub) as key:
                        val, _ = winreg.QueryValueEx(key, "PATH")
                        for p in val.split(os.pathsep) if isinstance(val, str) else ():
                            expanded = os.path.expandvars(p.strip())
                            if expanded and os.path.exists(os.path.join(expanded, "ffmpeg.exe")):
                                return expanded
                except OSError:
                    continue

    return None


# yt-dlp's own preference order; deno's runtime only gets fixes until about october 2027
_JS_RUNTIMES = ("deno", "node")


def _js_runtime_candidates(name: str) -> list[str]:
    """PATH first, then the usual install spots, since a Finder-launched app gets a bare PATH."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    home = os.path.expanduser("~")
    candidates = [shutil.which(name)]
    if name == "deno":
        candidates.append(os.path.join(home, ".deno", "bin", exe))
    if sys.platform == "win32":
        scoop = os.environ.get("SCOOP") or os.path.join(home, "scoop")
        choco = os.environ.get("CHOCOLATEYINSTALL") or r"C:\ProgramData\chocolatey"
        candidates += [
            os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Links\{exe}"),
            os.path.join(scoop, "shims", exe),
            os.path.join(choco, "bin", exe),
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "nodejs", exe),
        ]
    else:
        candidates += [f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"]
    return [c for c in dict.fromkeys(candidates) if c and os.path.isfile(c)]


def find_js_runtime() -> tuple[str, str] | None:
    """(name, path) of a javascript runtime yt-dlp supports, which a logged-in youtube
    session needs for its challenge solver. yt-dlp judges the version, so this never
    accepts a runtime yt-dlp would then refuse."""
    from yt_dlp.globals import supported_js_runtimes

    for name in _JS_RUNTIMES:
        runtime = supported_js_runtimes.value.get(name)
        for path in _js_runtime_candidates(name) if runtime else ():
            info = runtime(path=path).info
            if info and info.supported:
                return name, path
    return None


def _read_cookie_jar(path: str):
    """Load a cookies.txt without yt-dlp echoing malformed lines (cookie values) to stderr."""
    from yt_dlp.cookies import YoutubeDLCookieJar

    jar = YoutubeDLCookieJar(path)
    with contextlib.redirect_stderr(io.StringIO()):
        jar.load()
    return jar


def _cookies_text(path: str) -> str:
    """The file's valid cookies, re-serialized for yt-dlp's private copies."""
    jar = _read_cookie_jar(path)
    fd, tmp = tempfile.mkstemp(prefix="sunnify-cookies-", suffix=".txt")
    os.close(fd)
    try:
        jar.save(tmp)
        with open(tmp, encoding="utf-8") as f:
            return f.read()
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp)


def cookies_problem(path: str) -> tuple[str, str] | None:
    """(error code, message) when a youtube cookies file can't be used, else None."""
    if not os.path.isfile(path):
        return "cookies_unusable", f"cookies file not found: {path}"
    try:
        jar = _read_cookie_jar(path)
    except Exception:
        return "cookies_unusable", f"not a netscape cookies.txt file: {path}"
    if not any(
        c.domain.lstrip(".") == "youtube.com" or c.domain.endswith(".youtube.com") for c in jar
    ):
        return "cookies_unusable", f"no youtube.com cookies in {path}"
    if find_js_runtime() is None:
        return (
            "deno_missing",
            "no supported javascript runtime (deno, or node 22+); youtube needs one with cookies",
        )
    return None
