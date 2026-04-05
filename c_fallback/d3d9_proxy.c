/*
 * d3d9.dll proxy — forces FlatOut 2 into windowed mode.
 *
 * No SDK headers needed. Works with any C compiler (TCC, GCC, MSVC).
 *
 * How it works:
 *   1. Game calls Direct3DCreate9 -> we load the real d3d9.dll and call it
 *   2. We get back an IDirect3D9 COM object (a pointer to a vtable pointer)
 *   3. We replace the CreateDevice entry in the vtable (index 16)
 *   4. Our CreateDevice sets Windowed=TRUE, then calls the original
 *
 * Build with TCC:
 *   tcc -shared -o d3d9.dll d3d9_proxy.c
 *
 * Drop d3d9.dll next to FlatOut2.exe.
 */

#include <windows.h>
#include <stdio.h>

/* ── Logging ─────────────────────────────────────────────────────── */

static FILE *g_log = NULL;

static void log_msg(const char *fmt, ...) {
    if (!g_log) g_log = fopen("d3d9_proxy.log", "w");
    if (!g_log) return;
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

/* ── D3DPRESENT_PARAMETERS layout (offsets we care about) ────────
 *
 * We only need to know where Windowed and FullScreen_RefreshRateInHz
 * sit in the struct. They're at fixed offsets in the D3D9 ABI:
 *
 *   Offset  Field
 *   0x00    BackBufferWidth          (UINT)
 *   0x04    BackBufferHeight         (UINT)
 *   0x08    BackBufferFormat         (UINT/enum)
 *   0x0C    BackBufferCount          (UINT)
 *   0x10    MultiSampleType          (UINT/enum)
 *   0x14    MultiSampleQuality       (DWORD)
 *   0x18    SwapEffect               (UINT/enum)
 *   0x1C    hDeviceWindow            (HWND)
 *   0x20    Windowed                 (BOOL)  <-- this one
 *   0x24    EnableAutoDepthStencil   (BOOL)
 *   0x28    AutoDepthStencilFormat   (UINT/enum)
 *   0x2C    Flags                    (DWORD)
 *   0x30    FullScreen_RefreshRateInHz (UINT) <-- and this one
 *   0x34    PresentationInterval     (UINT)
 *
 * IDirect3D9 vtable index for CreateDevice is 16.
 * ────────────────────────────────────────────────────────────────── */

#define PP_OFFSET_WIDTH       0x00
#define PP_OFFSET_HEIGHT      0x04
#define PP_OFFSET_WINDOWED    0x20
#define PP_OFFSET_REFRESHRATE 0x30

/* IDirect3D9 vtable: CreateDevice is method index 16 */
#define VTABLE_INDEX_CREATEDEVICE 16

/* ── Real d3d9.dll ───────────────────────────────────────────────── */

typedef void* (__stdcall *Direct3DCreate9_t)(unsigned int SDKVersion);
static HMODULE g_real_d3d9 = NULL;
static Direct3DCreate9_t g_real_Direct3DCreate9 = NULL;

/*
 * Original CreateDevice function pointer.
 * Signature: HRESULT __stdcall(void *this, UINT, UINT, HWND, DWORD, void *pPP, void **ppDev)
 */
typedef long (__stdcall *CreateDevice_t)(void *This, unsigned int Adapter,
    unsigned int DeviceType, HWND hWnd, unsigned long BehaviorFlags,
    void *pPresentationParameters, void **ppDevice);

static CreateDevice_t g_original_CreateDevice = NULL;

/* ── Our hooked CreateDevice ─────────────────────────────────────── */

static long __stdcall Hooked_CreateDevice(
    void *This,
    unsigned int Adapter,
    unsigned int DeviceType,
    HWND hWnd,
    unsigned long BehaviorFlags,
    void *pPresentationParameters,
    void **ppDevice
) {
    unsigned char *pp = (unsigned char*)pPresentationParameters;

    unsigned int w = *(unsigned int*)(pp + PP_OFFSET_WIDTH);
    unsigned int h = *(unsigned int*)(pp + PP_OFFSET_HEIGHT);

    log_msg("CreateDevice intercepted: %ux%u, Windowed=%d\n",
            w, h, *(int*)(pp + PP_OFFSET_WINDOWED));

    /* Force windowed mode */
    *(int*)(pp + PP_OFFSET_WINDOWED) = 1;     /* TRUE */
    *(unsigned int*)(pp + PP_OFFSET_REFRESHRATE) = 0;

    log_msg("Forced windowed: %ux%u\n", w, h);

    return g_original_CreateDevice(This, Adapter, DeviceType, hWnd,
                                   BehaviorFlags, pPresentationParameters,
                                   ppDevice);
}

/* ── Hook installation ───────────────────────────────────────────── */

static void hook_vtable(void *pD3D9) {
    /*
     * COM object layout:  pD3D9 -> [lpVtbl] -> [fn0, fn1, ..., fn16, ...]
     * We patch fn16 (CreateDevice) in the vtable.
     */
    void ***ppVtbl = (void***)pD3D9;    /* pD3D9->lpVtbl */
    void **vtbl = *ppVtbl;              /* the actual vtable array */

    g_original_CreateDevice = (CreateDevice_t)vtbl[VTABLE_INDEX_CREATEDEVICE];

    /* Unprotect the vtable entry so we can write to it */
    DWORD oldProtect;
    VirtualProtect(&vtbl[VTABLE_INDEX_CREATEDEVICE], sizeof(void*),
                   PAGE_EXECUTE_READWRITE, &oldProtect);

    vtbl[VTABLE_INDEX_CREATEDEVICE] = (void*)Hooked_CreateDevice;

    VirtualProtect(&vtbl[VTABLE_INDEX_CREATEDEVICE], sizeof(void*),
                   oldProtect, &oldProtect);

    log_msg("Hooked CreateDevice at vtable[%d]\n", VTABLE_INDEX_CREATEDEVICE);
}

/* ── Exported function ───────────────────────────────────────────── */

__declspec(dllexport) void* __stdcall Direct3DCreate9(unsigned int SDKVersion) {
    log_msg("Direct3DCreate9(SDK %u)\n", SDKVersion);

    if (!g_real_d3d9) {
        char path[MAX_PATH];
        GetSystemDirectoryA(path, MAX_PATH);
        strcat(path, "\\d3d9.dll");
        g_real_d3d9 = LoadLibraryA(path);
        if (!g_real_d3d9) {
            log_msg("FATAL: Cannot load %s\n", path);
            return NULL;
        }
        g_real_Direct3DCreate9 = (Direct3DCreate9_t)
            GetProcAddress(g_real_d3d9, "Direct3DCreate9");
        if (!g_real_Direct3DCreate9) {
            log_msg("FATAL: Direct3DCreate9 not found in real dll\n");
            return NULL;
        }
    }

    void *pD3D9 = g_real_Direct3DCreate9(SDKVersion);
    if (!pD3D9) {
        log_msg("Real Direct3DCreate9 returned NULL\n");
        return NULL;
    }

    hook_vtable(pD3D9);
    return pD3D9;
}

/* ── DLL entry point ─────────────────────────────────────────────── */

BOOL __stdcall DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    (void)hinstDLL; (void)lpvReserved;
    if (fdwReason == DLL_PROCESS_DETACH && g_real_d3d9) {
        FreeLibrary(g_real_d3d9);
        if (g_log) fclose(g_log);
    }
    return TRUE;
}
