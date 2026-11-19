param([string]$Python)
$ErrorActionPreference='Stop'
if (-not $Python) { $Python = & (Join-Path $PSScriptRoot 'python-runtime.ps1') }
& $Python -m pip install --disable-pip-version-check --only-binary=:all: --target (Join-Path $PSScriptRoot '.local\vision') opencv-python-headless==4.12.0.88 numpy==2.2.6
if ($LASTEXITCODE) { throw 'Face framing installation failed for this Python runtime.' }
