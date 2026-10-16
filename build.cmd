@echo off
rem ============================================================
rem  Build script for D2InventoryScanner.exe  (PyInstaller)
rem  Full from-scratch build; all output goes to build_out.log.
rem  The final line of the log is BUILD_EXIT_CODE=N  (0 = success)
rem ============================================================
cd /d "D:\Addon test"

rem --- clean previous artifacts --------------------------------------
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist D2InventoryScanner.spec del /q D2InventoryScanner.spec
if exist build_out.log del /q build_out.log

echo BUILD_STARTED %date% %time% > build_out.log

rem --- build ---------------------------------------------------------
rem  --onefile      : single exe at dist\D2InventoryScanner.exe
rem  --noconsole    : windowless app (GUI/tkinter, matches main.py design)
rem  --add-data     : model at bundle ROOT, because main.py loads it from
rem                   os.path.dirname(__file__) (the _MEIPASS root)
rem  --collect-all  : ultralytics and torchvision need their files bundled
rem                  (torchvision provides NMS operator used by YOLO inference)
"C:\Users\Asad\AppData\Roaming\Python\Python311\Scripts\pyinstaller.exe" ^
  --noconfirm --clean --onefile --noconsole ^
  --upx-dir "C:\upx-5.2.1-win64" ^
  --name D2InventoryScanner ^
  --add-data "tooltip_best_v6.pt;." ^
  --collect-all ultralytics ^
  --collect-all torchvision ^
  main.py >> build_out.log 2>&1

echo BUILD_EXIT_CODE=%ERRORLEVEL% >> build_out.log
