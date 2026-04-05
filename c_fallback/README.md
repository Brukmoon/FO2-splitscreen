# d3d9 Proxy DLL — Force Windowed Mode

FlatOut 2 has no windowed mode option. This proxy DLL intercepts Direct3D9 and forces `Windowed=TRUE` when the game creates its device.

## How It Works

When you place `d3d9.dll` next to `FlatOut2.exe`, Windows loads it instead of the system one. The proxy loads the real `d3d9.dll` from `System32`, wraps `CreateDevice` to set windowed mode, and passes everything else through.

## Building

FlatOut 2 is a **32-bit** game. You must produce a **32-bit** DLL.

### Option A: MinGW-w64

Install MinGW-w64 with the i686 (32-bit) toolchain. Easiest way:

```
winget install -e --id MSYS2.MSYS2
```

Then open MSYS2 MINGW32 shell and install the toolchain:

```
pacman -S mingw-w64-i686-gcc
```

Build from this directory:

```
i686-w64-mingw32-gcc -shared -m32 -o d3d9.dll d3d9_proxy.c -ld3d9 -Wl,--enable-stdcall-fixup
```

Or just run:

```
build.bat mingw
```

### Option B: Visual Studio

Open **x86 Native Tools Command Prompt** (not x64) from the Start menu, `cd` to this directory, and run:

```
build.bat msvc
```

### Option C: Skip building — use dgVoodoo2

If you don't want to compile anything:

1. Download dgVoodoo2 from http://dgvoodoo.dege.hu/
2. Extract the ZIP
3. Copy `MS/x86/d3d9.dll` into your FlatOut 2 game folder
4. Run `dgVoodooCpl.exe`, point it at the game folder, enable windowed mode

## Installation

Copy the built `d3d9.dll` into your FlatOut 2 game folder (next to `FlatOut2.exe`):

```
copy d3d9.dll "D:\Games\FlatOut 2\d3d9.dll"
```

## Verify It Works

Launch FlatOut 2 normally. It should start in a window instead of fullscreen. Check `d3d9_proxy.log` in the game folder for:

```
Direct3DCreate9 called (SDK 32)
IDirect3D9 wrapped successfully
CreateDevice intercepted: Windowed=0, 640x480
Forced windowed mode: 640x480
```

## Removal

Delete `d3d9.dll` from the game folder. The game goes back to fullscreen.

```
del "D:\Games\FlatOut 2\d3d9.dll"
```
