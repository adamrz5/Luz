[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$FilePath,
    [Parameter(Mandatory)][ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$Thumbprint,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $FilePath).Path
$certificate = Get-ChildItem Cert:/CurrentUser/My -CodeSigningCert |
    Where-Object Thumbprint -eq $Thumbprint | Select-Object -First 1
if (-not $certificate -or -not $certificate.HasPrivateKey) {
    throw 'A code-signing certificate with a private key is required in CurrentUser/My.'
}
if ($certificate.Subject -eq $certificate.Issuer -or
    $certificate.NotBefore -gt (Get-Date) -or $certificate.NotAfter -le (Get-Date)) {
    throw 'Use a current, publicly trusted certificate. Self-signed certificates cannot verify the publisher for other users.'
}
$chain = [Security.Cryptography.X509Certificates.X509Chain]::new()
try {
    if (-not $chain.Build($certificate)) {
        throw "The signing certificate is not trusted: $($chain.ChainStatus.Status -join ', ')."
    }
} finally {
    $chain.Dispose()
}

$kitDirectory = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin'
$signTool = Get-ChildItem -LiteralPath $kitDirectory -Directory |
    Sort-Object Name -Descending |
    ForEach-Object { Join-Path $_.FullName 'x64/signtool.exe' } |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $signTool) {
    throw 'Install the Windows SDK signing tools before signing a release.'
}
if ($CheckOnly) {
    Write-Output 'Signing certificate and Windows SDK validated.'
    return
}

& $signTool sign /s My /sha1 $Thumbprint /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $target
if ($LASTEXITCODE -ne 0) { throw 'Authenticode signing failed.' }
& $signTool verify /pa /all $target
if ($LASTEXITCODE -ne 0) { throw 'Authenticode verification failed.' }
$signature = Get-AuthenticodeSignature -LiteralPath $target
if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate) {
    throw 'A valid, timestamped signature is required.'
}
