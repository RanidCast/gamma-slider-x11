import ctypes
import logging
import sys
from ctypes import POINTER, byref, c_float, c_int32, c_uint32

from gamma_color import build_ramp, clip_ramp_endpoints

if sys.platform != "darwin":
    raise ImportError("backend_macos is macOS-only")

log = logging.getLogger("gamma_slider")

CGDirectDisplayID = c_uint32
CGDisplayCount = c_uint32
CGTableCount = c_uint32
CGGammaValue = c_float
CGError = c_int32
kCGErrorSuccess = 0

_CG = ctypes.CDLL(
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)

_CG.CGGetActiveDisplayList.argtypes = [
    CGDisplayCount, POINTER(CGDirectDisplayID), POINTER(CGDisplayCount),
]
_CG.CGGetActiveDisplayList.restype = CGError
_CG.CGDisplayGammaTableCapacity.argtypes = [CGDirectDisplayID]
_CG.CGDisplayGammaTableCapacity.restype = CGTableCount
_CG.CGGetDisplayTransferByTable.argtypes = [
    CGDirectDisplayID,
    CGTableCount,
    POINTER(CGGammaValue),
    POINTER(CGGammaValue),
    POINTER(CGGammaValue),
    POINTER(CGTableCount),
]
_CG.CGGetDisplayTransferByTable.restype = CGError
_CG.CGSetDisplayTransferByTable.argtypes = [
    CGDirectDisplayID,
    CGTableCount,
    POINTER(CGGammaValue),
    POINTER(CGGammaValue),
    POINTER(CGGammaValue),
]
_CG.CGSetDisplayTransferByTable.restype = CGError
_CG.CGDisplayRestoreColorSyncSettings.argtypes = []
_CG.CGDisplayRestoreColorSyncSettings.restype = None


def _unit_ramp(values):
    return [min(1.0, max(0.0, v / 65535.0)) for v in values]


def _identity_unit(size):
    last = max(size - 1, 1)
    return [i / last for i in range(size)]


def _copy_table(src, count):
    dst = (CGGammaValue * count)()
    for i in range(count):
        dst[i] = src[i]
    return dst


class MacOSBackend:
    def __init__(self):
        self._displays = []
        self._enumerate()

    def _enumerate(self):
        count = CGDisplayCount(0)
        err = _CG.CGGetActiveDisplayList(0, None, byref(count))
        if err != kCGErrorSuccess or count.value == 0:
            log.warning("CGGetActiveDisplayList failed: %s", err)
            return
        ids = (CGDirectDisplayID * count.value)()
        err = _CG.CGGetActiveDisplayList(count.value, ids, byref(count))
        if err != kCGErrorSuccess:
            log.warning("CGGetActiveDisplayList fill failed: %s", err)
            return
        for i in range(count.value):
            display_id = ids[i]
            capacity = int(_CG.CGDisplayGammaTableCapacity(display_id) or 0)
            if capacity <= 0:
                capacity = 256
            red = (CGGammaValue * capacity)()
            green = (CGGammaValue * capacity)()
            blue = (CGGammaValue * capacity)()
            sample = CGTableCount(0)
            saved = None
            err = _CG.CGGetDisplayTransferByTable(
                display_id, capacity, red, green, blue, byref(sample),
            )
            sample_count = int(sample.value or 0)
            if err == kCGErrorSuccess and sample_count > 0:
                saved = {
                    "size": sample_count,
                    "red": _copy_table(red, sample_count),
                    "green": _copy_table(green, sample_count),
                    "blue": _copy_table(blue, sample_count),
                }
            else:
                log.warning(
                    "CGGetDisplayTransferByTable failed for display %s",
                    display_id,
                )
            self._displays.append({
                "id": display_id,
                "capacity": capacity,
                "original": saved,
            })
        log.info(
            "macOS displays: %s",
            [d["id"] for d in self._displays],
        )

    def _set_table(self, display_id, red, green, blue):
        size = len(red)
        rt = (CGGammaValue * size)(*red)
        gt = (CGGammaValue * size)(*green)
        bt = (CGGammaValue * size)(*blue)
        return _CG.CGSetDisplayTransferByTable(
            display_id, size, rt, gt, bt,
        ) == kCGErrorSuccess

    def apply(self, temp, gamma, mode=0):
        any_ok = False
        for d in self._displays:
            size = d["capacity"]
            r, g, b = build_ramp(int(temp), float(gamma), 1.0, int(mode), size)
            ru, gu, bu = _unit_ramp(r), _unit_ramp(g), _unit_ramp(b)
            if self._set_table(d["id"], ru, gu, bu):
                any_ok = True
                continue
            cr, cg, cb = clip_ramp_endpoints(r, g, b)
            ru, gu, bu = _unit_ramp(cr), _unit_ramp(cg), _unit_ramp(cb)
            if self._set_table(d["id"], ru, gu, bu):
                any_ok = True
                log.warning(
                    "CGSetDisplayTransferByTable used clipped endpoints on %s",
                    d["id"],
                )
            else:
                log.warning(
                    "CGSetDisplayTransferByTable failed on %s",
                    d["id"],
                )
        return any_ok

    def reset(self):
        for d in self._displays:
            original = d.get("original")
            ok = False
            if original is not None:
                ok = self._set_table(
                    d["id"],
                    original["red"],
                    original["green"],
                    original["blue"],
                )
            if not ok:
                ident = _identity_unit(d["capacity"])
                if not self._set_table(d["id"], ident, ident, ident):
                    _CG.CGDisplayRestoreColorSyncSettings()

    def close(self):
        self.reset()
        self._displays.clear()
