@echo off
:loop
if exist dist\D2InventoryScanner.exe (
    echo EXE_READY
    goto :eof
)
ping -n 6 127.0.0.1 >nul
goto loop