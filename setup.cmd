@echo off
REM Link this repo's skills/ directory into every agent's skills location
REM via NTFS junctions (no admin rights required).
REM Usage: run once after cloning this repo on a new machine.
setlocal
set "REPO=%~dp0skills"
if not exist "%REPO%" (
    echo [error] skills directory not found: %REPO%
    exit /b 1
)

for %%D in (.claude .agents .zcode) do call :link %%D

echo.
echo Done. Restart your agent tools to reload skills.
exit /b 0

:link
set "DIR=%USERPROFILE%\%~1\skills"
if not exist "%DIR%" goto :mklink

dir "%USERPROFILE%\%~1" /AL /B 2>nul | findstr /I /X "skills" >nul
if not errorlevel 1 (
    echo [skip]   %DIR% is already a junction
    exit /b 0
)

echo [backup] %DIR% -^> %DIR%.bak
move "%DIR%" "%DIR%.bak" >nul

:mklink
echo [link]   %DIR% -^> %REPO%
mklink /J "%DIR%" "%REPO%"
exit /b 0
