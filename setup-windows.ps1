param([switch]$RenderOnly, [switch]$ProductionExtras)
$ErrorActionPreference='Stop'
$toolsRoot=Join-Path $PSScriptRoot '.local'
$downloadRoot=Join-Path $toolsRoot 'downloads'
$binaryRoot=Join-Path $toolsRoot 'bin'
$modelRoot=Join-Path $toolsRoot 'models'
New-Item -ItemType Directory -Force -Path $downloadRoot,$binaryRoot,$modelRoot | Out-Null

function Get-VerifiedFile([string]$Url,[string]$Path,[string]$Digest) {
    if ((Test-Path -LiteralPath $Path) -and (Get-FileHash -LiteralPath $Path).Hash -eq $Digest) { return }
    $part=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.part'
    try {
        curl.exe --fail --show-error --location --retry 2 --output $part $Url
        if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath $part).Hash -ne $Digest) { throw "Download failed verification: $Url" }
        Move-Item -Force -LiteralPath $part -Destination $Path
    } finally { if(Test-Path -LiteralPath $part){ Remove-Item -LiteralPath $part } }
}
if (-not ((Test-Path -LiteralPath (Join-Path $binaryRoot 'ffmpeg.exe')) -and (Test-Path -LiteralPath (Join-Path $binaryRoot 'ffprobe.exe')))) {
    $url='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    $digest=((Invoke-RestMethod -Uri ($url+'.sha256')) -split '\s+')[0]
    if ($digest -notmatch '^[a-fA-F0-9]{64}$') { throw 'Invalid FFmpeg publisher checksum.' }
    $archive=Join-Path $downloadRoot 'ffmpeg.zip'
    Get-VerifiedFile $url $archive $digest
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach($entry in $zip.Entries) {
            if($entry.Name -in @('ffmpeg.exe','ffprobe.exe')) { [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,(Join-Path $binaryRoot $entry.Name),$true) }
        }
    } finally { $zip.Dispose() }
}
$whisperDir=Join-Path $toolsRoot 'whisper'
if (-not (Get-ChildItem -LiteralPath $whisperDir -Recurse -Filter whisper-cli.exe -ErrorAction SilentlyContinue)) {
    $archive=Join-Path $downloadRoot 'whisper.zip'
    Get-VerifiedFile 'https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip' $archive '6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb'
    Expand-Archive -LiteralPath $archive -DestinationPath $whisperDir -Force
}
Get-VerifiedFile 'https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-tiny.bin' (Join-Path $modelRoot 'ggml-tiny.bin') 'be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21'
if ($ProductionExtras) {
    $studioPython = & (Join-Path $PSScriptRoot 'python-runtime.ps1')
    & (Join-Path $PSScriptRoot 'setup-vision.ps1') -Python $studioPython
    & (Join-Path $PSScriptRoot 'setup-effects.ps1') -Python $studioPython
    $bundledNode = Join-Path (Split-Path (Split-Path $studioPython -Parent) -Parent) 'node\node_modules\playwright-core\package.json'
    if (-not (Test-Path -LiteralPath $bundledNode)) {
        $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $npm) { throw 'Install Node.js with npm for multi-section website capture, then rerun -ProductionExtras.' }
        & $npm.Source install --prefix (Join-Path $toolsRoot 'web-capture') --no-audit --no-fund --ignore-scripts playwright-core@1.55.0
        if ($LASTEXITCODE) { throw 'Multi-section website capture setup failed.' }
    }
}
if ($RenderOnly) { Write-Host 'Template editing, rendering and transcription are ready.'; return }

$ollamaCmd=Get-Command ollama.exe -ErrorAction SilentlyContinue
$ollamaExe=if($ollamaCmd){$ollamaCmd.Source}else{Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'}
if (-not (Test-Path -LiteralPath $ollamaExe)) {
    winget install --exact --id Ollama.Ollama --source winget --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ollamaExe)) { throw 'Ollama install did not complete. Install from ollama.com and rerun setup.' }
}
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD='1'
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null }
catch {
    Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden
    for ($i=0;$i -lt 30;$i++) {
        Start-Sleep -Seconds 1
        try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; break } catch {}
    }
}
$weightName='qwen2.5-1.5b-instruct-q4_k_m.gguf'
Get-VerifiedFile ('https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/'+$weightName) (Join-Path $modelRoot $weightName) '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'
$modelDefinition=Join-Path $modelRoot 'Modelfile'
[IO.File]::WriteAllText($modelDefinition,("FROM ./"+$weightName+[Environment]::NewLine+"PARAMETER num_ctx 4096"+[Environment]::NewLine))
Push-Location -LiteralPath $modelRoot
try { & $ollamaExe create 'orgainse-editor:1.5b' -f $modelDefinition; if ($LASTEXITCODE -ne 0) { throw 'Local model registration failed.' } } finally { Pop-Location }
Write-Host 'Ready. Double-click Start Studio.cmd.'
