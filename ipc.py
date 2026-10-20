import logging
import os
import socket
import sys
import threading
import time

from platform_support import is_windows

log = logging.getLogger("gamma_slider")

PIPE_NAME = "\\\\.\\pipe\\GammaSliderX11"
_COMMANDS = ("warmer", "cooler", "toggle")


def socket_path():
    if is_windows():
        return PIPE_NAME
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return os.path.join(runtime, "gamma-slider.sock")
    return os.path.expanduser("~/.local/share/gamma-slider/gamma-slider.sock")


def parse_cli(argv):
    argv = [a for a in argv if a]
    if not argv:
        return None
    if len(argv) == 1 and argv[0] in ("--warmer", "--cooler", "--toggle"):
        return argv[0][2:]
    if len(argv) == 2 and argv[0] == "--temp":
        try:
            value = int(argv[1])
        except ValueError:
            _usage()
        return "temp %d" % value
    if argv[0].startswith("--"):
        _usage()
    log.warning("Ignoring extra arguments: %s", argv)
    return None


def _usage():
    print("usage: app.py [--warmer|--cooler|--toggle|--temp N]", file=sys.stderr)
    raise SystemExit(2)


def send_command(line, timeout=1.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            _send_once(line)
            return True
        except OSError as exc:
            last = exc
            time.sleep(0.05)
    log.info("IPC send failed: %s", last)
    return False


def _send_once(line):
    payload = (line + "\n").encode("utf-8")
    if is_windows():
        _send_windows(payload)
        return
    path = socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.4)
        sock.connect(path)
        sock.sendall(payload)
    finally:
        sock.close()


def _send_windows(payload):
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitNamedPipeW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong]
    kernel32.WaitNamedPipeW.restype = ctypes.c_int
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
        ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.WriteFile.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    if not kernel32.WaitNamedPipeW(PIPE_NAME, 50):
        raise OSError("pipe not ready")
    handle = kernel32.CreateFileW(PIPE_NAME, 0x40000000, 0, None, 3, 0, None)
    invalid = ctypes.c_void_p(-1).value
    if not handle or handle == invalid:
        raise OSError("open pipe failed")
    written = ctypes.c_ulong()
    ok = kernel32.WriteFile(handle, payload, len(payload), ctypes.byref(written), None)
    kernel32.CloseHandle(handle)
    if not ok:
        raise OSError("write pipe failed")


class IpcServer:
    def __init__(self, out_queue):
        self.out_queue = out_queue
        self._stop = threading.Event()
        self._thread = None
        self._listen_sock = None

    def start(self):
        target = self._serve_windows if is_windows() else self._serve_unix
        self._thread = threading.Thread(target=target, name="gamma-ipc", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        sock = self._listen_sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        try:
            _send_once("")
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._unlink()

    def _unlink(self):
        if is_windows():
            return
        path = socket_path()
        if os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass

    def _emit(self, line):
        line = (line or "").strip()
        if not line or self._stop.is_set():
            return
        head = line.split(None, 1)[0]
        if head not in _COMMANDS and head != "temp":
            log.warning("Ignored IPC line: %s", line)
            return
        self.out_queue.put(line)

    def _serve_unix(self):
        path = socket_path()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(path):
            try:
                os.unlink(path)
            except OSError as exc:
                log.warning("Could not unlink stale socket: %s", exc)
                return
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listen_sock = sock
        try:
            sock.bind(path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            sock.listen(4)
            sock.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    conn, _ = sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    conn.settimeout(1.0)
                    data = b""
                    while b"\n" not in data and len(data) < 128:
                        chunk = conn.recv(128)
                        if not chunk:
                            break
                        data += chunk
                    self._emit(data.split(b"\n", 1)[0].decode("utf-8", "replace"))
                except OSError:
                    pass
                finally:
                    try:
                        conn.close()
                    except OSError:
                        pass
        except OSError as exc:
            log.warning("IPC listen failed: %s", exc)
        finally:
            self._listen_sock = None
            try:
                sock.close()
            except OSError:
                pass

    def _serve_windows(self):
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateNamedPipeW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
        ]
        kernel32.CreateNamedPipeW.restype = ctypes.c_void_p
        kernel32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.ConnectNamedPipe.restype = ctypes.c_int
        kernel32.ReadFile.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
        ]
        kernel32.ReadFile.restype = ctypes.c_int
        kernel32.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
        kernel32.DisconnectNamedPipe.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        invalid = ctypes.c_void_p(-1).value
        pipe_mode = 0x00000008
        while not self._stop.is_set():
            handle = kernel32.CreateNamedPipeW(
                PIPE_NAME, 0x00000001, pipe_mode, 1, 256, 256, 0, None,
            )
            if not handle or handle == invalid:
                log.warning("CreateNamedPipe failed: %s", ctypes.get_last_error())
                return
            connected = kernel32.ConnectNamedPipe(handle, None)
            if not connected and ctypes.get_last_error() != 535:
                kernel32.CloseHandle(handle)
                if self._stop.is_set():
                    return
                continue
            buf = ctypes.create_string_buffer(256)
            read = ctypes.c_ulong()
            ok = kernel32.ReadFile(handle, buf, 255, ctypes.byref(read), None)
            if ok and read.value:
                self._emit(buf.raw[:read.value].decode("utf-8", "replace"))
            kernel32.DisconnectNamedPipe(handle)
            kernel32.CloseHandle(handle)
