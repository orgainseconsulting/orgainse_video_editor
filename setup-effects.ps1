param([string]$Python)
$ErrorActionPreference='Stop'
if (-not $Python) { $Python = & (Join-Path $PSScriptRoot 'python-runtime.ps1') }
Push-Location -LiteralPath $PSScriptRoot
try {
    & $Python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)"
    if ($LASTEXITCODE) { throw 'Use 64-bit Python 3.10 to 3.12 for the pinned MediaPipe effects runtime.' }
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.git')) {
        git submodule update --init --depth 1
        if ($LASTEXITCODE) { throw 'Retrieving the pinned source projects failed.' }
    }
    $requiredSources = @('shotcraft/gallery/api/library.json', 'caption-styles/captions.js', 'video-effects/scripts/fx.py',
        'remotion-skill/examples/src/components/Layers.tsx', 'vaibhav-editor/scripts/apply_keep.py',
        'digital-samba/docs/repurposing.md', 'fframes/skills/fframes-video/SKILL.md')
    foreach ($relative in $requiredSources) {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot ('upstream/' + $relative)) -PathType Leaf)) {
            throw "Missing upstream/$relative. Extract the full Windows source release or use a recursive Git checkout."
        }
    }
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
