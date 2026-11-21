[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Installer,
    [Parameter(Mandatory)][ValidatePattern('^[0-9A-Fa-f]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory)][string]$ResultsDirectory
)

$ErrorActionPreference = 'Stop'
$applicationDirectory = Join-Path $env:LOCALAPPDATA 'Programs/Luz'
$originalState = Join-Path $env:LOCALAPPDATA 'Luz'
if ((Test-Path -LiteralPath $applicationDirectory) -or (Test-Path -LiteralPath $originalState)) {
    throw 'Use a disposable Windows account with no existing Luz installation or data.'
}
# Inno Setup can reuse a previous installation's custom directory.
$uninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Luz.adamrz5_is1'
foreach ($view in 'Registry64', 'Registry32') {
    $currentUser = [Microsoft.Win32.RegistryKey]::OpenBaseKey('CurrentUser', $view)
    try {
        $existingInstallation = $currentUser.OpenSubKey($uninstallKey)
        if ($null -ne $existingInstallation) {
            $existingInstallation.Dispose()
            throw 'Use a disposable Windows account with no existing Luz installation or data.'
        }
    } finally {
        $currentUser.Dispose()
    }
}
New-Item -ItemType Directory -Path $ResultsDirectory -Force | Out-Null
$report = [ordered]@{
    Windows = [Environment]::OSVersion.VersionString
    PythonCommandFound = [bool](Get-Command python.exe, py.exe -ErrorAction SilentlyContinue)
    ChecksumVerified = $false
    Installed = $false
    WindowOpened = $false
    Uninstalled = $false
    Error = $null
}
$process = $null
$state = Join-Path $env:TEMP ('luz-installer-test-' + [guid]::NewGuid())
$previousState = $env:LUZ_STATE_DIR
$previousPath = $env:PATH
try {
    if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash -ne $ExpectedSha256) {
        throw 'Installer checksum does not match the build output.'
    }
    $report.ChecksumVerified = $true
    $setup = Start-Process -FilePath $Installer -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-' -PassThru
    if (-not $setup.WaitForExit(120000) -or $setup.ExitCode -ne 0) {
        throw 'The installer failed or exceeded its time limit.'
    }
    $application = Join-Path $applicationDirectory 'Luz.exe'
    if (-not (Test-Path -LiteralPath $application)) { throw 'Installed application is missing.' }
    $report.Installed = $true
    $env:LUZ_STATE_DIR = $state
    $env:PATH = (Join-Path $env:WINDIR 'System32') + ';' + $env:WINDIR
    $process = Start-Process -FilePath $application -ArgumentList '--sin-bandeja' -PassThru
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 200
        $process.Refresh()
        if ($process.HasExited) { throw 'The installed application exited before opening a window.' }
    } until (($process.MainWindowHandle -ne 0 -and $process.MainWindowTitle -eq "Luz") -or (Get-Date) -ge $deadline)
    if ($process.MainWindowHandle -eq 0 -or $process.MainWindowTitle -ne "Luz") { throw 'The installed application did not open a window.' }
    $report.WindowOpened = $true
    Start-Sleep -Seconds 2
    [void]$process.CloseMainWindow()
    if (-not $process.WaitForExit(10000) -or $process.ExitCode -ne 0) {
        throw 'The installed application did not close normally.'
    }
    $uninstaller = Join-Path $applicationDirectory 'unins000.exe'
    $remove = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -PassThru
    if (-not $remove.WaitForExit(60000) -or $remove.ExitCode -ne 0) { throw 'Uninstallation failed.' }
    $report.Uninstalled = -not (Test-Path -LiteralPath $application)
    if (-not $report.Uninstalled) { throw 'Application remains after uninstallation.' }
} catch {
    $report.Error = $_.Exception.Message
    throw
} finally {
    if ($process -and -not $process.HasExited) { $process.Kill() }
    $env:LUZ_STATE_DIR = $previousState
    $env:PATH = $previousPath
    $report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ResultsDirectory 'installer-test.json') -Encoding UTF8
}
