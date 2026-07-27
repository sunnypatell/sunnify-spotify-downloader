# Sunnify installer (Windows) - safe to pipe: iwr -useb <raw-url> | iex
#
# Design rules (AI agents drive this):
#   - zero prompts, zero UAC: user-scope install dir + HKCU PATH only
#   - the exe comes from GitHub release assets, SHA256-verified against the
#     release's checksums.txt before anything is installed
#   - idempotent: re-running replaces the previous install
$ErrorActionPreference = "Stop"

$repo = "sunnypatell/sunnify-spotify-downloader"
$base = "https://github.com/$repo/releases/latest/download"
$asset = "Sunnify-Windows.exe"
$destDir = Join-Path $env:LOCALAPPDATA "Sunnify"

Write-Host "downloading $asset (latest release)..."
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$tmp = Join-Path $env:TEMP "sunnify-install-$PID"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
    Invoke-WebRequest -UseBasicParsing -Uri "$base/$asset" -OutFile (Join-Path $tmp $asset)
    Invoke-WebRequest -UseBasicParsing -Uri "$base/checksums.txt" -OutFile (Join-Path $tmp "checksums.txt")

    $expectedLine = Select-String -Path (Join-Path $tmp "checksums.txt") -Pattern ([regex]::Escape($asset) + "$") | Select-Object -First 1
    if (-not $expectedLine) { throw "checksums.txt has no entry for $asset" }
    $expected = ($expectedLine.Line -split "\s+")[0].ToLower()
    $actual = (Get-FileHash -Algorithm SHA256 (Join-Path $tmp $asset)).Hash.ToLower()
    if ($actual -ne $expected) { throw "SHA256 mismatch for $asset (got $actual, want $expected)" }
    Write-Host "checksum verified"

    # `sunnify.exe` on PATH: same binary as the GUI (no arguments opens the app)
    Move-Item -Force (Join-Path $tmp $asset) (Join-Path $destDir "sunnify.exe")
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

# user-scope PATH (HKCU), no elevation; new shells pick it up automatically
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $destDir) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$destDir", "User")
    Write-Host "added $destDir to your user PATH (new shells only)"
}
if (($env:Path -split ";") -notcontains $destDir) {
    $env:Path = "$env:Path;$destDir"
}

Write-Host ""
Write-Host "installed: $destDir\sunnify.exe"
Write-Host "try: sunnify --help   (tip: pipe output, e.g. `sunnify doctor | Out-Default`, so the shell waits)"
