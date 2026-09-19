#!/usr/bin/env python3
import sys
import os
import logging
import ctypes
import ctypes.util
import time
from datetime import datetime

from platform_support import (
    paths,
    setup_logging,
    acquire_single_instance,
    is_autostart_enabled,
    toggle_autostart,
    is_linux,
)

try:
    from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSlider,
                                 QLabel, QSystemTrayIcon, QMenu, QCheckBox,
                                 QHBoxLayout, QComboBox, QPushButton)
    from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QCursor
    from PyQt5.QtCore import Qt, QObject, QTimer, QEvent
    QT_VERSION = 5

    _LEFT_BUTTON    = Qt.LeftButton
    _TRANSPARENT    = Qt.transparent
    _NO_PEN         = Qt.NoPen
    _ALIGN_CENTER   = Qt.AlignCenter
    _HORIZONTAL     = Qt.Horizontal
    _POPUP          = Qt.Tool
    _FRAMELESS      = Qt.FramelessWindowHint
    _STAYS_ON_TOP   = Qt.WindowStaysOnTopHint
    _TRAY_TRIGGER   = QSystemTrayIcon.Trigger
    _TRAY_WARNING   = QSystemTrayIcon.Warning
    _ANTIALIAS      = QPainter.Antialiasing
    _BOLD           = QFont.Bold
    _EXTRABOLD      = QFont.ExtraBold

except ImportError:
    from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSlider,
                                 QLabel, QSystemTrayIcon, QMenu, QCheckBox,
                                 QHBoxLayout, QComboBox, QPushButton)
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QCursor
    from PyQt6.QtCore import Qt, QObject, QTimer, QEvent
    QT_VERSION = 6

    _LEFT_BUTTON    = Qt.MouseButton.LeftButton
    _TRANSPARENT    = Qt.GlobalColor.transparent
    _NO_PEN         = Qt.PenStyle.NoPen
    _ALIGN_CENTER   = Qt.AlignmentFlag.AlignCenter
    _HORIZONTAL     = Qt.Orientation.Horizontal
    _POPUP          = Qt.WindowType.Tool
    _FRAMELESS      = Qt.WindowType.FramelessWindowHint
    _STAYS_ON_TOP   = Qt.WindowType.WindowStaysOnTopHint
    _TRAY_TRIGGER   = QSystemTrayIcon.ActivationReason.Trigger
    _TRAY_WARNING   = QSystemTrayIcon.MessageIcon.Warning
    _ANTIALIAS      = QPainter.RenderHint.Antialiasing
    _BOLD           = QFont.Weight.Bold
    _EXTRABOLD      = QFont.Weight.ExtraBold

# ---------------------------------------------------------------------------

log = setup_logging()

# ---------------------------------------------------------------------------

LANGUAGES = {
    "en": {"name": "English",   "active": "Enabled",    "title": "Color Temp",     "show_label": "Tray Value",   "auto": "Auto",      "contrast": "Visibility", "quit": "Exit",    "as_on": "Autostart: ON",         "as_off": "Autostart: OFF", "mode_classic": "Classic",     "mode_aggressive": "Aggressive",     "mode_mathematical": "Mathematical", "mode_label": "Color mode"},
    "ru": {"name": "Русский",   "active": "Включено",   "title": "Температура",    "show_label": "В трее",       "auto": "Авто",      "contrast": "Видимость",  "quit": "Выход",   "as_on": "Автозапуск: ВКЛ",       "as_off": "Автозапуск: ВЫКЛ", "mode_classic": "Классический", "mode_aggressive": "Агрессивный",     "mode_mathematical": "Математический", "mode_label": "Режим цвета"},
    "zh": {"name": "中文",       "active": "已启用",      "title": "色温",           "show_label": "托盘数值",      "auto": "自动",      "contrast": "可见性",      "quit": "退出",    "as_on": "自启动: 开启",           "as_off": "自启动: 关闭", "mode_classic": "经典",      "mode_aggressive": "激进",          "mode_mathematical": "数学", "mode_label": "颜色模式"},
    "es": {"name": "Español",   "active": "Activado",   "title": "Temp. de color", "show_label": "En bandeja",   "auto": "Auto",      "contrast": "Visibilidad","quit": "Salir",   "as_on": "Inicio auto: ON",        "as_off": "Inicio auto: OFF", "mode_classic": "Clásico",   "mode_aggressive": "Agresivo",       "mode_mathematical": "Matemático", "mode_label": "Modo de color"},
    "hi": {"name": "हिन्दी",    "active": "सक्रिय",     "title": "रंग तापमान",    "show_label": "ट्रे मान",    "auto": "ऑटो",      "contrast": "दृश्यता",   "quit": "निकास",  "as_on": "ऑटोस्टार्ट: चालू",     "as_off": "ऑटोस्टार्ट: बंद", "mode_classic": "क्लासिक",  "mode_aggressive": "आक्रामक",       "mode_mathematical": "गणितीय", "mode_label": "रंग मोड"},
    "ar": {"name": "العربية",   "active": "مفعل",       "title": "درجة الحرارة",   "show_label": "قيمة التبويب", "auto": "تلقائي",   "contrast": "الرؤية",    "quit": "خروج",   "as_on": "بدء تلقائي: تشغيل",    "as_off": "بدء تلقائي: إيقاف", "mode_classic": "كلاسيكي",  "mode_aggressive": "عدواني",        "mode_mathematical": "رياضي", "mode_label": "وضع اللون"},
    "pt": {"name": "Português", "active": "Ativado",    "title": "Temp. Cor",      "show_label": "Na bandeja",   "auto": "Auto",      "contrast": "Visibilidade","quit": "Sair",   "as_on": "Auto-início: LIG",       "as_off": "Auto-início: DES", "mode_classic": "Clássico", "mode_aggressive": "Agressivo",      "mode_mathematical": "Matemático", "mode_label": "Modo de cor"},
    "fr": {"name": "Français",  "active": "Activé",     "title": "Temp. Couleur",  "show_label": "Dans le tray", "auto": "Auto",      "contrast": "Visibilité", "quit": "Quitter", "as_on": "Démarrage: ON",          "as_off": "Démarrage: OFF", "mode_classic": "Classique","mode_aggressive": "Agressif",       "mode_mathematical": "Mathématique", "mode_label": "Mode couleur"},
    "de": {"name": "Deutsch",   "active": "Aktiviert",  "title": "Farbtemp.",      "show_label": "Tray-Wert",    "auto": "Auto",      "contrast": "Sichtbarkeit","quit": "Beenden","as_on": "Autostart: AN",           "as_off": "Autostart: AUS", "mode_classic": "Klassisch","mode_aggressive": "Aggressiv",      "mode_mathematical": "Mathematisch", "mode_label": "Farbmodus"},
    "ja": {"name": "日本語",     "active": "有効",        "title": "色温度",         "show_label": "トレイ表示",    "auto": "自動",      "contrast": "視認性",     "quit": "終了",    "as_on": "自動起動: オン",         "as_off": "自動起動: オフ", "mode_classic": "クラシック","mode_aggressive": "アグレッシブ",   "mode_mathematical": "数学的", "mode_label": "色モード"},
    "ko": {"name": "한국어",     "active": "활성화됨",    "title": "색온도",          "show_label": "트레이 값",    "auto": "자동",      "contrast": "시인성",     "quit": "종료",    "as_on": "자동 시작: 켜짐",        "as_off": "자동 시작: 꺼짐", "mode_classic": "클래식",  "mode_aggressive": "공격적",         "mode_mathematical": "수학적", "mode_label": "색상 모드"},
    "he": {"name": "עברית",     "active": "פעיל",       "title": "טמפ' צבע",       "show_label": "ערך במגש",    "auto": "אוטומטי",  "contrast": "נראות",     "quit": "יציאה",  "as_on": "הפעלה אוטומטית: פעיל", "as_off": "הפעלה אוטומטית: כבוי", "mode_classic": "קלאסי",  "mode_aggressive": "אגרסיבי",      "mode_mathematical": "מתמטי", "mode_label": "מצב צבע"},
}
NAME_TO_CODE = {v["name"]: k for k, v in LANGUAGES.items()}

def target_temp_for_time(now: datetime) -> float:
    h = now.hour + now.minute / 60.0
    DAWN_START, DAWN_END  = 6.0,  7.5
    DUSK_START, DUSK_END  = 17.0, 21.0
    DAY_TEMP,   NIGHT_TEMP = 6500.0, 3000.0
    def lerp(a, b, t): return a + (b - a) * t
    if DAWN_START <= h < DAWN_END:
        return lerp(NIGHT_TEMP, DAY_TEMP, (h - DAWN_START) / (DAWN_END - DAWN_START))
    elif DAWN_END <= h < DUSK_START:
        return DAY_TEMP
    elif DUSK_START <= h < DUSK_END:
        return lerp(DAY_TEMP, NIGHT_TEMP, (h - DUSK_START) / (DUSK_END - DUSK_START))
    else:
        return NIGHT_TEMP

SMOOTH_STEP     = 100
SMOOTH_INTERVAL = 5000
# ---------------------------------------------------------------------------

BUTTON1_MASK = 1 << 8


class X11Pointer:
    def __init__(self):
        self.display = None
        self.x11 = None
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return

        lib_name = ctypes.util.find_library("X11")
        if not lib_name:
            log.warning("libX11 not found; outside-click polling is unavailable")
            return

        try:
            self.x11 = ctypes.cdll.LoadLibrary(lib_name)
            self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            self.x11.XOpenDisplay.restype = ctypes.c_void_p
            self.x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
            self.x11.XQueryPointer.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_uint)
            ]
            self.x11.XQueryPointer.restype = ctypes.c_int
            self.display = self.x11.XOpenDisplay(None)
            if not self.display:
                log.warning("XOpenDisplay failed; outside-click polling is unavailable")
        except Exception as e:
            log.warning(f"X11 pointer init failed: {e}")
            self.display = None
            self.x11 = None

    def state(self):
        if not self.display or not self.x11:
            return None

        root = self.x11.XDefaultRootWindow(self.display)
        root_return = ctypes.c_ulong()
        child_return = ctypes.c_ulong()
        root_x = ctypes.c_int()
        root_y = ctypes.c_int()
        win_x = ctypes.c_int()
        win_y = ctypes.c_int()
        mask = ctypes.c_uint()

        ok = self.x11.XQueryPointer(
            self.display, root,
            ctypes.byref(root_return), ctypes.byref(child_return),
            ctypes.byref(root_x), ctypes.byref(root_y),
            ctypes.byref(win_x), ctypes.byref(win_y),
            ctypes.byref(mask)
        )
        if not ok:
            return None

        return root_x.value, root_y.value, mask.value

def save_settings(s):
    try:
        with open(paths.config_file, "w") as f:
            for k, v in s.items(): f.write(f"{k}={v}\n")
    except Exception as e:
        log.error(f"save_settings: {e}")

def load_settings():
    s = {"temp": 6500, "show_label": 0, "lang": "ru", "auto": 0, "contrast": 0, "enabled": 1, "color_mode": 0}
    if os.path.exists(paths.config_file):
        try:
            with open(paths.config_file, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        s[k.strip()] = int(v.strip()) if v.strip().isdigit() else v.strip()
        except Exception as e:
            log.error(f"load_settings: {e}")
    return s

def create_backend():
    if sys.platform == "win32":
        from backend_win32 import Win32Backend
        return Win32Backend()
    from backend_linux import LinuxBackend
    backend = LinuxBackend(paths.engine)
    backend.unpack()
    return backend

# ---------------------------------------------------------------------------

class JumpSlider(QSlider):
    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == _LEFT_BUTTON:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.pos().x()) / self.width()
            self.setValue(int(val))
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if not self.isEnabled(): return
        delta = 100 if event.angleDelta().y() > 0 else -100
        self.setValue(max(self.minimum(), min(self.maximum(), self.value() + delta)))


class PopupSlider(QWidget):
    def __init__(self, settings, tray_parent):
        super().__init__()
        self.tray_parent = tray_parent
        self.s = settings
        self._float_temp = float(self.s['temp'])

        self.setWindowFlags(_POPUP | _FRAMELESS | _STAYS_ON_TOP)
        self.setFixedSize(320, 200)
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #ffffff; border: 1px solid #444; border-radius: 8px; }
            QSlider::groove:horizontal {
                height: 8px; border-radius: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff3300, stop:0.5 #ffffff, stop:1 #3399ff);
            }
            QSlider::handle:horizontal { background: #ffffff; border: 2px solid #000; width: 18px; height: 18px; margin: -5px 0; border-radius: 9px; }
            QPushButton { background: #333; padding: 5px; border-radius: 4px; }
            QPushButton:hover { background: #444; }
            QComboBox { background: #333; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        top = QHBoxLayout()
        self.check_enabled = QCheckBox()
        self.check_enabled.setChecked(bool(self.s['enabled']))
        self.check_enabled.setStyleSheet("font-size: 13px; color: #fb923c; font-weight: bold;")
        self.check_enabled.stateChanged.connect(self.toggle_power)
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Verdana", 10, _BOLD))
        self.title_label.setStyleSheet("border: none;")
        top.addWidget(self.check_enabled); top.addStretch(); top.addWidget(self.title_label)
        layout.addLayout(top)

        mode_row = QHBoxLayout()
        self.mode_label = QLabel()
        self.mode_box = QComboBox()
        current_lang = LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])
        self.mode_box.addItems([
            current_lang["mode_classic"],
            current_lang["mode_aggressive"],
            current_lang["mode_mathematical"]
        ])
        self.mode_box.setCurrentIndex(int(self.s.get('color_mode', 0)))
        self.mode_box.currentIndexChanged.connect(self.change_color_mode)
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_box)
        layout.addLayout(mode_row)

        self.slider = JumpSlider(_HORIZONTAL)
        self.slider.setRange(1000, 10000)
        self.slider.setValue(int(self.s['temp']))
        self.slider.valueChanged.connect(self.sync)
        layout.addWidget(self.slider)

        mid = QHBoxLayout()
        self.check_label = QCheckBox()
        self.check_label.setChecked(bool(self.s['show_label']))
        self.check_label.stateChanged.connect(self.sync)
        self.check_auto = QCheckBox()
        self.check_auto.setChecked(bool(self.s['auto']))
        self.check_auto.stateChanged.connect(self.toggle_auto)
        mid.addWidget(self.check_label); mid.addStretch(); mid.addWidget(self.check_auto)
        layout.addLayout(mid)

        bot = QHBoxLayout()
        self.check_contrast = QCheckBox()
        self.check_contrast.setChecked(bool(self.s['contrast']))
        self.check_contrast.stateChanged.connect(self.sync)
        self.lang_box = QComboBox()
        self.lang_box.addItems([LANGUAGES[k]["name"] for k in LANGUAGES])
        self.lang_box.setCurrentText(LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])["name"])
        self.lang_box.currentTextChanged.connect(self.change_lang)
        bot.addWidget(self.check_contrast); bot.addStretch(); bot.addWidget(self.lang_box)
        layout.addLayout(bot)

        self.btn_as = QPushButton()
        self.btn_as.clicked.connect(self.toggle_as)
        layout.addWidget(self.btn_as)

        self.smooth_timer = QTimer()
        self.smooth_timer.timeout.connect(self._smooth_tick)
        self.smooth_timer.start(SMOOTH_INTERVAL)

        self.outside_click_timer = QTimer()
        self.outside_click_timer.setInterval(30)
        self.outside_click_timer.timeout.connect(self._watch_outside_click)
        self._wait_for_mouse_release = False
        self._pending_outside_click = False
        self._ignore_outside_click_until = 0.0
        self._suppress_tray_show_until = 0.0
        self.x11_pointer = X11Pointer() if is_linux() else None

        self.retranslate_ui()
        self.tray_parent.update_icon(self._display_temp(), self.s['show_label'])
        QTimer.singleShot(500, self.sync)

        if self.s['enabled'] and not self.s.get('auto', 0):
            QTimer.singleShot(650, lambda: self.apply_engine(
                self._display_temp(), self.s.get('color_mode', 0)
            ))

        QApplication.instance().installEventFilter(self)

        if is_linux() and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            warning_label = QLabel("⚠ Wayland detected — this app requires an X11 session.\nGamma changes will not work.")
            warning_label.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 11px; padding: 8px; background: #331111; border-radius: 4px;")
            warning_label.setWordWrap(True)
            self.layout().insertWidget(0, warning_label)

            for wtype in (QSlider, QPushButton, QCheckBox, QComboBox):
                for widget in self.findChildren(wtype):
                    widget.setEnabled(False)

    def _display_temp(self) -> int:
        return round(self._float_temp / 100) * 100

    def _smooth_tick(self):
        if not self.s.get('auto') or not self.s.get('enabled'):
            return
        target  = target_temp_for_time(datetime.now())
        current = self._float_temp
        if abs(current - target) < 1:
            return
        step      = SMOOTH_STEP if target > current else -SMOOTH_STEP
        new_float = current + step
        if (step > 0 and new_float > target) or (step < 0 and new_float < target):
            new_float = target
        self._float_temp = new_float
        disp = self._display_temp()
        self.s['temp'] = disp
        self.apply_engine(disp, self.s.get('color_mode', 0))
        self.tray_parent.update_icon(disp, self.s['show_label'])
        self.title_label.setText(
            f"{LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])['title']}: {disp} K"
        )
        log.info(f"Auto smooth: {round(current)}K → {disp}K (target {round(target)}K)")

    def retranslate_ui(self):
        l = LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])
        self.check_enabled.setText(l['active'])
        self.check_label.setText(l['show_label'])
        self.check_auto.setText(l['auto'])
        self.check_contrast.setText(l['contrast'])
        self.btn_as.setText(l['as_on'] if is_autostart_enabled() else l['as_off'])
        self.title_label.setText(f"{l['title']}: {self.s['temp']} K")

        if hasattr(self, 'mode_box'):
            current = self.mode_box.currentIndex()
            self.mode_box.clear()
            self.mode_box.addItems([
                l["mode_classic"],
                l["mode_aggressive"],
                l["mode_mathematical"]
            ])
            self.mode_box.setCurrentIndex(current)

        if hasattr(self, 'mode_label'):
            self.mode_label.setText(l.get('mode_label', 'Режим цвета'))

        is_act = self.check_enabled.isChecked() and not self.check_auto.isChecked()
        self.slider.setEnabled(is_act)
        if hasattr(self, 'mode_box'):
            self.mode_box.setEnabled(is_act)
        self.check_contrast.setEnabled(is_act)
        self.mode_box.setEnabled(is_act)

    def toggle_power(self, state):
        self.s['enabled'] = int(state)
        if not state:
            self.tray_parent.backend.reset()
        else:
            self.sync()
        save_settings(self.s)
        self.retranslate_ui()

    def toggle_auto(self, state):
        self.s['auto'] = int(state)
        if state:
            log.info(f"Auto ON. current={self._display_temp()}K target={round(target_temp_for_time(datetime.now()))}K")
            self._smooth_tick()
        else:
            self.sync()
        save_settings(self.s)
        self.retranslate_ui()

    def change_lang(self, name):
        self.s['lang'] = NAME_TO_CODE.get(name, "ru")
        save_settings(self.s)
        self.retranslate_ui()
        self.tray_parent.update_menu()

    def change_color_mode(self, index):
        self.s['color_mode'] = int(index)
        save_settings(self.s)
        if self.s['enabled'] and not self.s.get('auto'):
            self.apply_engine(self._display_temp(), self.s.get('color_mode', 0))

    def sync(self):
        if self.s['auto'] and self.s['enabled']: return
        val = (self.slider.value() // 100) * 100
        self.s['temp']       = val
        self._float_temp     = float(val)
        self.s['show_label'] = int(self.check_label.isChecked())
        self.s['contrast']   = int(self.check_contrast.isChecked())
        if self.s['enabled']: self.apply_engine(val, self.s.get('color_mode', 0))
        self.tray_parent.update_icon(val, self.s['show_label'])
        self.title_label.setText(
            f"{LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])['title']}: {val} K"
        )
        save_settings(self.s)

    def apply_engine(self, temp, mode=None):
        gamma = 1.3 if self.s.get('contrast', 0) else 1.0
        if mode is None:
            mode = self.s.get('color_mode', 0)
        try:
            ok = self.tray_parent.backend.apply(temp, gamma, mode)
            if not ok and sys.platform == "win32":
                self.tray_parent.warn_ramp_rejected()
        except Exception as e:
            log.error(f"apply_engine: {e}")

    def toggle_as(self):
        toggle_autostart()
        self.retranslate_ui()

    def showEvent(self, event):
        self._wait_for_mouse_release = True
        self._pending_outside_click = False
        self.outside_click_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.outside_click_timer.stop()
        super().hideEvent(event)

    def show_at_cursor(self):
        pos = QCursor.pos()
        self.move(pos.x() - 160, pos.y() - 220)
        self.ignore_outside_clicks()
        self._show_and_raise()

    def bring_to_front(self):
        self._wait_for_mouse_release = True
        self.ignore_outside_clicks()
        self._show_and_raise()

    def ignore_outside_clicks(self, ms=350):
        self._pending_outside_click = False
        self._ignore_outside_click_until = time.monotonic() + (ms / 1000.0)

    def hide_from_tray(self):
        self._pending_outside_click = False
        self.hide()

    def should_suppress_tray_show(self):
        if time.monotonic() < self._suppress_tray_show_until:
            self._suppress_tray_show_until = 0.0
            return True
        return False

    def _show_and_raise(self):
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        self.outside_click_timer.start()

    def _watch_outside_click(self):
        x11_state = self.x11_pointer.state() if self.x11_pointer else None
        if x11_state:
            _, _, mask = x11_state
            left_pressed = bool(mask & BUTTON1_MASK)
        else:
            buttons = QApplication.mouseButtons()
            left_pressed = bool(buttons & _LEFT_BUTTON)

        now = time.monotonic()
        outside = not self._contains_global_pos(QCursor.pos())

        if self._wait_for_mouse_release:
            if not left_pressed:
                self._wait_for_mouse_release = False
            return

        if now < self._ignore_outside_click_until:
            self._pending_outside_click = False
            return

        if left_pressed:
            self._pending_outside_click = outside
            return

        if self._pending_outside_click and outside:
            self._pending_outside_click = False
            self._suppress_tray_show_until = time.monotonic() + 0.35
            self.hide()
        else:
            self._pending_outside_click = False

    def _contains_global_pos(self, pos):
        widget = QApplication.widgetAt(pos)
        active_popup = QApplication.activePopupWidget()

        current = widget
        while current:
            if current is active_popup:
                return True
            current = current.parentWidget()

        current = widget
        while current:
            if current is self:
                return True
            if current.window() is self:
                return True
            current = current.parentWidget()

        top_left = self.mapToGlobal(self.rect().topLeft())
        bottom_right = self.mapToGlobal(self.rect().bottomRight())
        return top_left.x() <= pos.x() <= bottom_right.x() and top_left.y() <= pos.y() <= bottom_right.y()

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

class TrayApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self.on_exit)
        self._ramp_warned = False

        self.settings = load_settings()
        self.backend = create_backend()
        log.info(f"Gamma Slider started (PyQt{QT_VERSION})")

        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.update_menu()

        self.update_icon(self.settings['temp'], self.settings['show_label'])

        self.popup = PopupSlider(self.settings, self)
        self.tray.activated.connect(self.clicked)
        self.tray.show()

    def on_exit(self):
        log.info("Exiting")
        self.backend.close()

    def warn_ramp_rejected(self):
        if self._ramp_warned:
            return
        self._ramp_warned = True
        log.warning("Display driver rejected the gamma ramp")
        try:
            self.tray.showMessage(
                "Gamma Slider",
                "Display driver rejected the gamma ramp. Disable Night Light / HDR and try again.",
                _TRAY_WARNING,
                8000,
            )
        except Exception as e:
            log.error(f"tray warning: {e}")

    def update_menu(self):
        self.menu.clear()
        l = LANGUAGES.get(self.settings.get('lang', 'ru'), LANGUAGES['ru'])
        self.menu.addAction(l['quit']).triggered.connect(self.app.quit)

    def update_icon(self, val, show):
        pix = QPixmap(64, 64)
        pix.fill(_TRANSPARENT)
        p = QPainter(pix)
        p.setRenderHint(_ANTIALIAS)
        p.setBrush(QColor("#fb923c"))
        p.setPen(_NO_PEN)
        p.drawEllipse(4, 4, 56, 56)
        if show:
            p.setPen(QColor("black"))
            p.setFont(QFont("Verdana", 28, _BOLD))
            p.drawText(pix.rect(), _ALIGN_CENTER, str(val // 100))
        p.end()
        self.tray.setIcon(QIcon(pix))
        self.tray.setToolTip(f"{val} K")

    def clicked(self, r):
        if r == _TRAY_TRIGGER:
            if self.popup.isVisible():
                self.popup.hide_from_tray()
            elif not self.popup.should_suppress_tray_show():
                self.popup.show_at_cursor()

if __name__ == "__main__":
    if not acquire_single_instance():
        sys.exit(0)
    app = TrayApp()
    sys.exit(app.app.exec())
