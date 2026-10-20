@echo off
REM Link every skill in this repo into each agent's skills directory
REM via per-skill NTFS junctions (no admin rights required).
REM
REM Repo layout:
REM   my-skills\<skill>\     self-made skills
REM   download\<skill>\      third-party (downloaded) skills
REM
REM The agent-side skills directory becomes a real directory filled
REM with junctions, one per skill, so both kinds stay visible.
REM
REM Usage: run once after cloning this repo on a new machine,
REM        and re-run after adding a skill or moving skills around
REM        (broken junctions are detected and rebuilt automatically).
setlocal
set "REPO=%~dp0"
if not exist "%REPO%my-skills" (
    echo [error] my-skills not found under %REPO%
    exit /b 1
)
if not exist "%REPO%download" (
    echo [error] download not found under %REPO%
    exit /b 1
)

for %%D in (.claude .agents .zcode) do call :prepare %%D

echo.
echo Done. Restart your agent tools to reload skills.
exit /b 0

:prepare
set "DIR=%USERPROFILE%\%~1\skills"
if not exist "%DIR%" goto :mkdir

dir "%USERPROFILE%\%~1" /AL /B 2>nul | findstr /I /X "skills" >nul
if not errorlevel 1 (
    echo [reset]  %DIR% is a junction - replacing with a real directory
    rmdir "%DIR%"
    goto :mkdir
)

echo [keep]   %DIR% already exists as a real directory
goto :linkskills

:mkdir
mkdir "%DIR%" 2>nul

:linkskills
REM self-made skills under my-skills\
for /D %%S in ("%REPO%my-skills\*") do if exist "%%S\SKILL.md" call :linkone "%DIR%" "%%S"
REM third-party skills under download\
for /D %%S in ("%REPO%download\*") do if exist "%%S\SKILL.md" call :linkone "%DIR%" "%%S"
exit /b 0

:linkone
set "LINK=%~1\%~n2"
dir "%~1" /AL /B 2>nul | findstr /I /X "%~n2" >nul
if not errorlevel 1 (
    REM "link\*" enumerates the target: false means the junction is broken
    if exist "%LINK%\*" (
        echo [skip]   %LINK%
    ) else (
        echo [repair] %LINK% is broken - relinking
        rmdir "%LINK%"
        goto :mk
    )
    exit /b 0
)
if exist "%LINK%" (
    echo [warn]   %LINK% exists and is not a junction - skipped
    exit /b 0
)
:mk
echo [link]   %LINK% -^> %~2
mklink /J "%LINK%" "%~2" >nul
exit /b 0
