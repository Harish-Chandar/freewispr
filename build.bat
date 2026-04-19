@echo off
setlocal

rem Run from repository root (folder containing this script)
pushd "%~dp0" >nul

rem Prefer the Python launcher, then fall back to python on PATH
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    set "PYTHON_CMD=python"
  )
)

if "%PYTHON_CMD%"=="" (
  echo ERROR: Python 3.10+ was not found.
  echo Install Python and ensure ^`py^` or ^`python^` is available on PATH.
  popd >nul
  pause
  exit /b 1
)

echo === freewispr build ===
echo.

@REM echo Generating icon...
@REM %PYTHON_CMD% make_icon.py
@REM if errorlevel 1 (
@REM   echo.
@REM   echo Build FAILED while generating icon.
@REM   popd >nul
@REM   pause
@REM   exit /b 1
@REM )

echo.
echo Building exe...
%PYTHON_CMD% -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name freewispr ^
  --icon "assets/icon.ico" ^
  --add-data "assets/icon.png;assets" ^
  --add-data "assets/icon.ico;assets" ^
  --collect-all=faster_whisper ^
  --hidden-import=faster_whisper ^
  --hidden-import=sounddevice ^
  --hidden-import=keyboard ^
  --hidden-import=pystray._win32 ^
  main.py

  if errorlevel 1 (
    echo.
    echo Build FAILED during PyInstaller step.
    popd >nul
    pause
    exit /b 1
  )

echo.
if exist dist\freewispr.exe (
    echo Build successful! dist\freewispr.exe is ready.
) else (
    echo Build FAILED. Check errors above.
)

  popd >nul
pause
