[Setup]
AppName=Diablo Quick-Sell
AppVersion=1.0
DefaultDirName={pf}\DiabloQuickSell
DefaultGroupName=Diablo Quick-Sell
OutputDir=user:output
OutputBaseFilename=DiabloQuickSellSetup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\D2InventoryScanner.exe"; DestDir: "{app}"; Flags: ignoreversion
; Ensure the captures folder exists next to the exe
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "D2InventoryScanner.exe"

[Dirs]
Name: "{app}\captures"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\Diablo Quick-Sell"; Filename: "{app}\D2InventoryScanner.exe"
Name: "{desktop}\Diablo Quick-Sell"; Filename: "{app}\D2InventoryScanner.exe"

[Run]
Filename: "{app}\D2InventoryScanner.exe"; Description: "Launch Diablo Quick-Sell"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\captures"
