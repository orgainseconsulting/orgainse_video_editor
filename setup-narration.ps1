param([string]$Python)
$ErrorActionPreference = 'Stop'
if (-not $Python) { $Python = & (Join-Path $PSScriptRoot 'python-runtime.ps1') }
. (Join-Path $PSScriptRoot 'verified-download.ps1')
$modelDir = Join-Path $PSScriptRoot '.local/kokoro'
$packages = Join-Path $PSScriptRoot '.local/narration-python'
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
$release = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1'
Get-VerifiedFile "$release/kokoro-v1.0.onnx" (Join-Path $modelDir 'kokoro-v1.0.onnx') 'beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a'
Get-VerifiedFile "$release/voices-v1.0.bin" (Join-Path $modelDir 'voices-v1.0.bin') 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'
& $Python -m pip install --disable-pip-version-check --upgrade --target $packages kokoro-onnx==0.6.1
if ($LASTEXITCODE) { throw 'Local British narration packages could not be installed.' }
$node = (Get-Command node.exe -ErrorAction Stop).Source
$pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
$bundledPnpm = Join-Path (Split-Path (Split-Path $node)) 'node_modules/pnpm/bin/pnpm.cjs'
Push-Location (Join-Path $PSScriptRoot 'narration')
try {
    $store = Join-Path $PSScriptRoot '.local/pnpm-store'
    if ($pnpm) { & $pnpm.Source install --frozen-lockfile --ignore-scripts --store-dir $store }
    elseif (Test-Path -LiteralPath $bundledPnpm) { & $node $bundledPnpm install --frozen-lockfile --ignore-scripts --store-dir $store }
    else { & npm.cmd install --no-audit --no-fund --ignore-scripts }
    if ($LASTEXITCODE) { throw 'Installing the local grammar checker failed.' }
} finally { Pop-Location }
Write-Host 'British neural narration and local English proofreading are ready.'
