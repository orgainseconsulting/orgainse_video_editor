param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$studioUrl = "http://127.0.0.1:$Port"
try {
    $active = Invoke-RestMethod -Uri "$studioUrl/api/status" -TimeoutSec 4
    if ($null -ne $active.ffmpeg -and $null -ne $active.planner) {
        if (-not $NoBrowser) { Start-Process $studioUrl }
        Write-Host "ORGAINSE is running at $studioUrl"
        exit 0
    }
} catch { }
$pythonBin = & (Join-Path $PSScriptRoot 'python-runtime.ps1')
$extra = @()
if (-not $NoBrowser) { $extra += '--open' }
& $pythonBin -B (Join-Path $PSScriptRoot 'studio.py') --port $Port @extra
exit $LASTEXITCODE
