@echo off
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --collect-all playwright --collect-submodules pywinauto --collect-submodules comtypes --hidden-import psutil --name AutoJoin app.py
echo.
echo Готово: dist\AutoJoin.exe
pause
