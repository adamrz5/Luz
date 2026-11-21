#ifndef LuzVersion
  #define LuzVersion "1.0.1"
#endif
#ifndef LuzSource
  #define LuzSource "ensayo\app"
#endif
#ifndef LuzAppId
  #define LuzAppId "Luz.adamrz5"
#endif

#ifndef LuzGroup
  #define LuzGroup "Luz"
#endif

[Setup]
AppId={#LuzAppId}
AppName=Luz
AppVersion={#LuzVersion}
AppPublisher=adamrz5
LicenseFile=..\LICENSE
DefaultDirName={localappdata}\Programs\Luz
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
SetupIconFile=luz-qt.ico
UninstallDisplayIcon={app}\Luz.exe
OutputDir=distribucion
OutputBaseFilename=Luz-instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
RestartApplications=no
#ifdef LuzSign
SignTool=luz
SignedUninstaller=yes
#endif

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#LuzSource}\Luz.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#LuzSource}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#LuzGroup}\Luz"; Filename: "{app}\Luz.exe"; WorkingDir: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
  RunKey: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
  if RegQueryStringValue(HKCU, RunKey, 'Luz', Command) and
     (CompareText(Command, '"' + ExpandConstant('{app}\Luz.exe') + '" --oculto') = 0) then
    RegDeleteValue(HKCU, RunKey, 'Luz');
end;
