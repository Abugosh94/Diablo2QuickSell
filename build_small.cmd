@echo off
rem ============================================================
rem  Build a *smaller* D2InventoryScanner.exe
rem  - Uses UPX compression (if UPX is in PATH)
rem  - Excludes Torch sub‑modules that are not needed by Ultralytics
rem ============================================================
setlocal

rem ------ 1. Folder setup --------------------------------------
pushd "%~dp0"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist D2InventoryScanner.spec del /q D2InventoryScanner.spec
if exist build_out.log del /q build_out.log

rem ------ 2. PyInstaller command -------------------------------
set PYI_CMD="%USERPROFILE%\AppData\Roaming\Python\Python311\Scripts\pyinstaller.exe"
rem Add any exclusions you need – the list below covers the biggest
rem unused parts of PyTorch while keeping what Ultralytics requires.
set EXCLUDES=^
    --exclude-module torch.distributed ^
    --exclude-module torch.testing ^
    --exclude-module torch.nn.parallel ^
    --exclude-module torch.utils.benchmark ^
    --exclude-module torch.utils.data.datapipes ^
    --exclude-module torch.utils.mobile_optimizer ^
    --exclude-module torch.utils.model_zoo ^
    --exclude-module torch.hub ^
    --exclude-module torch.onnx ^
    --exclude-module torch.nn.intrinsic ^
    --exclude-module torchvision

echo BUILD_STARTED %date% %time% > build_out.log
%PYI_CMD% ^
    --noconfirm --clean --onefile --noconsole ^
    --name D2InventoryScanner ^
    --add-data "tooltip_best_v6.pt;." ^
    --collect-all ultralytics ^
    %EXCLUDES% ^
    main.py >> build_out.log 2>&1

echo BUILD_EXIT_CODE=%ERRORLEVEL% >> build_out.log

rem ------ 3. Optional UPX compression -------------------------
where upx >nul 2>&1
if not errorlevel 1 (
    echo Running UPX compression...
    upx --best --lzma dist\D2InventoryScanner.exe >> build_out.log 2>&1
) else (
    echo UPX not found in PATH – skipping compression.
    echo To get a smaller exe, install UPX from https://upx.github.io/ and add it to your PATH.
)

popd
endlocal