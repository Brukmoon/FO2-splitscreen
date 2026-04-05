/*
 * d3d9.dll proxy — forces FlatOut 2 into windowed mode.
 *
 * Drop the compiled d3d9.dll into the FlatOut 2 game directory (next to
 * FlatOut2.exe). The game loads DLLs from its own directory first, so it
 * picks up this proxy instead of the system d3d9.dll.
 *
 * This proxy:
 *   1. Loads the real d3d9.dll from System32
 *   2. Hooks Direct3DCreate9 to return a wrapper IDirect3D9
 *   3. The wrapper intercepts CreateDevice to set Windowed=TRUE
 *   4. All other calls pass through to the real Direct3D9
 *
 * Build (MinGW-w64, 32-bit — FlatOut 2 is a 32-bit game):
 *   i686-w64-mingw32-gcc -shared -o d3d9.dll d3d9_proxy.c -ld3d9 -luuid
 *
 * Build (MSVC / Visual Studio Developer Command Prompt, 32-bit):
 *   cl /LD /DWIN32 d3d9_proxy.c /link /DEF:d3d9.def d3d9_real.lib
 *
 * Build (simple, with the provided build script):
 *   build.bat
 */

#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

/* ── Logging ────────────────────────────────────────────────────────── */

static FILE *g_log = NULL;

static void log_init(void) {
    if (!g_log) g_log = fopen("d3d9_proxy.log", "w");
}
static void log_msg(const char *fmt, ...) {
    if (!g_log) return;
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

/* ── Real d3d9.dll ──────────────────────────────────────────────────── */

typedef IDirect3D9* (WINAPI *Direct3DCreate9_t)(UINT SDKVersion);
static HMODULE g_real_d3d9 = NULL;
static Direct3DCreate9_t g_real_Direct3DCreate9 = NULL;

static BOOL load_real_d3d9(void) {
    char path[MAX_PATH];
    GetSystemDirectoryA(path, MAX_PATH);
    strcat(path, "\\d3d9.dll");
    g_real_d3d9 = LoadLibraryA(path);
    if (!g_real_d3d9) return FALSE;
    g_real_Direct3DCreate9 = (Direct3DCreate9_t)GetProcAddress(g_real_d3d9, "Direct3DCreate9");
    return g_real_Direct3DCreate9 != NULL;
}

/* ── IDirect3D9 Wrapper ─────────────────────────────────────────────
 *
 * We wrap the IDirect3D9 vtable to intercept CreateDevice.
 * All other methods forward to the real object.
 * ──────────────────────────────────────────────────────────────────── */

typedef struct D3D9Wrapper {
    IDirect3D9Vtbl *lpVtbl;
    IDirect3D9Vtbl vtbl;      /* Our modified vtable copy */
    IDirect3D9 *real;         /* The real IDirect3D9 */
    ULONG refcount;
} D3D9Wrapper;

/* Forward all calls via macros — tedious but straightforward */

static HRESULT WINAPI W_QueryInterface(IDirect3D9 *This, REFIID riid, void **ppvObj) {
    D3D9Wrapper *w = (D3D9Wrapper*)This;
    return IDirect3D9_QueryInterface(w->real, riid, ppvObj);
}
static ULONG WINAPI W_AddRef(IDirect3D9 *This) {
    D3D9Wrapper *w = (D3D9Wrapper*)This;
    return ++w->refcount;
}
static ULONG WINAPI W_Release(IDirect3D9 *This) {
    D3D9Wrapper *w = (D3D9Wrapper*)This;
    if (--w->refcount == 0) {
        IDirect3D9_Release(w->real);
        free(w);
        return 0;
    }
    return w->refcount;
}
static HRESULT WINAPI W_RegisterSoftwareDevice(IDirect3D9 *This, void *pInit) {
    return IDirect3D9_RegisterSoftwareDevice(((D3D9Wrapper*)This)->real, pInit);
}
static UINT WINAPI W_GetAdapterCount(IDirect3D9 *This) {
    return IDirect3D9_GetAdapterCount(((D3D9Wrapper*)This)->real);
}
static HRESULT WINAPI W_GetAdapterIdentifier(IDirect3D9 *This, UINT a, DWORD b, D3DADAPTER_IDENTIFIER9 *c) {
    return IDirect3D9_GetAdapterIdentifier(((D3D9Wrapper*)This)->real, a, b, c);
}
static UINT WINAPI W_GetAdapterModeCount(IDirect3D9 *This, UINT a, D3DFORMAT b) {
    return IDirect3D9_GetAdapterModeCount(((D3D9Wrapper*)This)->real, a, b);
}
static HRESULT WINAPI W_EnumAdapterModes(IDirect3D9 *This, UINT a, D3DFORMAT b, UINT c, D3DDISPLAYMODE *d) {
    return IDirect3D9_EnumAdapterModes(((D3D9Wrapper*)This)->real, a, b, c, d);
}
static HRESULT WINAPI W_GetAdapterDisplayMode(IDirect3D9 *This, UINT a, D3DDISPLAYMODE *b) {
    return IDirect3D9_GetAdapterDisplayMode(((D3D9Wrapper*)This)->real, a, b);
}
static HRESULT WINAPI W_CheckDeviceType(IDirect3D9 *This, UINT a, D3DDEVTYPE b, D3DFORMAT c, D3DFORMAT d, BOOL e) {
    return IDirect3D9_CheckDeviceType(((D3D9Wrapper*)This)->real, a, b, c, d, e);
}
static HRESULT WINAPI W_CheckDeviceFormat(IDirect3D9 *This, UINT a, D3DDEVTYPE b, D3DFORMAT c, DWORD d, D3DRESOURCETYPE e, D3DFORMAT f) {
    return IDirect3D9_CheckDeviceFormat(((D3D9Wrapper*)This)->real, a, b, c, d, e, f);
}
static HRESULT WINAPI W_CheckDeviceMultiSampleType(IDirect3D9 *This, UINT a, D3DDEVTYPE b, D3DFORMAT c, BOOL d, D3DMULTISAMPLE_TYPE e, DWORD *f) {
    return IDirect3D9_CheckDeviceMultiSampleType(((D3D9Wrapper*)This)->real, a, b, c, d, e, f);
}
static HRESULT WINAPI W_CheckDepthStencilMatch(IDirect3D9 *This, UINT a, D3DDEVTYPE b, D3DFORMAT c, D3DFORMAT d, D3DFORMAT e) {
    return IDirect3D9_CheckDepthStencilMatch(((D3D9Wrapper*)This)->real, a, b, c, d, e);
}
static HRESULT WINAPI W_CheckDeviceFormatConversion(IDirect3D9 *This, UINT a, D3DDEVTYPE b, D3DFORMAT c, D3DFORMAT d) {
    return IDirect3D9_CheckDeviceFormatConversion(((D3D9Wrapper*)This)->real, a, b, c, d);
}
static HRESULT WINAPI W_GetDeviceCaps(IDirect3D9 *This, UINT a, D3DDEVTYPE b, D3DCAPS9 *c) {
    return IDirect3D9_GetDeviceCaps(((D3D9Wrapper*)This)->real, a, b, c);
}
static HMONITOR WINAPI W_GetAdapterMonitor(IDirect3D9 *This, UINT a) {
    return IDirect3D9_GetAdapterMonitor(((D3D9Wrapper*)This)->real, a);
}

/* ── The important one: CreateDevice ─────────────────────────────── */

static HRESULT WINAPI W_CreateDevice(
    IDirect3D9 *This,
    UINT Adapter,
    D3DDEVTYPE DeviceType,
    HWND hFocusWindow,
    DWORD BehaviorFlags,
    D3DPRESENT_PARAMETERS *pPresentationParameters,
    IDirect3DDevice9 **ppReturnedDeviceInterface
) {
    D3D9Wrapper *w = (D3D9Wrapper*)This;

    log_msg("CreateDevice intercepted: Windowed=%d, %dx%d\n",
            pPresentationParameters->Windowed,
            pPresentationParameters->BackBufferWidth,
            pPresentationParameters->BackBufferHeight);

    /* Force windowed mode */
    pPresentationParameters->Windowed = TRUE;
    pPresentationParameters->FullScreen_RefreshRateInHz = 0;

    log_msg("Forced windowed mode: %dx%d\n",
            pPresentationParameters->BackBufferWidth,
            pPresentationParameters->BackBufferHeight);

    return IDirect3D9_CreateDevice(w->real, Adapter, DeviceType, hFocusWindow,
                                   BehaviorFlags, pPresentationParameters,
                                   ppReturnedDeviceInterface);
}

/* ── Wrapper construction ────────────────────────────────────────── */

static IDirect3D9* wrap_d3d9(IDirect3D9 *real) {
    D3D9Wrapper *w = (D3D9Wrapper*)malloc(sizeof(D3D9Wrapper));
    if (!w) return real;

    w->real = real;
    w->refcount = 1;

    /* Copy the real vtable and override CreateDevice */
    w->vtbl = *real->lpVtbl;
    w->vtbl.QueryInterface             = W_QueryInterface;
    w->vtbl.AddRef                     = W_AddRef;
    w->vtbl.Release                    = W_Release;
    w->vtbl.RegisterSoftwareDevice     = W_RegisterSoftwareDevice;
    w->vtbl.GetAdapterCount            = W_GetAdapterCount;
    w->vtbl.GetAdapterIdentifier       = W_GetAdapterIdentifier;
    w->vtbl.GetAdapterModeCount        = W_GetAdapterModeCount;
    w->vtbl.EnumAdapterModes           = W_EnumAdapterModes;
    w->vtbl.GetAdapterDisplayMode      = W_GetAdapterDisplayMode;
    w->vtbl.CheckDeviceType            = W_CheckDeviceType;
    w->vtbl.CheckDeviceFormat          = W_CheckDeviceFormat;
    w->vtbl.CheckDeviceMultiSampleType = W_CheckDeviceMultiSampleType;
    w->vtbl.CheckDepthStencilMatch     = W_CheckDepthStencilMatch;
    w->vtbl.CheckDeviceFormatConversion= W_CheckDeviceFormatConversion;
    w->vtbl.GetDeviceCaps              = W_GetDeviceCaps;
    w->vtbl.GetAdapterMonitor          = W_GetAdapterMonitor;
    w->vtbl.CreateDevice               = W_CreateDevice;

    w->lpVtbl = &w->vtbl;

    log_msg("IDirect3D9 wrapped successfully\n");
    return (IDirect3D9*)w;
}

/* ── Exported function ───────────────────────────────────────────── */

__declspec(dllexport) IDirect3D9* WINAPI Direct3DCreate9(UINT SDKVersion) {
    log_init();
    log_msg("Direct3DCreate9 called (SDK %u)\n", SDKVersion);

    if (!g_real_Direct3DCreate9 && !load_real_d3d9()) {
        log_msg("FATAL: Could not load real d3d9.dll\n");
        return NULL;
    }

    IDirect3D9 *real = g_real_Direct3DCreate9(SDKVersion);
    if (!real) {
        log_msg("Real Direct3DCreate9 returned NULL\n");
        return NULL;
    }

    return wrap_d3d9(real);
}

/* ── DLL entry point ─────────────────────────────────────────────── */

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    (void)hinstDLL; (void)lpvReserved;
    if (fdwReason == DLL_PROCESS_DETACH && g_real_d3d9) {
        FreeLibrary(g_real_d3d9);
    }
    return TRUE;
}
