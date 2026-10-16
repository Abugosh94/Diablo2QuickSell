; Diablo2QuickSell Installer Script
; Compile with: iscc Diablo2QuickSell.iss

#define MyAppName "Diablo2QuickSell"
#define MyAppVersion "0.02"
#define MyAppPublisher "Diablo2QuickSell"
#define MyAppExeName "Diablo2QuickSell.exe"

[Setup]
AppId={{8D3F2A1B-4C5E-6F7G-8H9I-0J1K2L3M4N5O}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer
OutputFile=Diablo2QuickSell_Setup_{#MyAppVersion}.exe
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The main executable
Source: "dist\Diablo2QuickSell.exe"; DestDir: "{app}"; Flags: ignoreversion
; The YOLO model file (bundled alongside the exe)
Source: "tooltip_best_v6.pt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
