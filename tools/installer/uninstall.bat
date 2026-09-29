@echo off
REM ===================================================================
REM  Uninstall -- just double-click this file once.
REM
REM  It removes the desktop shortcut and (after you confirm by typing
REM  "yes") the whole app folder.  It also cleans up an autostart entry
REM  in case an older build created one.
REM
REM  Why "yes" and not just a keypress: deleting the folder also deletes
REM  logs\ and config_local.json -- the on-site log history and any tuned
REM  parameters.  That is not something to do by bumping the keyboard.
REM
REM  ASCII-only and pushd + relative path, same reasons as install.bat
REM  next to this file.
REM ===================================================================

setlocal
pushd "%~dp0"

if not exist "setup.ps1" (
    echo.
    echo [ERROR] setup.ps1 is missing.
    echo         Keep this .bat together with the app in the same folder.
    echo.
    popd
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File ".\setup.ps1" -Uninstall
set RC=%errorlevel%

popd

if not "%RC%"=="0" (
    echo.
    echo [ERROR] Uninstall failed. See the message above.
    echo.
)

pause
exit /b %RC%
