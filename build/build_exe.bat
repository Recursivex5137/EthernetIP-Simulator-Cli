@echo off
echo ================================================
echo Building EthernetIP Simulator Portable .exe
echo ================================================
echo.

REM Clean previous builds
echo [1/4] Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
echo      Done.
echo.

REM Check UPX availability
echo [2/4] Checking UPX compression tool...
where upx >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo      WARNING: UPX not found in PATH
    echo      Build will be larger without UPX compression
    echo      Download from: https://github.com/upx/upx/releases
    echo      Extract upx.exe to a folder in your PATH
    echo.
    echo      Continue without UPX? Press Ctrl+C to cancel, or
    pause
) else (
    echo      UPX found - will use compression
)
echo.

REM Build executable
echo [3/4] Building executable with PyInstaller...
set PYTHONOPTIMIZE=2
pyinstaller --clean --log-level WARN build\EthernetIP_Simulator.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    echo Check the output above for errors.
    pause
    exit /b 1
)
echo      Build successful!
echo.

REM Report size
echo [4/4] Build Summary
echo ================================================
for %%A in ("dist\EthernetIP_Simulator.exe") do (
    set size=%%~zA
    set /a size_mb=%%~zA/1048576
    echo Executable: dist\EthernetIP_Simulator.exe
    echo Size: %%~zA bytes (~!size_mb! MB)
)
echo.
echo Target: 80-120 MB
echo ================================================
echo.
echo Next Steps:
echo 1. Test the executable: dist\EthernetIP_Simulator.exe
echo 2. Copy to a clean machine (no Python) for final testing
echo 3. If size is too large, see plan for advanced optimizations
echo.
pause
