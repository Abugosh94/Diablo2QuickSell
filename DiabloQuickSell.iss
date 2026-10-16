[Setup]
AppName=Diablo2QuickSell
AppVersion=1.0
DefaultDirName={pf}\DiabloQuickSell
DefaultGroupName=Diablo2QuickSell
OutputDir=user:output
OutputBaseFilename=Diablo2QuickSellSetup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\Diablo2QuickSell.exe"; DestDir: "{app}"; Flags: ignoreversion
; Ensure the captures folder exists next to the exe
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "Diablo2QuickSell.exe"

[Dirs]
Name: "{app}\captures"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\Diablo2QuickSell"; Filename: "{app}\Diablo2QuickSell.exe"
Name: "{desktop}\Diablo2QuickSell"; Filename: "{app}\Diablo2QuickSell.exe"

[Run]
Filename: "{app}\Diablo2QuickSell.exe"; Description: "Launch Diablo2QuickSell"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\captures"

