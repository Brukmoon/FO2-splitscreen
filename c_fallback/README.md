# d3d9 Proxy DLL — Force Windowed Mode

FlatOut 2 has no windowed mode option. This proxy DLL forces it.

## Build

FlatOut 2 is 32-bit. You need a 32-bit C compiler.

**Easiest: install TCC (Tiny C Compiler) — single exe, no setup:**

1. Download `tcc-0.9.27-win32-bin.zip` from https://download.savannah.gnu.org/releases/tinycc/
2. Extract anywhere (e.g. `C:\tcc`)
3. From this directory, run:

```
C:\tcc\tcc.exe -shared -o d3d9.dll d3d9_proxy.c -ld3d9
```

Done.

## Install

Copy `d3d9.dll` to your FlatOut 2 game folder (next to `FlatOut2.exe`).

## Remove

Delete `d3d9.dll` from the game folder. Game goes back to fullscreen.
