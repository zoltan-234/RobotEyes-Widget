@echo off
setlocal
title RobotEyes Widget eltavolitas
cd /d "%~dp0"
echo.
echo  RobotEyes Widget eltavolitasa
echo  -----------------------------
echo  Ez a kovetkezoket csinalja:
echo   - leallitja a futo RobotEyes Widgetet
echo   - torli az asztali parancsikont
echo   - torli a beallitasokat  (%APPDATA%\RobotEyes-Widget)
echo   - torli ezt a teljes mappat:  %~dp0
echo.
choice /C IN /M "Biztosan eltavolitod? (I = igen, N = nem)"
if errorlevel 2 (
  echo Megszakitva, semmi nem valtozott.
  pause
  exit /b 0
)

echo.
echo [1/5] RobotEyes Widget leallitasa...
if exist "%APPDATA%\RobotEyes-Widget\roboteyes.pid" (
  set /p RSPID=<"%APPDATA%\RobotEyes-Widget\roboteyes.pid"
)
if defined RSPID taskkill /PID %RSPID% /F >nul 2>&1
rem korabbi nev (RobotSzem) is
if exist "%APPDATA%\RobotSzem\robotszem.pid" (
  set /p OLDPID=<"%APPDATA%\RobotSzem\robotszem.pid"
)
if defined OLDPID taskkill /PID %OLDPID% /F >nul 2>&1
taskkill /IM RobotEyes-Widget.exe /F >nul 2>&1
taskkill /IM RobotSzem.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/5] Asztali parancsikon torlese...
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); Remove-Item -LiteralPath ($d + '\RobotEyes Widget.lnk'),($d + '\RobotSzem.lnk') -ErrorAction SilentlyContinue"

echo [3/5] Beallitasok torlese...
if exist "%APPDATA%\RobotEyes-Widget" rmdir /s /q "%APPDATA%\RobotEyes-Widget"
if exist "%APPDATA%\RobotSzem" rmdir /s /q "%APPDATA%\RobotSzem"
if exist "%TEMP%\RobotEyes-Widget.lock" del /f /q "%TEMP%\RobotEyes-Widget.lock" >nul 2>&1
if exist "%TEMP%\RobotSzem.lock" del /f /q "%TEMP%\RobotSzem.lock" >nul 2>&1

echo [4/5] Python csomagok (PySide6, PyInstaller)
echo   Ezeket mas programok is hasznalhatjak. Ha nem tudod, valaszd az N-t.
choice /C IN /M "  Toroljem oket is? (I = igen, N = nem)"
if errorlevel 2 goto skippip
python -m pip uninstall -y PySide6 PySide6_Addons PySide6_Essentials shiboken6 pyinstaller pyinstaller-hooks-contrib >nul 2>&1
echo   Python csomagok torolve.
:skippip

echo [5/5] A RobotEyes Widget mappa torlese...
echo.
echo  Kesz! A RobotEyes Widget el lett tavolitva. Ez az ablak bezarul.
timeout /t 3 /nobreak >nul
cd /d "%TEMP%"
start "" /min cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q "%~dp0""
exit
