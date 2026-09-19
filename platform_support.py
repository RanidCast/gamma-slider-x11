import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def is_frozen():
    return getattr(sys, "frozen", False)


def is_windows():
    return sys.platform == "win32"


def is_linux():
    return sys.platform.startswith("linux")


class Paths:
    def __init__(self):
        if is_windows():
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            local = os.environ.get("LOCALAPPDATA") or appdata
            self.config_dir = os.path.join(appdata, "gamma-slider")
            self.log_dir = os.path.join(local, "gamma-slider")
            self.data_dir = self.log_dir
            self.config_file = os.path.join(self.config_dir, "gamma_slider.conf")
            self.log_file = os.path.join(self.log_dir, "gamma_slider.log")
            self.engine = None
            self.autostart_file = None
            self.menu_file = None
        else:
            self.data_dir = os.path.expanduser("~/.local/share/gamma-slider")
            self.config_dir = os.path.expanduser("~/.config/gamma-slider")
            self.log_dir = self.data_dir
            self.config_file = os.path.join(self.config_dir, "gamma_slider.conf")
            self.log_file = os.path.join(self.data_dir, "gamma_slider.log")
            self.engine = os.path.join(self.data_dir, "gamma-engine")
            self.autostart_file = os.path.expanduser(
                "~/.config/autostart/gamma-slider-x11.desktop"
            )
            self.menu_file = os.path.expanduser(
                "~/.local/share/applications/gamma-slider-x11.desktop"
            )

    def ensure(self):
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        if self.data_dir and self.data_dir not in (self.config_dir, self.log_dir):
            os.makedirs(self.data_dir, exist_ok=True)


paths = Paths()

_lock_handle = None
_mutex_handle = None

WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WIN_RUN_NAME = "GammaSlider"
ERROR_ALREADY_EXISTS = 183


def setup_logging():
    paths.ensure()
    handler = RotatingFileHandler(paths.log_file, maxBytes=1 * 1024 * 1024, backupCount=2)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger = logging.getLogger("gamma_slider")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


def acquire_single_instance():
    global _lock_handle, _mutex_handle
    if is_windows():
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, True, "GammaSliderX11")
        _mutex_handle = handle
        if not handle:
            return True
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    import fcntl

    _lock_handle = open("/tmp/gamma_slider.lock", "w")
    try:
        fcntl.lockf(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _windows_autostart_command():
    if is_frozen():
        return '"%s"' % sys.executable
    exe = sys.executable
    directory, name = os.path.split(exe)
    lower = name.lower()
    if lower.startswith("python") and lower.endswith(".exe") and not lower.startswith("pythonw"):
        pythonw = os.path.join(directory, "pythonw.exe")
        if os.path.isfile(pythonw):
            exe = pythonw
    script = os.path.abspath(sys.argv[0])
    return '"%s" "%s"' % (exe, script)


def _linux_desktop_files():
    return (
        paths.autostart_file,
        paths.menu_file,
        os.path.expanduser("~/.config/autostart/gamma_slider.desktop"),
        os.path.expanduser("~/.local/share/applications/gamma_slider.desktop"),
    )


def is_autostart_enabled():
    if is_windows():
        import winreg

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, WIN_RUN_NAME)
                return True
            finally:
                winreg.CloseKey(key)
        except OSError:
            return False
    return any(p and os.path.exists(p) for p in _linux_desktop_files())


def enable_autostart():
    log = logging.getLogger("gamma_slider")
    if is_windows():
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(
                key, WIN_RUN_NAME, 0, winreg.REG_SZ, _windows_autostart_command(),
            )
        finally:
            winreg.CloseKey(key)
        log.info("Autostart enabled")
        return
    p_bin = os.path.abspath(sys.argv[0])
    d = (
        "[Desktop Entry]\nType=Application\nName=Gamma Slider\n"
        "Exec=python3 %s\nIcon=weather-clear\nCategories=Settings;\nTerminal=false\n"
        % p_bin
    )
    for p in (paths.autostart_file, paths.menu_file):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(d)
    log.info("Autostart enabled")


def disable_autostart():
    log = logging.getLogger("gamma_slider")
    if is_windows():
        import winreg

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, WIN_RUN_NAME)
            finally:
                winreg.CloseKey(key)
        except OSError:
            pass
        log.info("Autostart removed")
        return
    for p in _linux_desktop_files():
        if p and os.path.exists(p):
            os.remove(p)
            log.info("Autostart removed: %s", p)


def toggle_autostart():
    if is_autostart_enabled():
        disable_autostart()
    else:
        enable_autostart()
