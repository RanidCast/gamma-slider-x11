import ctypes
import logging
import sys
from ctypes import wintypes

from gamma_color import build_ramp, clip_ramp_endpoints, identity_ramp

if sys.platform != "win32":
    raise ImportError("backend_win32 is Windows-only")

log = logging.getLogger("gamma_slider")

RAMP_SIZE = 256
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x00000008


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


class RAMP(ctypes.Structure):
    _fields_ = [
        ("red", wintypes.WORD * RAMP_SIZE),
        ("green", wintypes.WORD * RAMP_SIZE),
        ("blue", wintypes.WORD * RAMP_SIZE),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

user32.EnumDisplayDevicesW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD,
]
user32.EnumDisplayDevicesW.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateDCW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
]
gdi32.CreateDCW.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.GetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]
gdi32.GetDeviceGammaRamp.restype = wintypes.BOOL
gdi32.SetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]
gdi32.SetDeviceGammaRamp.restype = wintypes.BOOL


def _copy_ramp(src):
    dst = RAMP()
    ctypes.memmove(ctypes.byref(dst), ctypes.byref(src), ctypes.sizeof(RAMP))
    return dst


def _fill_ramp(struct, r, g, b):
    struct.red[:] = r
    struct.green[:] = g
    struct.blue[:] = b


class Win32Backend:
    def __init__(self):
        self._displays = []
        self._enumerate()

    def _add_display(self, hdc, name, from_getdc=False):
        original = RAMP()
        saved = None
        if gdi32.GetDeviceGammaRamp(hdc, ctypes.byref(original)):
            saved = _copy_ramp(original)
        else:
            log.warning("GetDeviceGammaRamp failed for %s", name)
        self._displays.append({
            "hdc": hdc,
            "name": name,
            "original": saved,
            "from_getdc": from_getdc,
        })

    def _enumerate(self):
        i = 0
        while True:
            dd = DISPLAY_DEVICEW()
            dd.cb = ctypes.sizeof(dd)
            if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
                break
            flags = dd.StateFlags
            attached = flags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
            mirror = flags & DISPLAY_DEVICE_MIRRORING_DRIVER
            if attached and not mirror:
                name = dd.DeviceName
                hdc = gdi32.CreateDCW("DISPLAY", name, None, None)
                if hdc:
                    self._add_display(hdc, name)
            i += 1
        if not self._displays:
            hdc = user32.GetDC(None)
            if hdc:
                self._add_display(hdc, "PRIMARY", from_getdc=True)
        log.info("Win32 displays: %s", [d["name"] for d in self._displays])

    def apply(self, temp, gamma, mode=0):
        r, g, b = build_ramp(int(temp), float(gamma), 1.0, int(mode), RAMP_SIZE)
        ramp = RAMP()
        _fill_ramp(ramp, r, g, b)
        any_ok = False
        for d in self._displays:
            if gdi32.SetDeviceGammaRamp(d["hdc"], ctypes.byref(ramp)):
                any_ok = True
                continue
            cr, cg, cb = clip_ramp_endpoints(r, g, b)
            clipped = RAMP()
            _fill_ramp(clipped, cr, cg, cb)
            if gdi32.SetDeviceGammaRamp(d["hdc"], ctypes.byref(clipped)):
                any_ok = True
                log.warning("SetDeviceGammaRamp used clipped endpoints on %s", d["name"])
            else:
                log.warning("SetDeviceGammaRamp failed on %s", d["name"])
        return any_ok

    def reset(self):
        ident = identity_ramp(RAMP_SIZE)
        ident_ramp = RAMP()
        _fill_ramp(ident_ramp, ident, ident, ident)
        for d in self._displays:
            ok = False
            if d["original"] is not None:
                ok = bool(gdi32.SetDeviceGammaRamp(d["hdc"], ctypes.byref(d["original"])))
            if not ok:
                gdi32.SetDeviceGammaRamp(d["hdc"], ctypes.byref(ident_ramp))

    def close(self):
        self.reset()
        for d in self._displays:
            if d.get("from_getdc"):
                user32.ReleaseDC(None, d["hdc"])
            else:
                gdi32.DeleteDC(d["hdc"])
        self._displays.clear()
