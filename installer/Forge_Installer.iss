#define MyAppName "Forge"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "JeanMarc31110"
#define MyAppExeName "Forge.exe"

[Setup]
AppId={{A7F2E3C1-9B45-4E8A-9F1D-2A5C8B3D4E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf64}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=Forge_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayName={#MyAppName}
CreateUninstallRegKey=yes
SetupLogging=yes
MinVersion=10.0.17763
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[InstallDelete]
Type: filesandordirs; Name: "{app}\*"
Type: files; Name: "{userdesktop}\Forge.lnk"
Type: files; Name: "{commondesktop}\Forge.lnk"
Type: files; Name: "{userprograms}\Forge.lnk"
Type: files; Name: "{commonprograms}\Forge.lnk"

[Files]
Source: "..\dist\Forge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Forge"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Forge"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Forge"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopLegacyInstances();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/C taskkill /F /T /IM Forge.exe >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeSetup(): Boolean;
begin
  StopLegacyInstances();
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopLegacyInstances();
end;
