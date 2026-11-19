param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$spec = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $Folder 'voice-lines.json') | ConvertFrom-Json
$lines = @($spec.lines)
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    for ($i=0; $i -lt $lines.Count; $i++) {
        if ([string]::IsNullOrWhiteSpace($lines[$i])) { continue }
        $speaker.SetOutputToWaveFile((Join-Path $Folder ("voice-{0}.wav" -f $i)))
        $speaker.Speak([string]$lines[$i])
        $speaker.SetOutputToNull()
    }
} finally { $speaker.Dispose() }
