@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment tidak ditemukan.
    echo Jalankan scripts\install_windows.bat terlebih dahulu.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m PyInstaller --noconfirm --clean --windowed --onefile --name ARSIPTA --icon "assets\icon\apps.ico" --add-data "assets;assets" --collect-all PySide6 main.py

if errorlevel 1 (
    echo.
    echo BUILD GAGAL. Periksa pesan error di atas.
    pause
    exit /b 1
)

echo.
echo BUILD BERHASIL.
echo Executable: dist\ARSIPTA.exe
echo Salin hanya ARSIPTA.exe untuk distribusi.
pause
