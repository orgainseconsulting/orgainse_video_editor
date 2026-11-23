function Get-VerifiedFile([string]$Url,[string]$Path,[string]$Digest) {
    if ((Test-Path -LiteralPath $Path) -and (Get-FileHash -LiteralPath $Path).Hash -eq $Digest) { return }
    $part=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.part'
    try {
        curl.exe --fail --show-error --location --retry 2 --output $part $Url
        if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath $part).Hash -ne $Digest) { throw "Download failed verification: $Url" }
        Move-Item -Force -LiteralPath $part -Destination $Path
    } finally { if(Test-Path -LiteralPath $part){ Remove-Item -LiteralPath $part } }
}
