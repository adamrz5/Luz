param(
    [Parameter(Mandatory)][string]$Scratch
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

Add-Type -TypeDefinition @"
using System;
using Microsoft.Win32;

public class MockRegistry : IDisposable {
    public static RegistryView PresentIn;
    private RegistryView view;

    public static MockRegistry OpenBaseKey(RegistryHive hive, RegistryView view) {
        if (hive != RegistryHive.CurrentUser) throw new Exception("Unexpected registry hive");
        return new MockRegistry { view = view };
    }

    public MockRegistry OpenSubKey(string path) {
        if (path != @"Software\Microsoft\Windows\CurrentVersion\Uninstall\Luz.adamrz5_is1")
            throw new Exception("Unexpected uninstall path: " + path);
        return view == PresentIn ? this : null;
    }

    public void Dispose() {}
}
"@

$env:LOCALAPPDATA = $Scratch
$source = Get-Content -Raw -LiteralPath (Join-Path $root 'tools/Test-Installer.ps1')
$isolatedSource = $source.Replace('[Microsoft.Win32.RegistryKey]', '[MockRegistry]')
if ($isolatedSource -eq $source) { throw 'Registry mock could not be installed.' }
$testInstaller = [scriptblock]::Create($isolatedSource)
function Test-Path { return $false }
function Get-FileHash { [pscustomobject]@{ Hash = '0' * 64 } }
function Start-Process { throw 'Called Start-Process despite existing custom installation.' }

foreach ($view in 'Registry64', 'Registry32') {
    [MockRegistry]::PresentIn = $view
    try {
        & $testInstaller -Installer 'never-launched.exe' -ExpectedSha256 ('0' * 64) -ResultsDirectory $Scratch
        throw 'Expected an existing installation to be rejected.'
    } catch {
        if ($_.Exception.Message -notlike '*disposable Windows account*') { throw }
    }
}

$tools = Join-Path $Scratch 'tools'
$src = Join-Path $Scratch 'src'
New-Item -ItemType Directory -Path $tools, $src | Out-Null
$build = Join-Path $tools 'Build-Release.ps1'
Copy-Item -LiteralPath (Join-Path $root 'tools/Build-Release.ps1') -Destination $build
Set-Content -LiteralPath (Join-Path $src 'Diagnostico.py') -Value 'LUZ_VERSION = "1.1.2"'
function Test-Path {
    param([string]$LiteralPath)
    return $LiteralPath -like '*.exe'
}

try {
    & $build -Version 9.9.9
    throw 'Expected the mismatched build version to be rejected.'
} catch {
    if ($_.Exception.Message -notlike '*9.9.9*1.1.2*') { throw }
}
