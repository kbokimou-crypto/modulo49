@echo off
REM Construit Modulo49.exe puis, si Inno Setup est installé, linstallateur.
cd /d "%~dp0"
python -m pip install --upgrade -r requirements.txt || goto erreur
python -m PyInstaller --noconfirm modulo49.spec || goto erreur
echo.
echo Programme construit : dist\Modulo49\Modulo49.exe
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
  %ISCC% installateur.iss || goto erreur
  echo Installateur construit : installateur\Modulo49-Setup.exe
) else (
  echo Inno Setup 6 non trouve : seul le dossier dist\Modulo49 a ete cree.
)
pause
exit /b 0
:erreur
echo La construction a echoue.
pause
exit /b 1
