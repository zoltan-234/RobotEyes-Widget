@echo off
rem RobotEyes-Widget.exe keszitese + parancsikon az asztalra
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --noconsole --onefile --name RobotEyes-Widget --icon icon.ico main.py
if not exist "dist\RobotEyes-Widget.exe" (
  echo HIBA: nem keszult el az exe.
  pause
  exit /b 1
)
rem regi (RobotSzem nevu) parancsikon eltavolitasa, ha van
powershell -NoProfile -Command "Remove-Item -LiteralPath ([Environment]::GetFolderPath('Desktop') + '\RobotSzem.lnk') -ErrorAction SilentlyContinue"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\RobotEyes Widget.lnk'); $s.TargetPath='%~dp0dist\RobotEyes-Widget.exe'; $s.WorkingDirectory='%~dp0dist'; $s.IconLocation='%~dp0dist\RobotEyes-Widget.exe'; $s.Save()"
echo.
echo Kesz: dist\RobotEyes-Widget.exe  (+ "RobotEyes Widget" parancsikon az asztalon)
pause
