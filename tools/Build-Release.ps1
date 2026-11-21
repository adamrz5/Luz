[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+(\.\d+)?$')][string]$Version,
    [ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$source = Get-Content -LiteralPath (Join-Path $root 'src/Diagnostico.py') -Raw
$sourceVersion = [regex]::Match($source, '(?m)^LUZ_VERSION\s*=\s*"(\d+\.\d+\.\d+(?:\.\d+)?)"[ \t]*\r?$').Groups[1].Value
if (-not $sourceVersion) { throw 'Could not determine LUZ_VERSION from src/Diagnostico.py.' }
if ($Version -and $Version -ne $sourceVersion) {
    throw "Requested installer version $Version differs from the application version $sourceVersion."
}
$Version = $sourceVersion
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
}
$compiler = @(
    (Join-Path $env:LOCALAPPDATA 'Programs/Inno Setup 6/ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$signScript = Join-Path $PSScriptRoot 'Sign-Release.ps1'
$dist = Join-Path $root 'build/ensayo'
$output = Join-Path $root 'build/distribucion'
if (-not $compiler) {
    throw 'Create .venv from requirements.txt and install Inno Setup 6 for the current user.'
}
if ($CertificateThumbprint) {
    & $signScript -FilePath (Join-Path $root 'build/Luz.iss') -Thumbprint $CertificateThumbprint -CheckOnly
}

Push-Location -LiteralPath $root
try {
    & $python -B tests/ejecutar-seguras.py
    if ($LASTEXITCODE -ne 0) { throw 'The safe test suite failed.' }
    & $python -m PyInstaller --noconfirm build/Luz.spec --distpath $dist --workpath build/cache
    if ($LASTEXITCODE -ne 0) { throw 'Application packaging failed.' }
    $application = Join-Path $dist 'app/Luz.exe'
    & $python -B tests/comprobar-luz.py $application
    if ($LASTEXITCODE -ne 0) { throw 'The packaged application did not start.' }

    $compilerArguments = @('/Qp', "/DLuzVersion=$Version", "/DLuzSource=$dist\app", "/O$output")
    if ($CertificateThumbprint) {
        & $signScript -FilePath $application -Thumbprint $CertificateThumbprint
        $shell = (Get-Process -Id $PID).Path
        $signCommand = '$q' + $shell + '$q -NoProfile -NonInteractive -File $q' +
            $signScript + '$q -FilePath $f -Thumbprint ' + $CertificateThumbprint
        $compilerArguments += '/DLuzSign'
        $compilerArguments += '/Sluz=' + $signCommand
    }
    & $compiler @compilerArguments build/Luz.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer packaging or signing failed.' }

    $installer = Join-Path $output 'Luz-instalador.exe'
    if ($CertificateThumbprint -and (Get-AuthenticodeSignature -LiteralPath $installer).Status -ne 'Valid') {
        throw 'Installer signature verification failed.'
    }
    $hash = Get-FileHash -LiteralPath $installer -Algorithm SHA256
    $checksum = $hash.Hash.ToLowerInvariant() + '  Luz-instalador.exe'
    Set-Content -LiteralPath (Join-Path $output 'SHA256SUMS.txt') -Value $checksum -Encoding ascii
    Write-Output "Installer created at $installer"
    if (-not $CertificateThumbprint) {
        Write-Warning 'This build is unsigned. Windows may show an unknown publisher or SmartScreen warning.'
    }
} finally {
    Pop-Location
}
