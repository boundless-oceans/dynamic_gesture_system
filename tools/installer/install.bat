@echo off
REM ===================================================================
REM  First-run setup -- just double-click this file once.
REM
REM  It creates a desktop shortcut pointing at the exe in this folder,
REM  then starts the app.  All the talking is done by setup.ps1 (Chinese).
REM
REM  It does NOT copy any files and does NOT set up autostart.  This is a
REM  portable deployment: the app stays right here.  To remove it, run
REM  uninstall.bat next to this file.
REM
REM  WHY ASCII FILENAMES -- install.bat / uninstall.bat / setup.ps1 are all
REM  ASCII on purpose.  The folder and the exe have to be Chinese (that is
REM  the product name), but there is no reason to add more: a non-ASCII
REM  name has to survive zip -> transfer -> extract, and old or non-standard
REM  extractors do not always restore those names correctly.
REM
REM  ENCODING -- this .bat is ASCII-only because Chinese saved as UTF-8
REM  turns into mojibake in the default GBK console.  setup.ps1 carries the
REM  Chinese messages instead; it is saved as UTF-8 *with BOM*, which
REM  PowerShell 5.1 reads correctly.
REM
REM  PATH HANDLING -- pushd "%~dp0" + a relative ".\setup.ps1" is on
REM  purpose: it keeps Chinese characters out of the command line (this
REM  folder name is Chinese), which is the part that tends to break.
REM  Verified working with a Chinese folder name.
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

powershell -NoProfile -ExecutionPolicy Bypass -File ".\setup.ps1"
set RC=%errorlevel%

popd

if not "%RC%"=="0" (
    echo.
    echo [ERROR] Setup failed. See the message above.
    echo.
)

pause
exit /b %RC%
