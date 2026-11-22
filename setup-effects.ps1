param([string]$Python)
$ErrorActionPreference='Stop'
if (-not $Python) { $Python = & (Join-Path $PSScriptRoot 'python-runtime.ps1') }
Push-Location -LiteralPath $PSScriptRoot
try {
    & $Python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)"
    if ($LASTEXITCODE) { throw 'Use 64-bit Python 3.10 to 3.12 for the pinned MediaPipe effects runtime.' }
    git submodule update --init --depth 1
    if ($LASTEXITCODE) { throw 'Retrieving the pinned source projects failed.' }
    & $Python -m pip install --disable-pip-version-check --only-binary=:all: --upgrade --target .local/effects-python mediapipe==0.10.21 Pillow==11.3.0
    if ($LASTEXITCODE) { throw 'The local person tracking and effects packages could not be installed.' }
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    $bundledPnpm = Join-Path (Split-Path (Split-Path $node)) 'node_modules\pnpm\bin\pnpm.cjs'
    Push-Location motion
    try {
        if ($pnpm) { & $pnpm.Source install --frozen-lockfile --ignore-scripts }
        elseif (Test-Path -LiteralPath $bundledPnpm) { & $node $bundledPnpm install --frozen-lockfile --ignore-scripts }
        else { & npm.cmd install --no-audit --no-fund --ignore-scripts }
        if ($LASTEXITCODE) { throw 'Installing the local animation libraries failed.' }
        & $node build.cjs
        if ($LASTEXITCODE) { throw 'Building the Shotcraft and studio compositions failed.' }
    } finally { Pop-Location }
    Write-Host 'The effects, caption and motion renderers are ready.'
} finally { Pop-Location }
