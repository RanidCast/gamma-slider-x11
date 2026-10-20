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
    "PgUp": (0xFF9A, 0xFFB9),
    "PgDown": (0xFF9B, 0xFFB3),
    "Home": (0xFF95, 0xFFB7),
    "End": (0xFF9C, 0xFFB1),
    "Left": (0xFF96, 0xFFB4),
    "Up": (0xFF97, 0xFFB8),
    "Right": (0xFF98, 0xFFB6),
    "Down": (0xFF99, 0xFFB2),
    "Insert": (0xFF9E, 0xFFB0),
    "Delete": (0xFF9F, 0xFFAE),
}
_QT_KEYPAD = 0x20000000
_QT_MOD_BITS = 0x02000000 | 0x04000000 | 0x08000000 | 0x10000000 | 0x20000000
_NUMPAD_DIGIT_KEYS = {
    "PgUp": 0x39,
    "PgDown": 0x33,
    "Home": 0x37,
    "End": 0x31,
    "Insert": 0x30,
    "Delete": 0x2E,
    "Left": 0x34,
    "Up": 0x38,
    "Right": 0x36,
    "Down": 0x32,
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
    mask = 0
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


class KDEGlobalShortcuts:
    COMPONENT = "gamma-slider-x11"
    ACTIONS = {
        "warmer": ("warmer", "Gamma Slider X11", "Warmer"),
        "cooler": ("cooler", "Gamma Slider X11", "Cooler"),
    }
    SET_PRESENT = 2
    NO_AUTOLOADING = 4

    def __init__(self, events):
        self.events = events
        self.bus = None
        self.interface = None
        self.component = None
        self.available = False
        self.action_ids = {}
        self._signal_matches = []
        try:
            from dbus.mainloop.pyqt5 import DBusQtMainLoop
            import dbus

            DBusQtMainLoop(set_as_default=True)
            self.dbus = dbus
            self.bus = dbus.SessionBus()
            self.interface = dbus.Interface(
                self.bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"),
                "org.kde.KGlobalAccel",
            )
            for action_key, (action_name, component_title, action_title) in self.ACTIONS.items():
                action_id = dbus.Array(
                    [self.COMPONENT, action_name, component_title, action_title], signature="s",
                )
                self.interface.doRegister(action_id)
                self.action_ids[action_key] = action_id

            component_path = self.interface.getComponent(self.COMPONENT)
            self.component = dbus.Interface(
                self.bus.get_object("org.kde.kglobalaccel", component_path),
                "org.kde.kglobalaccel.Component",
            )
            self._signal_matches.append(
                self.component.connect_to_signal("globalShortcutPressed", self._pressed)
            )
            self._signal_matches.append(
                self.component.connect_to_signal("globalShortcutRepeated", self._pressed)
            )
            self._signal_matches.append(
                self.bus.add_signal_receiver(
                    self._shortcuts_changed,
                    signal_name="yourShortcutsChanged",
                    dbus_interface="org.kde.KGlobalAccel",
                    path="/kglobalaccel",
                )
            )
            self.available = True
            log.info("KGlobalAccel ready (%s)", self.COMPONENT)
        except Exception:
            log.exception("KGlobalAccel initialization failed")
            self.close()

    @staticmethod
    def _qt_sequence(spec):
        try:
            from PyQt5.QtGui import QKeySequence
        except ImportError:
            try:
                from PyQt6.QtGui import QKeySequence
            except ImportError:
                return 0
        sequence = QKeySequence(str(spec))
        if sequence.count() != 1:
            return 0
        key = sequence[0]
        return key.toCombined() if hasattr(key, "toCombined") else int(key)

    @classmethod
    def _qt_sequences(cls, spec):
        base = cls._qt_sequence(spec)
        if not base:
            return []
        parsed = parse_hotkey(spec)
        if not parsed:
            return [base]
        mods, name = parsed
        digit = _NUMPAD_DIGIT_KEYS.get(name)
        if digit is None:
            return [base]
        mask = 0
        if "shift" in mods:
            mask |= 0x02000000
        if "ctrl" in mods:
            mask |= 0x04000000
        if "alt" in mods:
            mask |= 0x08000000
        qt_key = base & ~_QT_MOD_BITS
        keys = []
        for extra in (qt_key, digit):
            combo = mask | _QT_KEYPAD | extra
            if combo not in keys:
                keys.append(combo)
        if base not in keys:
            keys.append(base)
        return keys

    @staticmethod
    def _sequence_text(key):
        try:
            from PyQt5.QtGui import QKeySequence
            sequence_format = QKeySequence.PortableText
        except ImportError:
            from PyQt6.QtGui import QKeySequence
            sequence_format = QKeySequence.SequenceFormat.PortableText
        return QKeySequence(int(key)).toString(sequence_format)

    def _action_keys(self, action_key):
        if self.interface is None:
            return []
        return [int(key) for key in self.interface.shortcut(self.action_ids[action_key])]

    def rebind(self, enabled, up, down, force=False):
        if self.interface is None:
            return {}
        requested = {"warmer": up, "cooler": down}
        assigned = {}
        for action_key, spec in requested.items():
            action_id = self.action_ids[action_key]
            current = [key for key in self._action_keys(action_key) if key]
            wanted = self._qt_sequences(spec)
            if force or not current or set(current) <= set(wanted):
                keys = wanted or current
                replace = bool(wanted) and (force or set(current) != set(wanted))
            else:
                keys = current
                replace = False
            if keys:
                bind_flags = 0
                if enabled:
                    bind_flags = self.SET_PRESENT
                    if replace:
                        bind_flags |= self.NO_AUTOLOADING
                result = self.interface.setShortcut(
                    action_id,
                    self.dbus.Array([self.dbus.Int32(key) for key in keys], signature="i"),
                    self.dbus.UInt32(bind_flags),
                )
                current = [int(item) for item in result if int(item)]
            if current:
                assigned[action_key] = self._sequence_text(current[0])
            if not enabled:
                self.interface.setInactive(action_id)
        try:
            active = bool(self.component.isActive()) if self.component is not None else False
        except Exception:
            active = False
        log.info(
            "KGlobalAccel rebind enabled=%s active=%s assigned=%s",
            enabled, active, assigned,
        )
        return assigned

    def _pressed(self, component_name, action_name, timestamp):
        if component_name != self.COMPONENT:
            return
        event = {"warmer": "up", "cooler": "down"}.get(str(action_name))
        if event:
            self.events.put(event)

    def _shortcuts_changed(self, action_id, key_sequences):
        if len(action_id) < 2 or str(action_id[0]) != self.COMPONENT:
            return
        action_key = {value[0]: key for key, value in self.ACTIONS.items()}.get(str(action_id[1]))
        if action_key is None:
            return
        keys = list(key_sequences)
        text = self._sequence_text(keys[0][0]) if keys and keys[0] else ""
        self.events.put(("kde-binding", action_key, text))

    def configure(self):
        if self.component is None:
            return False
        try:
            self.component.invokeShortcut("configure")
            return True
        except Exception as exc:
            log.info("No KDE shortcut configuration action: %s", exc)
            return False

    def close(self):
        if self.interface is not None:
            for action_id in self.action_ids.values():
                try:
                    self.interface.setInactive(action_id)
                except Exception:
                    pass
        for match in self._signal_matches:
            try:
                match.remove()
            except Exception:
                pass
        self._signal_matches.clear()
        self.available = False


class _XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


_XErrorHandler = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_XErrorEvent),
)


_MOD_IGNORE = 2 | 16 | 32 | 128
_LOCK_MODIFIERS = (2, 16, 32, 128)
_KEY_PRESS = 2
_BAD_ACCESS = 10
_X_GRAB_KEY_REQUEST = 33


class _LinuxGrab:
    def __init__(self, up, down, out_queue):
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._display = None
        self._x11 = None
        self._root = 0
        self._chords = []
        self._grabs = []
        self._out = out_queue
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
        self._thread.join(timeout=2)
        for fd in (self._wake_r, self._wake_w):
            try:
                os.close(fd)
            except OSError:
                pass

    def _run(self, up, down):
        try:
            self._listen(up, down)
        except Exception as exc:
            log.warning("Hotkey listen failed: %s", exc)
        finally:
            self._ready.set()

    def _listen(self, up, down):
        x11lib = ctypes.util.find_library("X11")
        if not x11lib:
            log.warning("X11 library unavailable; hotkey listen disabled")
            return
        x11 = ctypes.cdll.LoadLibrary(x11lib)
        self._bind(x11)
        display = x11.XOpenDisplay(None)
        if not display:
            log.warning("XOpenDisplay failed; hotkey listen unavailable")
            return
        self._display = display
        self._x11 = x11
        self._root = x11.XDefaultRootWindow(display)
        self._resolve(x11, display, "up", up)
        self._resolve(x11, display, "down", down)
        self._register_grabs()
        self._ready.set()
        if not self._grabs:
            log.warning("No Linux hotkeys registered")
            x11.XCloseDisplay(display)
            self._display = None
            return
        log.info("Global X11 hotkeys listening")
        fd = x11.XConnectionNumber(display)
        event_buffer = ctypes.create_string_buffer(192)
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
                    while x11.XPending(display):
                        x11.XNextEvent(display, event_buffer)
                        event = ctypes.cast(
                            event_buffer, ctypes.POINTER(_XKeyEvent),
                        ).contents
                        if event.type == _KEY_PRESS:
                            name = self._match(event.keycode, event.state)
                            if name:
                                self._out.put(name)
                if self._stop.is_set():
                    break
        finally:
            try:
                for keycode, modifiers in self._grabs:
                    x11.XUngrabKey(display, keycode, modifiers, self._root)
                x11.XSync(display, 0)
            except Exception:
                pass
            x11.XCloseDisplay(display)
            self._grabs.clear()
            self._display = None

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

    def _register_grabs(self):
        if not self._chords:
            return

        display = self._display
        x11 = self._x11
        errors = []
        old_handler = ctypes.c_void_p()

        @_XErrorHandler
        def on_x_error(error_display, error):
            event = error.contents
            if (
                error_display == display
                and event.request_code == _X_GRAB_KEY_REQUEST
                and event.error_code == _BAD_ACCESS
            ):
                errors.append((event.resourceid, event.minor_code))
                return 0
            if old_handler.value:
                previous = ctypes.cast(old_handler, _XErrorHandler)
                return previous(error_display, error)
            return 0

        x11.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        x11.XSetErrorHandler.restype = ctypes.c_void_p
        x11.XGrabKey.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong,
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ]
        x11.XGrabKey.restype = ctypes.c_int

        old_handler = ctypes.c_void_p(
            x11.XSetErrorHandler(ctypes.cast(on_x_error, ctypes.c_void_p)),
        )
        try:
            for _, keycode, modifiers in self._chords:
                for ignored in range(1 << len(_LOCK_MODIFIERS)):
                    lock_mask = 0
                    for bit, modifier in enumerate(_LOCK_MODIFIERS):
                        if ignored & (1 << bit):
                            lock_mask |= modifier
                    grab_modifiers = modifiers | lock_mask
                    x11.XGrabKey(
                        display, keycode, grab_modifiers, self._root,
                        0, 1, 1,
                    )
                    self._grabs.append((keycode, grab_modifiers))
            x11.XSync(display, 0)
        finally:
            x11.XSetErrorHandler(old_handler)
            del on_x_error

        if errors:
            log.warning(
                "Some X11 hotkey grabs are unavailable; another application "
                "may own the chord (%d conflicts)", len(errors),
            )
        registered = len(self._grabs) - len(errors)
        if registered <= 0:
            self._grabs.clear()
            log.warning("Hotkey chords are already grabbed by another X11 client")
        x11.XFlush(display)

    def _bind(self, x11):
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XConnectionNumber.argtypes = [ctypes.c_void_p]
        x11.XConnectionNumber.restype = ctypes.c_int
        x11.XPending.argtypes = [ctypes.c_void_p]
        x11.XPending.restype = ctypes.c_int
        x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        x11.XNextEvent.restype = ctypes.c_int
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XSync.restype = ctypes.c_int
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XUngrabKey.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong,
        ]
        x11.XUngrabKey.restype = ctypes.c_int
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_ubyte


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
        specs = (_EventTypeSpec * 2)(
            _EventTypeSpec(0x6B657962, 5),
            _EventTypeSpec(0x6B657962, 6),
        )
        status = carbon.InstallApplicationEventHandler(
            handler, len(specs), specs, None, ctypes.byref(self._handler_ref),
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
        carbon.GetEventKind.argtypes = [ctypes.c_void_p]
        carbon.GetEventKind.restype = ctypes.c_uint32


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
            kind = carbon.GetEventKind(event)
            action = "pressed" if kind == 5 else "released" if kind == 6 else None
            if action:
                _carbon_queue.put((action, name))
        return 0 if name else -9874

    return handler
