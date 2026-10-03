import ctypes
import ctypes.util
import logging
import os
import queue
import select
import sys
import threading

log = logging.getLogger("gamma_slider")

HOTKEY_UP = 1
HOTKEY_DOWN = 2

_MOD_KEYS = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
}
_REJECTED_MODS = {"super", "win", "meta", "cmd", "command"}
_ALIASES = {
    "pgup": "PgUp",
    "pageup": "PgUp",
    "prior": "PgUp",
    "pgdown": "PgDown",
    "pagedown": "PgDown",
    "pgdn": "PgDown",
    "next": "PgDown",
    "home": "Home",
    "end": "End",
    "insert": "Insert",
    "ins": "Insert",
    "delete": "Delete",
    "del": "Delete",
    "left": "Left",
    "up": "Up",
    "right": "Right",
    "down": "Down",
    "space": "Space",
    "tab": "Tab",
    "esc": "Escape",
    "escape": "Escape",
    "return": "Return",
    "enter": "Return",
}

_WIN_VK = {
    "PgUp": 0x21,
    "PgDown": 0x22,
    "End": 0x23,
    "Home": 0x24,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "Insert": 0x2D,
    "Delete": 0x2E,
    "Space": 0x20,
    "Tab": 0x09,
    "Escape": 0x1B,
    "Return": 0x0D,
}
_MAC_KEY = {
    "A": 0x00, "S": 0x01, "D": 0x02, "F": 0x03, "H": 0x04, "G": 0x05,
    "Z": 0x06, "X": 0x07, "C": 0x08, "V": 0x09, "B": 0x0B, "Q": 0x0C,
    "W": 0x0D, "E": 0x0E, "R": 0x0F, "Y": 0x10, "T": 0x11,
    "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17,
    "9": 0x19, "7": 0x1A, "8": 0x1C, "0": 0x1D,
    "O": 0x1F, "U": 0x20, "I": 0x22, "P": 0x23, "Return": 0x24,
    "L": 0x25, "J": 0x26, "K": 0x28, "N": 0x2D, "M": 0x2E,
    "Tab": 0x30, "Space": 0x31, "Escape": 0x35, "Delete": 0x75,
    "Home": 0x73, "PgUp": 0x74, "End": 0x77, "PgDown": 0x79,
    "Left": 0x7B, "Right": 0x7C, "Down": 0x7D, "Up": 0x7E,
    "F1": 0x7A, "F2": 0x78, "F3": 0x63, "F4": 0x76, "F5": 0x60,
    "F6": 0x61, "F7": 0x62, "F8": 0x64, "F9": 0x65, "F10": 0x6D,
    "F11": 0x67, "F12": 0x6F,
}
_X_KEYSYM = {
    "PgUp": 0xFF55,
    "PgDown": 0xFF56,
    "Home": 0xFF50,
    "End": 0xFF57,
    "Insert": 0xFF63,
    "Delete": 0xFFFF,
    "Left": 0xFF51,
    "Up": 0xFF52,
    "Right": 0xFF53,
    "Down": 0xFF54,
    "Space": 0x0020,
    "Tab": 0xFF09,
    "Escape": 0xFF1B,
    "Return": 0xFF0D,
}
_X_KEYSYM_EXTRA = {
    "PgUp": (0xFF9A,),
    "PgDown": (0xFF9B,),
    "Home": (0xFF95,),
    "End": (0xFF9C,),
    "Left": (0xFF96,),
    "Up": (0xFF97,),
    "Right": (0xFF98,),
    "Down": (0xFF99,),
    "Insert": (0xFF9E,),
    "Delete": (0xFF9F,),
}

for _i in range(1, 13):
    _WIN_VK["F%d" % _i] = 0x6F + _i
    _X_KEYSYM["F%d" % _i] = 0xFFBD + _i
for _i, _ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _WIN_VK[_ch] = 0x41 + _i
    _X_KEYSYM[_ch] = 0x41 + _i
for _i in range(10):
    _WIN_VK[str(_i)] = 0x30 + _i
    _X_KEYSYM[str(_i)] = 0x30 + _i


def canonical_key(name):
    if not name:
        return None
    low = name.strip().lower()
    if low in _ALIASES:
        return _ALIASES[low]
    if len(low) >= 2 and low[0] == "f" and low[1:].isdigit():
        number = int(low[1:])
        if 1 <= number <= 12:
            return "F%d" % number
    if len(low) == 1 and low.isdigit():
        return low
    if len(low) == 1 and low.isalpha():
        return low.upper()
    return None


def usable_hotkey(spec):
    parsed = parse_hotkey(spec)
    if not parsed or not parsed[0]:
        return None
    return parsed


def parse_hotkey(spec):
    if not isinstance(spec, str) or not spec.strip():
        return None
    mods = set()
    key = None
    for part in spec.split("+"):
        token = part.strip()
        if not token:
            return None
        low = token.lower()
        if low in _REJECTED_MODS:
            return None
        if low in _MOD_KEYS:
            mods.add(_MOD_KEYS[low])
            continue
        if key is not None:
            return None
        key = canonical_key(token)
        if key is None:
            return None
    if key is None:
        return None
    return mods, key


def linux_grab_skipped():
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def register_win(hwnd, hotkey_id, spec):
    parsed = usable_hotkey(spec)
    if not parsed:
        log.warning("Invalid hotkey: %s", spec)
        return False
    mods, key = parsed
    vk = _WIN_VK.get(key)
    if not vk:
        log.warning("Unsupported hotkey key: %s", key)
        return False
    mask = 0x4000
    if "ctrl" in mods:
        mask |= 0x0002
    if "alt" in mods:
        mask |= 0x0001
    if "shift" in mods:
        mask |= 0x0004
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.RegisterHotKey.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
    ]
    user32.RegisterHotKey.restype = ctypes.c_int
    ok = user32.RegisterHotKey(ctypes.c_void_p(hwnd), int(hotkey_id), mask, vk)
    if not ok:
        log.warning("RegisterHotKey failed for %s (error %s)", spec, ctypes.get_last_error())
    return bool(ok)


def unregister_win(hwnd):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.UnregisterHotKey.restype = ctypes.c_int
    for hotkey_id in (HOTKEY_UP, HOTKEY_DOWN):
        user32.UnregisterHotKey(ctypes.c_void_p(hwnd), hotkey_id)


class HotkeyGrabber:
    def __init__(self):
        self.events = queue.Queue()
        self._impl = None

    def rebind(self, enabled, up, down):
        self.close()
        if not enabled:
            return
        if sys.platform.startswith("linux") and linux_grab_skipped():
            log.info("Hotkey listen skipped (Wayland); use the CLI")
            return
        try:
            if sys.platform == "darwin":
                self._impl = _MacGrab(up, down, self.events)
            elif sys.platform.startswith("linux"):
                self._impl = _LinuxGrab(up, down, self.events)
        except Exception as exc:
            log.warning("Hotkey register failed: %s", exc)
            self._impl = None

    def close(self):
        impl = self._impl
        self._impl = None
        if impl is None:
            return
        try:
            impl.close()
        except Exception as exc:
            log.warning("Hotkey release failed: %s", exc)


class _XRecordRange8(ctypes.Structure):
    _fields_ = [("first", ctypes.c_ubyte), ("last", ctypes.c_ubyte)]


class _XRecordRange16(ctypes.Structure):
    _fields_ = [("first", ctypes.c_ushort), ("last", ctypes.c_ushort)]


class _XRecordExtRange(ctypes.Structure):
    _fields_ = [("ext_major", _XRecordRange8), ("ext_minor", _XRecordRange16)]


class _XRecordRange(ctypes.Structure):
    _fields_ = [
        ("core_requests", _XRecordRange8),
        ("core_replies", _XRecordRange8),
        ("ext_requests", _XRecordExtRange),
        ("ext_replies", _XRecordExtRange),
        ("delivered_events", _XRecordRange8),
        ("device_events", _XRecordRange8),
        ("errors", _XRecordRange8),
        ("client_started", ctypes.c_int),
        ("client_died", ctypes.c_int),
    ]


class _XRecordInterceptData(ctypes.Structure):
    _fields_ = [
        ("id_base", ctypes.c_ulong),
        ("server_time", ctypes.c_ulong),
        ("client_seq", ctypes.c_ulong),
        ("category", ctypes.c_int),
        ("client_swapped", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("data_len", ctypes.c_ulong),
    ]


_MOD_IGNORE = 2 | 16 | 32 | 128


class _LinuxGrab:
    def __init__(self, up, down, out_queue):
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._ctx = 0
        self._chords = []
        self._out = out_queue
        self._cb = None
        self._wake_r, self._wake_w = os.pipe()
        os.set_blocking(self._wake_w, False)
        self._thread = threading.Thread(
            target=self._run, args=(up, down), name="gamma-hotkeys", daemon=True,
        )
        self._thread.start()

    def close(self):
        self._stop.set()
        try:
            os.write(self._wake_w, b"\0")
        except OSError:
            pass
        self._ready.wait(1.0)
        if self._ctx:
            self._disable()
        self._thread.join(timeout=2)
        for fd in (self._wake_r, self._wake_w):
            try:
                os.close(fd)
            except OSError:
                pass

    def _disable(self):
        x11lib = ctypes.util.find_library("X11")
        xtstlib = ctypes.util.find_library("Xtst")
        if not x11lib or not xtstlib:
            return
        x11 = ctypes.cdll.LoadLibrary(x11lib)
        xtst = ctypes.cdll.LoadLibrary(xtstlib)
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XRecordDisableContext.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xtst.XRecordDisableContext.restype = ctypes.c_int
        display = x11.XOpenDisplay(None)
        if not display:
            return
        xtst.XRecordDisableContext(display, self._ctx)
        x11.XFlush(display)
        x11.XCloseDisplay(display)

    def _run(self, up, down):
        try:
            self._listen(up, down)
        except Exception as exc:
            log.warning("Hotkey listen failed: %s", exc)
        finally:
            self._ready.set()

    def _listen(self, up, down):
        x11lib = ctypes.util.find_library("X11")
        xtstlib = ctypes.util.find_library("Xtst")
        if not x11lib or not xtstlib:
            log.warning("XRecord unavailable; hotkey listen disabled")
            return
        x11 = ctypes.cdll.LoadLibrary(x11lib)
        xtst = ctypes.cdll.LoadLibrary(xtstlib)
        self._bind(x11, xtst)
        display = x11.XOpenDisplay(None)
        if not display:
            log.warning("XOpenDisplay failed; hotkey listen unavailable")
            return
        self._resolve(x11, display, "up", up)
        self._resolve(x11, display, "down", down)
        if not self._chords:
            x11.XCloseDisplay(display)
            return
        rec_range = xtst.XRecordAllocRange()
        if not rec_range:
            log.warning("XRecordAllocRange failed")
            x11.XCloseDisplay(display)
            return
        rec_range.contents.device_events.first = 2
        rec_range.contents.device_events.last = 3
        clients = ctypes.c_ulong(3)
        range_array = (ctypes.POINTER(_XRecordRange) * 1)(rec_range)
        ranges = ctypes.cast(range_array, ctypes.POINTER(ctypes.POINTER(_XRecordRange)))
        ctx = xtst.XRecordCreateContext(display, 0, ctypes.byref(clients), 1, ranges, 1)
        if not ctx:
            log.warning("XRecordCreateContext failed")
            x11.XFree(rec_range)
            x11.XCloseDisplay(display)
            return
        self._ctx = ctx
        self._cb = self._callback(xtst)
        status = xtst.XRecordEnableContextAsync(display, ctx, self._cb, None)
        self._ready.set()
        if not status:
            log.warning("XRecordEnableContextAsync failed")
            xtst.XRecordFreeContext(display, ctx)
            x11.XFree(rec_range)
            x11.XCloseDisplay(display)
            self._ctx = 0
            return
        log.info("Hotkeys listening")
        fd = x11.XConnectionNumber(display)
        try:
            while not self._stop.is_set():
                try:
                    ready, _, _ = select.select([fd, self._wake_r], [], [], 0.5)
                except (OSError, ValueError):
                    break
                if self._wake_r in ready:
                    try:
                        os.read(self._wake_r, 64)
                    except OSError:
                        pass
                if fd in ready:
                    xtst.XRecordProcessReplies(display)
                if self._stop.is_set():
                    break
        finally:
            try:
                xtst.XRecordFreeContext(display, ctx)
            except Exception:
                pass
            x11.XFree(rec_range)
            x11.XCloseDisplay(display)
            self._ctx = 0

    def _callback(self, xtst):
        owner = self

        @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(_XRecordInterceptData))
        def cb(closure, data):
            try:
                if not data:
                    return
                rec = data.contents
                if rec.category == 0 and rec.data and rec.data_len:
                    raw = ctypes.string_at(rec.data, int(rec.data_len) * 4)
                    if len(raw) < 2 or raw[0] != 2:
                        return
                    keycode = raw[1]
                    if rec.client_swapped and len(raw) >= 30:
                        state = raw[29] | (raw[28] << 8)
                    elif len(raw) >= 30:
                        state = raw[28] | (raw[29] << 8)
                    else:
                        state = 0
                    name = owner._match(keycode, state)
                    if name:
                        owner._out.put(name)
            except Exception:
                pass
            finally:
                try:
                    xtst.XRecordFreeData(data)
                except Exception:
                    pass

        return cb

    def _match(self, keycode, state):
        state = (state & 0xFF) & ~_MOD_IGNORE
        for name, code, mask in self._chords:
            if keycode == code and state == mask:
                return name
        return None

    def _resolve(self, x11, display, name, spec):
        parsed = usable_hotkey(spec)
        if not parsed:
            log.warning("Invalid hotkey: %s", spec)
            return
        mods, key = parsed
        keysym = _X_KEYSYM.get(key)
        if not keysym:
            log.warning("Unsupported hotkey key: %s", key)
            return
        codes = []
        for ks in (keysym,) + _X_KEYSYM_EXTRA.get(key, ()):
            code = int(x11.XKeysymToKeycode(display, ks))
            if code and code not in codes:
                codes.append(code)
        if not codes:
            log.warning("Hotkey listen skipped for %s", spec)
            return
        mask = 0
        if "shift" in mods:
            mask |= 1
        if "ctrl" in mods:
            mask |= 4
        if "alt" in mods:
            mask |= 8
        for code in codes:
            self._chords.append((name, code, mask))

    def _bind(self, x11, xtst):
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XConnectionNumber.argtypes = [ctypes.c_void_p]
        x11.XConnectionNumber.restype = ctypes.c_int
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_ubyte
        xtst.XRecordAllocRange.argtypes = []
        xtst.XRecordAllocRange.restype = ctypes.POINTER(_XRecordRange)
        xtst.XRecordCreateContext.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_int, ctypes.POINTER(ctypes.POINTER(_XRecordRange)), ctypes.c_int,
        ]
        xtst.XRecordCreateContext.restype = ctypes.c_ulong
        xtst.XRecordEnableContextAsync.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p,
        ]
        xtst.XRecordEnableContextAsync.restype = ctypes.c_int
        xtst.XRecordProcessReplies.argtypes = [ctypes.c_void_p]
        xtst.XRecordProcessReplies.restype = None
        xtst.XRecordDisableContext.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xtst.XRecordDisableContext.restype = ctypes.c_int
        xtst.XRecordFreeContext.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xtst.XRecordFreeContext.restype = ctypes.c_int
        xtst.XRecordFreeData.argtypes = [ctypes.POINTER(_XRecordInterceptData)]
        xtst.XRecordFreeData.restype = None


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("hid", ctypes.c_uint32)]


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


_CARBON_HANDLER = None
_carbon_queue = None


def _keep_carbon_handler(handler):
    global _CARBON_HANDLER
    _CARBON_HANDLER = handler
    return handler


class _MacGrab:
    def __init__(self, up, down, out_queue):
        self._refs = []
        self._handler_ref = ctypes.c_void_p()
        self._carbon = None
        self._install(up, down, out_queue)

    def close(self):
        carbon = self._carbon
        if carbon is None:
            return
        for ref in self._refs:
            try:
                carbon.UnregisterEventHotKey(ref)
            except Exception:
                pass
        self._refs = []
        if self._handler_ref:
            try:
                carbon.RemoveEventHandler(self._handler_ref)
            except Exception:
                pass
            self._handler_ref = ctypes.c_void_p()

    def _install(self, up, down, out_queue):
        global _carbon_queue
        path = "/System/Library/Frameworks/Carbon.framework/Carbon"
        if not os.path.exists(path):
            found = ctypes.util.find_library("Carbon")
            path = found or ""
        if not path:
            log.warning("Carbon.framework not found; hotkey grab unavailable")
            return
        try:
            carbon = ctypes.cdll.LoadLibrary(path)
        except OSError as exc:
            log.warning("Carbon load failed: %s", exc)
            return
        self._bind_carbon(carbon)
        self._carbon = carbon
        _carbon_queue = out_queue
        handler = _keep_carbon_handler(_carbon_hotkey_handler(carbon))
        spec = _EventTypeSpec(0x6B657962, 6)
        status = carbon.InstallApplicationEventHandler(
            handler, 1, ctypes.byref(spec), None, ctypes.byref(self._handler_ref),
        )
        if status != 0:
            log.warning("InstallApplicationEventHandler failed: %s", status)
            return
        target = carbon.GetApplicationEventTarget()
        for name, spec_text, hotkey_id in (("up", up, HOTKEY_UP), ("down", down, HOTKEY_DOWN)):
            parsed = usable_hotkey(spec_text)
            if not parsed:
                log.warning("Invalid hotkey: %s", spec_text)
                continue
            mods, key = parsed
            code = _MAC_KEY.get(key)
            if code is None:
                log.warning("Unsupported hotkey key: %s", key)
                continue
            mask = 0
            if "ctrl" in mods:
                mask |= 1 << 12
            if "alt" in mods:
                mask |= 1 << 11
            if "shift" in mods:
                mask |= 1 << 9
            ref = ctypes.c_void_p()
            hot_id = _EventHotKeyID(0x47534C44, hotkey_id)
            status = carbon.RegisterEventHotKey(
                code, mask, hot_id, target, 0, ctypes.byref(ref),
            )
            if status != 0 or not ref:
                log.warning("RegisterEventHotKey failed for %s: %s", spec_text, status)
                continue
            self._refs.append(ref)
        if not self._refs:
            self.close()

    def _bind_carbon(self, carbon):
        carbon.RegisterEventHotKey.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ]
        carbon.RegisterEventHotKey.restype = ctypes.c_int
        carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        carbon.UnregisterEventHotKey.restype = ctypes.c_int
        carbon.GetApplicationEventTarget.argtypes = []
        carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        carbon.InstallApplicationEventHandler.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_EventTypeSpec),
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]
        carbon.InstallApplicationEventHandler.restype = ctypes.c_int
        carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
        carbon.RemoveEventHandler.restype = ctypes.c_int
        carbon.GetEventParameter.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
        ]
        carbon.GetEventParameter.restype = ctypes.c_int


def _carbon_hotkey_handler(carbon):
    @ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    def handler(next_handler, event, user_data):
        hot_id = _EventHotKeyID()
        status = carbon.GetEventParameter(
            event, 0x2D2D2D2D, 0x686B6964, None,
            ctypes.sizeof(hot_id), None, ctypes.byref(hot_id),
        )
        if status != 0 or hot_id.signature != 0x47534C44:
            return -9874
        name = "up" if hot_id.hid == HOTKEY_UP else "down" if hot_id.hid == HOTKEY_DOWN else None
        if name and _carbon_queue is not None:
            _carbon_queue.put(name)
        return 0 if name else -9874

    return handler
