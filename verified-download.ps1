function Get-StudioSha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
        finally { $sha.Dispose() }
    } finally { $stream.Dispose() }
}

function Get-VerifiedFile([string]$Url,[string]$Path,[string]$Digest) {
    if ((Test-Path -LiteralPath $Path) -and (Get-StudioSha256 $Path) -eq $Digest) { return }
    $part=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.part'
    try {
        curl.exe --fail --show-error --location --retry 2 --output $part $Url
        if ($LASTEXITCODE -ne 0 -or (Get-StudioSha256 $part) -ne $Digest) { throw "Download failed verification: $Url" }
        Move-Item -Force -LiteralPath $part -Destination $Path
    } finally { if(Test-Path -LiteralPath $part){ Remove-Item -LiteralPath $part } }
}
