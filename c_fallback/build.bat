@echo off
REM Build d3d9.dll proxy for FlatOut 2 (32-bit)
REM
REM Option 1: MinGW-w64 (install from https://www.mingw-w64.org/)
REM   Run from the c_fallback directory:
REM     build.bat mingw
REM
REM Option 2: Visual Studio (open "x86 Native Tools Command Prompt")
REM   Run from the c_fallback directory:
REM     build.bat msvc
REM
REM The output d3d9.dll goes into this directory.
REM Copy it to your FlatOut 2 game folder (next to FlatOut2.exe).

if "%1"=="msvc" goto msvc
if "%1"=="mingw" goto mingw

echo Usage: build.bat [mingw^|msvc]
echo.
echo   mingw  - Build with MinGW-w64 (i686-w64-mingw32-gcc must be in PATH)
echo   msvc   - Build with MSVC (run from x86 Native Tools Command Prompt)
goto end

:mingw
echo Building with MinGW-w64 (32-bit)...
i686-w64-mingw32-gcc -shared -m32 -o d3d9.dll d3d9_proxy.c -ld3d9 -Wl,--enable-stdcall-fixup
if %errorlevel%==0 (
    echo SUCCESS: d3d9.dll created
    echo Copy it to your FlatOut 2 game folder.
) else (
    echo FAILED. Make sure i686-w64-mingw32-gcc is installed and in PATH.
)
goto end

:msvc
echo Building with MSVC (32-bit)...
cl /nologo /LD /DWIN32 /DCINTERFACE /DCOBJMACROS d3d9_proxy.c /Fe:d3d9.dll /link /DEF:d3d9.def d3d9.lib
if %errorlevel%==0 (
    echo SUCCESS: d3d9.dll created
    echo Copy it to your FlatOut 2 game folder.
) else (
    echo FAILED. Make sure you are in a x86 Native Tools Command Prompt.
)
goto end

:end
