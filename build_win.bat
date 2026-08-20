@echo off
REM ============================================================
REM  NetDiag - Windows build script (PyInstaller onedir mode)
REM  Builds Win32 or Win64 package depending on current Python
REM  architecture. Run with 32-bit Python to produce Win32.
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo === NetDiag Windows Build ===
echo Checking Python and PyInstaller...
python --version || goto :err_python
python -m PyInstaller --version >nul 2>&1 || goto :err_pyi

REM Detect Python architecture
python -c "import struct;print('Arch:',struct.calcsize('P')*8)" 
for /f "delims=" %%i in ('python -c "import struct;print(struct.calcsize('P')*8)"') do set PYBITS=%%i
set PKG=Win64
if "%PYBITS%"=="32" set PKG=Win32
echo Building package for: %PKG%  (from Python %PYBITS% bit)

REM --- Build with PyInstaller (onedir) ---
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name NetDiag_%PKG% ^
  --paths src ^
  src\main.py
if errorlevel 1 goto :err_build

REM --- Assemble package ---
set DIST=dist\NetDiag_%PKG%
echo Assembling package: %DIST%
REM Copy iperf3 tools next to the exe (keep win32/win64 subdirs)
xcopy /e /i /y tools "%DIST%\tools" >nul 2>&1
copy /y config.ini "%DIST%\" >nul 2>&1
if not exist "%DIST%\tools" (
  echo WARNING: tools not copied - copy "tools\win32" or "tools\win64" manually
)
copy /y ..\README.md "%DIST%\使用说明.md" >nul 2>&1

echo.
echo === Build DONE ===
echo Output: %DIST%
echo Package contents: main exe + tools + config.ini
echo Distribute the whole folder as green package.
goto :eof

:err_python
echo ERROR: Python not found. Please install Python 3.8+ first.
exit /b 1

:err_pyi
echo ERROR: PyInstaller not found. Run: pip install pyinstaller
exit /b 1

:err_build
echo ERROR: PyInstaller build failed. See messages above.
exit /b 1
