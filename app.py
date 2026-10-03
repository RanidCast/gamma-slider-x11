#!/usr/bin/env python3
import sys
import os
import logging
import ctypes
import ctypes.util
import time
import queue
from datetime import datetime

from platform_support import (
    paths,
    setup_logging,
    acquire_single_instance,
    is_autostart_enabled,
    toggle_autostart,
    is_linux,
    is_frozen,
)
import hotkeys
from ipc import parse_cli, send_command, IpcServer

try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QSlider, QLabel, QSystemTrayIcon,
        QMenu, QCheckBox, QHBoxLayout, QComboBox, QPushButton, QStackedWidget,
        QSpinBox, QTimeEdit, QScrollArea, QFrame, QAbstractSpinBox, QSizePolicy,
    )
    from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QCursor
    from PyQt5.QtCore import Qt, QObject, QTimer, QEvent, QTime, QAbstractNativeEventFilter
    QT_VERSION = 5

    _LEFT_BUTTON    = Qt.LeftButton
    _TRANSPARENT    = Qt.transparent
    _NO_PEN         = Qt.NoPen
    _ALIGN_CENTER   = Qt.AlignCenter
    _HORIZONTAL     = Qt.Horizontal
    _POPUP          = Qt.Tool
    _FRAMELESS      = Qt.FramelessWindowHint
    _STAYS_ON_TOP   = Qt.WindowStaysOnTopHint
    _CLICK_FOCUS    = Qt.ClickFocus
    _SCROLL_AS_NEEDED = Qt.ScrollBarAsNeeded
    _SIZE_IGNORED   = QSizePolicy.Ignored
    _TRAY_TRIGGER   = QSystemTrayIcon.Trigger
    _TRAY_MIDDLE    = QSystemTrayIcon.MiddleClick
    _TRAY_WARNING   = QSystemTrayIcon.Warning
    _ANTIALIAS      = QPainter.Antialiasing
    _BOLD           = QFont.Bold
    _EXTRABOLD      = QFont.ExtraBold
    _CTRL           = Qt.ControlModifier
    _ALT            = Qt.AltModifier
    _SHIFT          = Qt.ShiftModifier
    _KEY_ESCAPE     = Qt.Key_Escape
    _EVT_MOUSE_PRESS = QEvent.MouseButtonPress
    _EVT_KEY_PRESS  = QEvent.KeyPress
    _EVT_WHEEL      = QEvent.Wheel
    _EVT_ENTER      = QEvent.Enter
    _NO_FRAME       = QFrame.NoFrame
    _SCROLL_OFF     = Qt.ScrollBarAlwaysOff
    _TEXT_SELECT    = Qt.TextSelectableByMouse
    _WA_DONT_SHOW   = Qt.WA_DontShowOnScreen

    def _qt_key(name):
        return getattr(Qt, name)

except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QSlider, QLabel, QSystemTrayIcon,
        QMenu, QCheckBox, QHBoxLayout, QComboBox, QPushButton, QStackedWidget,
        QSpinBox, QTimeEdit, QScrollArea, QFrame, QAbstractSpinBox, QSizePolicy,
    )
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QCursor
    from PyQt6.QtCore import Qt, QObject, QTimer, QEvent, QTime, QAbstractNativeEventFilter
    QT_VERSION = 6

    _LEFT_BUTTON    = Qt.MouseButton.LeftButton
    _TRANSPARENT    = Qt.GlobalColor.transparent
    _NO_PEN         = Qt.PenStyle.NoPen
    _ALIGN_CENTER   = Qt.AlignmentFlag.AlignCenter
    _HORIZONTAL     = Qt.Orientation.Horizontal
    _POPUP          = Qt.WindowType.Tool
    _FRAMELESS      = Qt.WindowType.FramelessWindowHint
    _STAYS_ON_TOP   = Qt.WindowType.WindowStaysOnTopHint
    _CLICK_FOCUS    = Qt.FocusPolicy.ClickFocus
    _SCROLL_AS_NEEDED = Qt.ScrollBarPolicy.ScrollBarAsNeeded
    _SIZE_IGNORED   = QSizePolicy.Policy.Ignored
    _TRAY_TRIGGER   = QSystemTrayIcon.ActivationReason.Trigger
    _TRAY_MIDDLE    = QSystemTrayIcon.ActivationReason.MiddleClick
    _TRAY_WARNING   = QSystemTrayIcon.MessageIcon.Warning
    _ANTIALIAS      = QPainter.RenderHint.Antialiasing
    _BOLD           = QFont.Weight.Bold
    _EXTRABOLD      = QFont.Weight.ExtraBold
    _CTRL           = Qt.KeyboardModifier.ControlModifier
    _ALT            = Qt.KeyboardModifier.AltModifier
    _SHIFT          = Qt.KeyboardModifier.ShiftModifier
    _KEY_ESCAPE     = Qt.Key.Key_Escape
    _EVT_MOUSE_PRESS = QEvent.Type.MouseButtonPress
    _EVT_KEY_PRESS  = QEvent.Type.KeyPress
    _EVT_WHEEL      = QEvent.Type.Wheel
    _EVT_ENTER      = QEvent.Type.Enter
    _NO_FRAME       = QFrame.Shape.NoFrame
    _SCROLL_OFF     = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    _TEXT_SELECT    = Qt.TextInteractionFlag.TextSelectableByMouse
    _WA_DONT_SHOW   = Qt.WidgetAttribute.WA_DontShowOnScreen

    def _qt_key(name):
        return getattr(Qt.Key, name)

log = setup_logging()

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
_EXTRA = {
    "en": {"settings": "Settings", "back": "Back", "hotkeys": "Hotkeys", "warmer": "Warmer", "cooler": "Cooler", "step": "Step", "schedule": "Schedule", "dawn_start": "Dawn start", "dawn_end": "Dawn end", "dusk_start": "Dusk start", "dusk_end": "Dusk end", "day": "Day", "night": "Night", "schedule_bad": "Invalid time order", "cli_hint": "Commands", "gnome_hint": "GNOME cannot grab keys. Bind these in system keyboard settings:"},
    "ru": {"settings": "Настройки", "back": "Назад", "hotkeys": "Горячие клавиши", "warmer": "Теплее", "cooler": "Холоднее", "step": "Шаг", "schedule": "Расписание", "dawn_start": "Рассвет с", "dawn_end": "Рассвет до", "dusk_start": "Закат с", "dusk_end": "Закат до", "day": "День", "night": "Ночь", "schedule_bad": "Неверный порядок времени", "cli_hint": "Команды", "gnome_hint": "GNOME не даёт перехватывать клавиши. Назначьте команды в настройках клавиатуры:"},
    "zh": {"settings": "设置", "back": "返回", "hotkeys": "快捷键", "warmer": "更暖", "cooler": "更冷", "step": "步进", "schedule": "时间表", "dawn_start": "黎明开始", "dawn_end": "黎明结束", "dusk_start": "黄昏开始", "dusk_end": "黄昏结束", "day": "白天", "night": "夜晚", "schedule_bad": "时间顺序无效", "cli_hint": "命令", "gnome_hint": "GNOME 无法捕获按键。请在系统键盘设置中绑定:"},
    "es": {"settings": "Ajustes", "back": "Atrás", "hotkeys": "Atajos", "warmer": "Más cálido", "cooler": "Más frío", "step": "Paso", "schedule": "Horario", "dawn_start": "Alba inicio", "dawn_end": "Alba fin", "dusk_start": "Ocaso inicio", "dusk_end": "Ocaso fin", "day": "Día", "night": "Noche", "schedule_bad": "Orden de horas inválido", "cli_hint": "Comandos", "gnome_hint": "GNOME no captura teclas. Asigne estos comandos en el teclado del sistema:"},
    "hi": {"settings": "सेटिंग्स", "back": "वापस", "hotkeys": "हॉटकी", "warmer": "गर्म", "cooler": "ठंडा", "step": "चरण", "schedule": "समय-सारणी", "dawn_start": "भोर शुरू", "dawn_end": "भोर अंत", "dusk_start": "संध्या शुरू", "dusk_end": "संध्या अंत", "day": "दिन", "night": "रात", "schedule_bad": "समय क्रम अमान्य", "cli_hint": "कमांड", "gnome_hint": "GNOME कुंजी नहीं पकड़ सकता। सिस्टम कीबोर्ड सेटिंग में बाँधें:"},
    "ar": {"settings": "الإعدادات", "back": "رجوع", "hotkeys": "اختصارات", "warmer": "أدفأ", "cooler": "أبرد", "step": "خطوة", "schedule": "الجدول", "dawn_start": "بداية الفجر", "dawn_end": "نهاية الفجر", "dusk_start": "بداية الغسق", "dusk_end": "نهاية الغسق", "day": "نهار", "night": "ليل", "schedule_bad": "ترتيب الوقت غير صالح", "cli_hint": "أوامر", "gnome_hint": "لا يمكن لـ GNOME التقاط المفاتيح. اربط الأوامر في إعدادات لوحة المفاتيح:"},
    "pt": {"settings": "Definições", "back": "Voltar", "hotkeys": "Atalhos", "warmer": "Mais quente", "cooler": "Mais frio", "step": "Passo", "schedule": "Horário", "dawn_start": "Alvorada início", "dawn_end": "Alvorada fim", "dusk_start": "Crepúsculo início", "dusk_end": "Crepúsculo fim", "day": "Dia", "night": "Noite", "schedule_bad": "Ordem de horas inválida", "cli_hint": "Comandos", "gnome_hint": "O GNOME não captura teclas. Associe estes comandos nas definições do teclado:"},
    "fr": {"settings": "Réglages", "back": "Retour", "hotkeys": "Raccourcis", "warmer": "Plus chaud", "cooler": "Plus froid", "step": "Pas", "schedule": "Horaire", "dawn_start": "Aube début", "dawn_end": "Aube fin", "dusk_start": "Crépuscule début", "dusk_end": "Crépuscule fin", "day": "Jour", "night": "Nuit", "schedule_bad": "Ordre des heures invalide", "cli_hint": "Commandes", "gnome_hint": "GNOME ne capture pas les touches. Associez ces commandes dans les réglages clavier :"},
    "de": {"settings": "Einstellungen", "back": "Zurück", "hotkeys": "Tasten", "warmer": "Wärmer", "cooler": "Kälter", "step": "Schritt", "schedule": "Zeitplan", "dawn_start": "Morgen von", "dawn_end": "Morgen bis", "dusk_start": "Abend von", "dusk_end": "Abend bis", "day": "Tag", "night": "Nacht", "schedule_bad": "Ungültige Zeitfolge", "cli_hint": "Befehle", "gnome_hint": "GNOME kann Tasten nicht abfangen. Befehle in den Tastatureinstellungen binden:"},
    "ja": {"settings": "設定", "back": "戻る", "hotkeys": "ホットキー", "warmer": "暖色", "cooler": "寒色", "step": "間隔", "schedule": "スケジュール", "dawn_start": "夜明け開始", "dawn_end": "夜明け終了", "dusk_start": "夕方開始", "dusk_end": "夕方終了", "day": "昼", "night": "夜", "schedule_bad": "時刻の順序が無効", "cli_hint": "コマンド", "gnome_hint": "GNOMEはキーを取得できません。システムのキーボード設定で次を割り当ててください:"},
    "ko": {"settings": "설정", "back": "뒤로", "hotkeys": "단축키", "warmer": "더 따뜻하게", "cooler": "더 차갑게", "step": "단계", "schedule": "일정", "dawn_start": "새벽 시작", "dawn_end": "새벽 끝", "dusk_start": "저녁 시작", "dusk_end": "저녁 끝", "day": "낮", "night": "밤", "schedule_bad": "시간 순서가 잘못됨", "cli_hint": "명령", "gnome_hint": "GNOME은 키를 가로챌 수 없습니다. 시스템 키보드 설정에 다음을 등록하세요:"},
    "he": {"settings": "הגדרות", "back": "חזרה", "hotkeys": "קיצורי מקש", "warmer": "חם יותר", "cooler": "קר יותר", "step": "צעד", "schedule": "לוח זמנים", "dawn_start": "שחר התחלה", "dawn_end": "שחר סיום", "dusk_start": "דמדומים התחלה", "dusk_end": "דמדומים סיום", "day": "יום", "night": "לילה", "schedule_bad": "סדר הזמנים אינו תקין", "cli_hint": "פקודות", "gnome_hint": "GNOME לא יכול לתפוס מקשים. שייכו את הפקודות בהגדרות המקלדת:"},
}
for _code, _extra in _EXTRA.items():
    LANGUAGES[_code].update(_extra)
NAME_TO_CODE = {v["name"]: k for k, v in LANGUAGES.items()}

DEFAULTS = {
    "temp": 6500,
    "show_label": 0,
    "lang": "ru",
    "auto": 0,
    "contrast": 0,
    "enabled": 1,
    "color_mode": 0,
    "hotkeys": 1,
    "hotkey_up": "Ctrl+Alt+PgUp",
    "hotkey_down": "Ctrl+Alt+PgDown",
    "hotkey_step": 100,
    "dawn_start": 6 * 60,
    "dawn_end": 7 * 60 + 30,
    "dusk_start": 17 * 60,
    "dusk_end": 21 * 60,
    "day_temp": 6500,
    "night_temp": 3000,
}
TEMP_MIN = 1000
TEMP_MAX = 10000
POPUP_W = 320
POPUP_H = 200
SMOOTH_STEP = 100
SMOOTH_INTERVAL = 5000
PRESETS = (3000, 4000, 6500)
_QT_KEY_NAMES = {}
for _qt_name, _label in (
    ("Key_PageUp", "PgUp"),
    ("Key_PageDown", "PgDown"),
    ("Key_Home", "Home"),
    ("Key_End", "End"),
    ("Key_Insert", "Insert"),
    ("Key_Delete", "Delete"),
    ("Key_Left", "Left"),
    ("Key_Up", "Up"),
    ("Key_Right", "Right"),
    ("Key_Down", "Down"),
    ("Key_Space", "Space"),
    ("Key_Tab", "Tab"),
    ("Key_Return", "Return"),
    ("Key_Enter", "Return"),
):
    _QT_KEY_NAMES[_qt_key(_qt_name)] = _label
for _i in range(1, 13):
    _QT_KEY_NAMES[_qt_key("Key_F%d" % _i)] = "F%d" % _i
for _ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _QT_KEY_NAMES[_qt_key("Key_%s" % _ch)] = _ch
for _i in range(10):
    _QT_KEY_NAMES[_qt_key("Key_%d" % _i)] = str(_i)
_MODIFIER_KEYS = set()
for _mod_name in (
    "Key_Control", "Key_Shift", "Key_Alt", "Key_Meta",
    "Key_Super_L", "Key_Super_R", "Key_AltGr",
):
    try:
        _MODIFIER_KEYS.add(_qt_key(_mod_name))
    except AttributeError:
        pass


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def snap_temp(value):
    temp = _as_int(value, 6500)
    temp = max(TEMP_MIN, min(TEMP_MAX, temp))
    return ((temp + 50) // 100) * 100


def target_temp_for_time(now, settings=None):
    settings = settings or {}
    dawn_start = _as_int(settings.get("dawn_start", DEFAULTS["dawn_start"]), DEFAULTS["dawn_start"]) / 60.0
    dawn_end = _as_int(settings.get("dawn_end", DEFAULTS["dawn_end"]), DEFAULTS["dawn_end"]) / 60.0
    dusk_start = _as_int(settings.get("dusk_start", DEFAULTS["dusk_start"]), DEFAULTS["dusk_start"]) / 60.0
    dusk_end = _as_int(settings.get("dusk_end", DEFAULTS["dusk_end"]), DEFAULTS["dusk_end"]) / 60.0
    day = float(_as_int(settings.get("day_temp", DEFAULTS["day_temp"]), DEFAULTS["day_temp"]))
    night = float(_as_int(settings.get("night_temp", DEFAULTS["night_temp"]), DEFAULTS["night_temp"]))
    if not (dawn_start < dawn_end <= dusk_start < dusk_end):
        dawn_start, dawn_end, dusk_start, dusk_end = 6.0, 7.5, 17.0, 21.0
        day, night = 6500.0, 3000.0
    hour = now.hour + now.minute / 60.0

    def lerp(a, b, t):
        return a + (b - a) * t

    if dawn_start <= hour < dawn_end:
        return lerp(night, day, (hour - dawn_start) / (dawn_end - dawn_start))
    if dawn_end <= hour < dusk_start:
        return day
    if dusk_start <= hour < dusk_end:
        return lerp(day, night, (hour - dusk_start) / (dusk_end - dusk_start))
    return night


def cli_command(flag):
    if is_frozen():
        return "%s %s" % (sys.executable, flag)
    return "%s %s %s" % (sys.executable, os.path.abspath(sys.argv[0]), flag)


def _gnome_session():
    if not is_linux():
        return False
    desk = "%s %s" % (
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    )
    return "gnome" in desk.lower()


def _screen_at(pos):
    screen = None
    if hasattr(QApplication, "screenAt"):
        screen = QApplication.screenAt(pos)
    if screen is None and hasattr(QApplication, "screens"):
        for candidate in QApplication.screens():
            if candidate.geometry().contains(pos):
                screen = candidate
                break
    if screen is None and hasattr(QApplication, "primaryScreen"):
        screen = QApplication.primaryScreen()
    return screen


def format_chord(event):
    key = event.key()
    if key in _MODIFIER_KEYS:
        return None
    label = _QT_KEY_NAMES.get(key)
    if not label:
        return None
    mods = event.modifiers()
    parts = []
    if mods & _CTRL:
        parts.append("Ctrl")
    if mods & _ALT:
        parts.append("Alt")
    if mods & _SHIFT:
        parts.append("Shift")
    parts.append(label)
    return "+".join(parts)


def _native_pass():
    if QT_VERSION == 6:
        return False, 0
    return False


def _native_handled():
    if QT_VERSION == 6:
        return True, 0
    return True


class _WinMsg(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class _WinHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, eventType, message):
        try:
            kind = bytes(eventType)
        except Exception:
            kind = b""
        if b"windows_generic_MSG" not in kind and b"windows_dispatcher_MSG" not in kind:
            return _native_pass()
        if not message:
            return _native_pass()
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(_WinMsg)).contents
        except Exception:
            return _native_pass()
        hotkey_id = int(msg.wParam)
        if msg.message == 0x0312 and hotkey_id in (hotkeys.HOTKEY_UP, hotkeys.HOTKEY_DOWN):
            self._callback(hotkey_id)
            return _native_handled()
        return _native_pass()

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
            for k, v in s.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        log.error(f"save_settings: {e}")

def load_settings():
    s = dict(DEFAULTS)
    if os.path.exists(paths.config_file):
        try:
            with open(paths.config_file, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        s[k.strip()] = int(v.strip()) if v.strip().isdigit() else v.strip()
        except Exception as e:
            log.error(f"load_settings: {e}")
    for key in ("hotkey_up", "hotkey_down", "lang"):
        if key in s and not isinstance(s[key], str):
            s[key] = str(s[key])
    if _as_int(s.get("hotkey_step", 100), 100) == 500:
        s["hotkey_step"] = 100
    return s

def create_backend():
    if sys.platform == "win32":
        from backend_win32 import Win32Backend
        return Win32Backend()
    if sys.platform == "darwin":
        from backend_macos import MacOSBackend
        return MacOSBackend()
    from backend_linux import LinuxBackend
    backend = LinuxBackend(paths.engine)
    backend.unpack()
    return backend

class JumpSlider(QSlider):
    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == _LEFT_BUTTON:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.pos().x()) / self.width()
            self.setValue(int(val))
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return
        delta = 100 if event.angleDelta().y() > 0 else -100
        self.setValue(max(self.minimum(), min(self.maximum(), self.value() + delta)))
        event.accept()


class PopupSlider(QWidget):
    def __init__(self, settings, tray_parent):
        super().__init__()
        self.tray_parent = tray_parent
        self.s = settings
        self._float_temp = float(self.s["temp"])
        self._text_labels = []
        self._capturing = None
        self._last_hotkey = None
        self._last_hotkey_at = 0.0

        self.setObjectName("popup")
        self.setWindowFlags(_POPUP | _FRAMELESS | _STAYS_ON_TOP)
        self.setFixedSize(POPUP_W, POPUP_H)
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #ffffff; border: 1px solid #444; border-radius: 8px; }
            QWidget#page { border: none; background: #1e1e1e; }
            QLabel { border: none; }
            QStackedWidget, QScrollArea { border: none; background: #1e1e1e; }
            QSlider::groove:horizontal {
                height: 8px; border-radius: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff3300, stop:0.5 #ffffff, stop:1 #3399ff);
            }
            QSlider::handle:horizontal { background: #ffffff; border: 2px solid #000; width: 18px; height: 18px; margin: -5px 0; border-radius: 9px; }
            QPushButton { background: #333; padding: 2px 6px; border-radius: 4px; }
            QPushButton:hover { background: #444; }
            QPushButton:disabled { background: #2a2a2a; color: #777; }
            QComboBox, QSpinBox, QTimeEdit { background: #333; color: #ffffff; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(_SIZE_IGNORED, _SIZE_IGNORED)
        self.stack.addWidget(self._build_main())
        self.stack.addWidget(self._build_settings())
        layout.addWidget(self.stack)

        self.smooth_timer = QTimer(self)
        self.smooth_timer.timeout.connect(self._smooth_tick)
        self.smooth_timer.start(SMOOTH_INTERVAL)

        self.outside_click_timer = QTimer(self)
        self.outside_click_timer.setInterval(30)
        self.outside_click_timer.timeout.connect(self._watch_outside_click)
        self._wait_for_mouse_release = False
        self._pending_outside_click = False
        self._ignore_outside_click_until = 0.0
        self._suppress_tray_show_until = 0.0
        self.x11_pointer = X11Pointer() if is_linux() else None

        self.retranslate_ui()
        self.tray_parent.update_icon(self._display_temp(), self.s["show_label"])
        QTimer.singleShot(500, self.sync)

        if self.s["enabled"] and not self.s.get("auto", 0):
            QTimer.singleShot(650, lambda: self.apply_engine(
                self._display_temp(), self.s.get("color_mode", 0)
            ))

        QApplication.instance().installEventFilter(self)

        if is_linux() and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            warning_label = QLabel("⚠ Wayland detected — this app requires an X11 session.\nGamma changes will not work.")
            warning_label.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 11px; padding: 8px; background: #331111; border-radius: 4px;")
            warning_label.setWordWrap(True)
            self.layout().insertWidget(0, warning_label)

            for wtype in (QSlider, QPushButton, QCheckBox, QComboBox, QAbstractSpinBox):
                for widget in self.findChildren(wtype):
                    widget.setEnabled(False)

    def _label(self, key):
        label = QLabel()
        label.setStyleSheet("border: none;")
        self._text_labels.append((label, key))
        return label

    def _build_main(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        top = QHBoxLayout()
        self.check_enabled = QCheckBox()
        self.check_enabled.setChecked(bool(self.s["enabled"]))
        self.check_enabled.setStyleSheet("font-size: 13px; color: #fb923c; font-weight: bold;")
        self.check_enabled.stateChanged.connect(self.toggle_power)
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Verdana", 10, _BOLD))
        self.title_label.setStyleSheet("border: none;")
        top.addWidget(self.check_enabled)
        top.addStretch()
        top.addWidget(self.title_label)
        layout.addLayout(top)

        mode_row = QHBoxLayout()
        self.mode_label = self._label("mode_label")
        self.mode_box = QComboBox()
        current_lang = LANGUAGES.get(self.s["lang"], LANGUAGES["ru"])
        self.mode_box.addItems([
            current_lang["mode_classic"],
            current_lang["mode_aggressive"],
            current_lang["mode_mathematical"],
        ])
        self.mode_box.setCurrentIndex(int(self.s.get("color_mode", 0)))
        self.mode_box.setFocusPolicy(_CLICK_FOCUS)
        self.mode_box.currentIndexChanged.connect(self.change_color_mode)
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_box)
        layout.addLayout(mode_row)

        self.slider = JumpSlider(_HORIZONTAL)
        self.slider.setRange(TEMP_MIN, TEMP_MAX)
        self.slider.setValue(int(self.s["temp"]))
        self.slider.valueChanged.connect(self.sync)
        layout.addWidget(self.slider)

        presets = QHBoxLayout()
        self.preset_buttons = []
        for temp in PRESETS:
            button = QPushButton(str(temp))
            button.clicked.connect(lambda checked=False, value=temp: self.apply_preset(value))
            self.preset_buttons.append(button)
            presets.addWidget(button)
        layout.addLayout(presets)

        mid = QHBoxLayout()
        self.check_label = QCheckBox()
        self.check_label.setChecked(bool(self.s["show_label"]))
        self.check_label.stateChanged.connect(self.sync)
        self.check_auto = QCheckBox()
        self.check_auto.setChecked(bool(self.s["auto"]))
        self.check_auto.stateChanged.connect(self.toggle_auto)
        mid.addWidget(self.check_label)
        mid.addStretch()
        mid.addWidget(self.check_auto)
        layout.addLayout(mid)

        bot = QHBoxLayout()
        self.check_contrast = QCheckBox()
        self.check_contrast.setChecked(bool(self.s["contrast"]))
        self.check_contrast.stateChanged.connect(self.sync)
        self.lang_box = QComboBox()
        self.lang_box.addItems([LANGUAGES[k]["name"] for k in LANGUAGES])
        self.lang_box.setCurrentText(LANGUAGES.get(self.s["lang"], LANGUAGES["ru"])["name"])
        self.lang_box.setFocusPolicy(_CLICK_FOCUS)
        self.lang_box.currentTextChanged.connect(self.change_lang)
        bot.addWidget(self.check_contrast)
        bot.addStretch()
        bot.addWidget(self.lang_box)
        layout.addLayout(bot)

        bottom_btns = QHBoxLayout()
        self.btn_as = QPushButton()
        self.btn_as.clicked.connect(self.toggle_as)
        self.btn_settings = QPushButton()
        self.btn_settings.clicked.connect(lambda checked=False: self._set_page(1))
        bottom_btns.addWidget(self.btn_as)
        bottom_btns.addWidget(self.btn_settings)
        layout.addLayout(bottom_btns)
        return page

    def _build_settings(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.btn_back = QPushButton()
        self.btn_back.clicked.connect(lambda checked=False: self._set_page(0))
        layout.addWidget(self.btn_back)

        self.check_hotkeys = QCheckBox()
        self.check_hotkeys.setChecked(bool(self.s.get("hotkeys", 1)))
        self.check_hotkeys.stateChanged.connect(self._toggle_hotkeys)
        layout.addWidget(self.check_hotkeys)

        up_row = QHBoxLayout()
        up_row.addWidget(self._label("warmer"))
        self.btn_hotkey_up = QPushButton(str(self.s.get("hotkey_up", DEFAULTS["hotkey_up"])))
        self.btn_hotkey_up.clicked.connect(lambda checked=False: self._begin_capture("up"))
        up_row.addWidget(self.btn_hotkey_up)
        layout.addLayout(up_row)

        down_row = QHBoxLayout()
        down_row.addWidget(self._label("cooler"))
        self.btn_hotkey_down = QPushButton(str(self.s.get("hotkey_down", DEFAULTS["hotkey_down"])))
        self.btn_hotkey_down.clicked.connect(lambda checked=False: self._begin_capture("down"))
        down_row.addWidget(self.btn_hotkey_down)
        layout.addLayout(down_row)

        step_row = QHBoxLayout()
        step_row.addWidget(self._label("step"))
        self.spin_step = QSpinBox()
        self.spin_step.setRange(100, 2000)
        self.spin_step.setSingleStep(100)
        self.spin_step.setSuffix(" K")
        self.spin_step.setValue(max(100, _as_int(self.s.get("hotkey_step", 100), 100)))
        self.spin_step.valueChanged.connect(self._step_changed)
        step_row.addWidget(self.spin_step)
        layout.addLayout(step_row)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(_TEXT_SELECT)
        self.hint_label.setStyleSheet("border: none; color: #bbbbbb; font-size: 11px;")
        layout.addWidget(self.hint_label)

        layout.addWidget(self._label("schedule"))
        self.time_dawn_start = self._time_edit(self.s.get("dawn_start", DEFAULTS["dawn_start"]))
        self.time_dawn_end = self._time_edit(self.s.get("dawn_end", DEFAULTS["dawn_end"]))
        self.time_dusk_start = self._time_edit(self.s.get("dusk_start", DEFAULTS["dusk_start"]))
        self.time_dusk_end = self._time_edit(self.s.get("dusk_end", DEFAULTS["dusk_end"]))
        for key, editor in (
            ("dawn_start", self.time_dawn_start),
            ("dawn_end", self.time_dawn_end),
            ("dusk_start", self.time_dusk_start),
            ("dusk_end", self.time_dusk_end),
        ):
            row = QHBoxLayout()
            row.addWidget(self._label(key))
            row.addStretch()
            row.addWidget(editor)
            layout.addLayout(row)

        temp_row = QHBoxLayout()
        temp_row.addWidget(self._label("day"))
        self.spin_day = self._temp_spin(self.s.get("day_temp", DEFAULTS["day_temp"]))
        temp_row.addWidget(self.spin_day)
        temp_row.addWidget(self._label("night"))
        self.spin_night = self._temp_spin(self.s.get("night_temp", DEFAULTS["night_temp"]))
        temp_row.addWidget(self.spin_night)
        layout.addLayout(temp_row)

        self.schedule_warn = QLabel()
        self.schedule_warn.setStyleSheet("color: #ff6b6b; border: none;")
        self.schedule_warn.setVisible(False)
        layout.addWidget(self.schedule_warn)
        layout.addStretch()

        for editor in (
            self.time_dawn_start, self.time_dawn_end, self.time_dusk_start, self.time_dusk_end,
        ):
            editor.editingFinished.connect(self._commit_schedule)
        self.spin_day.valueChanged.connect(self._commit_schedule)
        self.spin_night.valueChanged.connect(self._commit_schedule)

        scroll = QScrollArea()
        scroll.setObjectName("page")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_NO_FRAME)
        scroll.setHorizontalScrollBarPolicy(_SCROLL_OFF)
        scroll.setVerticalScrollBarPolicy(_SCROLL_AS_NEEDED)
        scroll.setSizePolicy(_SIZE_IGNORED, _SIZE_IGNORED)
        scroll.setWidget(page)
        return scroll

    def _time_edit(self, minutes):
        editor = QTimeEdit()
        editor.setDisplayFormat("HH:mm")
        editor.setTime(self._qtime(minutes))
        return editor

    def _temp_spin(self, value):
        spin = QSpinBox()
        spin.setRange(TEMP_MIN, TEMP_MAX)
        spin.setSingleStep(100)
        spin.setSuffix(" K")
        spin.setValue(snap_temp(value))
        return spin

    def _qtime(self, minutes):
        minutes = _as_int(minutes, 0) % (24 * 60)
        return QTime(minutes // 60, minutes % 60)

    def _minutes(self, editor):
        clock = editor.time()
        return clock.hour() * 60 + clock.minute()

    def _display_temp(self) -> int:
        return round(self._float_temp / 100) * 100

    def _hotkey_step(self):
        step = _as_int(self.s.get("hotkey_step", 100), 100)
        if step < 100:
            return 100
        return step

    def can_adjust(self):
        return bool(self.s.get("enabled")) and not bool(self.s.get("auto"))

    def apply_temperature(self, temp):
        temp = snap_temp(temp)
        self.slider.blockSignals(True)
        self.slider.setValue(temp)
        self.slider.blockSignals(False)
        self.sync()

    def adjust_temperature(self, delta):
        if not self.can_adjust():
            return False
        self.apply_temperature(self._display_temp() + delta)
        return True

    def apply_preset(self, temp):
        if not self.s.get("enabled"):
            return
        if self.check_auto.isChecked():
            self.check_auto.blockSignals(True)
            self.check_auto.setChecked(False)
            self.check_auto.blockSignals(False)
            self.s["auto"] = 0
        self.apply_temperature(temp)
        self.retranslate_ui()

    def toggle_enabled(self):
        self.check_enabled.setChecked(not self.check_enabled.isChecked())

    def handle_hotkey(self, which):
        now = time.monotonic()
        if which == self._last_hotkey and now - self._last_hotkey_at < 0.18:
            return
        self._last_hotkey = which
        self._last_hotkey_at = now
        step = self._hotkey_step()
        self.adjust_temperature(step if which == "up" else -step)

    def handle_command(self, line):
        parts = (line or "").split()
        if not parts:
            return
        cmd = parts[0]
        if cmd == "warmer":
            self.adjust_temperature(self._hotkey_step())
        elif cmd == "cooler":
            self.adjust_temperature(-self._hotkey_step())
        elif cmd == "toggle":
            self.toggle_enabled()
        elif cmd == "temp" and len(parts) > 1:
            if self.can_adjust():
                self.apply_temperature(parts[1])
        else:
            log.warning("Ignored command: %s", line)
            return

    def _smooth_tick(self):
        if not self.s.get("auto") or not self.s.get("enabled"):
            return
        target = target_temp_for_time(datetime.now(), self.s)
        current = self._float_temp
        if abs(current - target) < 1:
            return
        step = SMOOTH_STEP if target > current else -SMOOTH_STEP
        new_float = current + step
        if (step > 0 and new_float > target) or (step < 0 and new_float < target):
            new_float = target
        self._float_temp = new_float
        disp = self._display_temp()
        self.s["temp"] = disp
        self.apply_engine(disp, self.s.get("color_mode", 0))
        self.tray_parent.update_icon(disp, self.s["show_label"])
        self.title_label.setText(
            f"{LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])['title']}: {disp} K"
        )
        log.info(f"Auto smooth: {round(current)}K → {disp}K (target {round(target)}K)")

    def retranslate_ui(self):
        lang = LANGUAGES.get(self.s["lang"], LANGUAGES["ru"])
        self.check_enabled.setText(lang["active"])
        self.check_label.setText(lang["show_label"])
        self.check_auto.setText(lang["auto"])
        self.check_contrast.setText(lang["contrast"])
        self.btn_as.setText(lang["as_on"] if is_autostart_enabled() else lang["as_off"])
        self.btn_settings.setText(lang["settings"])
        self.btn_back.setText(lang["back"])
        self.check_hotkeys.setText(lang["hotkeys"])
        self.schedule_warn.setText(lang["schedule_bad"])
        self.title_label.setText(f"{lang['title']}: {self.s['temp']} K")
        for widget, key in self._text_labels:
            widget.setText(lang[key])
        self._refresh_hint(lang)
        self._refresh_hotkey_buttons()

        current = self.mode_box.currentIndex()
        self.mode_box.blockSignals(True)
        self.mode_box.clear()
        self.mode_box.addItems([
            lang["mode_classic"],
            lang["mode_aggressive"],
            lang["mode_mathematical"],
        ])
        self.mode_box.setCurrentIndex(current)
        self.mode_box.blockSignals(False)

        active = self.check_enabled.isChecked() and not self.check_auto.isChecked()
        self.slider.setEnabled(active)
        self.mode_box.setEnabled(active)
        self.check_contrast.setEnabled(active)
        for button in self.preset_buttons:
            button.setEnabled(self.check_enabled.isChecked())

    def _refresh_hint(self, lang):
        warmer = cli_command("--warmer")
        cooler = cli_command("--cooler")
        if _gnome_session():
            text = lang["gnome_hint"] + "\n" + warmer + "\n" + cooler
        else:
            text = lang["cli_hint"] + "\n" + warmer + "\n" + cooler
        self.hint_label.setText(text)

    def _refresh_hotkey_buttons(self):
        if self._capturing == "up":
            self.btn_hotkey_up.setText("...")
        else:
            self.btn_hotkey_up.setText(str(self.s.get("hotkey_up", DEFAULTS["hotkey_up"])))
        if self._capturing == "down":
            self.btn_hotkey_down.setText("...")
        else:
            self.btn_hotkey_down.setText(str(self.s.get("hotkey_down", DEFAULTS["hotkey_down"])))

    def toggle_power(self, state):
        self.s["enabled"] = 1 if state else 0
        if not state:
            self.tray_parent.backend.reset()
        else:
            self.sync()
        save_settings(self.s)
        self.retranslate_ui()

    def toggle_auto(self, state):
        self.s["auto"] = 1 if state else 0
        if state:
            log.info(
                "Auto ON. current=%sK target=%sK",
                self._display_temp(),
                round(target_temp_for_time(datetime.now(), self.s)),
            )
            self._smooth_tick()
        else:
            self.sync()
        save_settings(self.s)
        self.retranslate_ui()

    def change_lang(self, name):
        self.s["lang"] = NAME_TO_CODE.get(name, "ru")
        save_settings(self.s)
        self.retranslate_ui()
        self.tray_parent.update_menu()

    def change_color_mode(self, index):
        self.s["color_mode"] = int(index)
        save_settings(self.s)
        if self.s["enabled"] and not self.s.get("auto"):
            self.apply_engine(self._display_temp(), self.s.get("color_mode", 0))

    def sync(self):
        if self.s["auto"] and self.s["enabled"]:
            return
        val = (self.slider.value() // 100) * 100
        self.s["temp"] = val
        self._float_temp = float(val)
        self.s["show_label"] = int(self.check_label.isChecked())
        self.s["contrast"] = int(self.check_contrast.isChecked())
        if self.s["enabled"]:
            self.apply_engine(val, self.s.get("color_mode", 0))
        self.tray_parent.update_icon(val, self.s["show_label"])
        self.title_label.setText(
            f"{LANGUAGES.get(self.s['lang'], LANGUAGES['ru'])['title']}: {val} K"
        )
        save_settings(self.s)

    def apply_engine(self, temp, mode=None):
        gamma = 1.3 if self.s.get("contrast", 0) else 1.0
        if mode is None:
            mode = self.s.get("color_mode", 0)
        try:
            ok = self.tray_parent.backend.apply(temp, gamma, mode)
            if not ok and sys.platform in ("win32", "darwin"):
                self.tray_parent.warn_ramp_rejected()
        except Exception as e:
            log.error(f"apply_engine: {e}")

    def toggle_as(self):
        toggle_autostart()
        self.retranslate_ui()

    def _toggle_hotkeys(self, state):
        self.s["hotkeys"] = 1 if state else 0
        save_settings(self.s)
        self.tray_parent.rebind_hotkeys()

    def _step_changed(self, value):
        self.s["hotkey_step"] = int(value)
        save_settings(self.s)

    def _commit_schedule(self):
        self.s["day_temp"] = snap_temp(self.spin_day.value())
        self.s["night_temp"] = snap_temp(self.spin_night.value())
        dawn_start = self._minutes(self.time_dawn_start)
        dawn_end = self._minutes(self.time_dawn_end)
        dusk_start = self._minutes(self.time_dusk_start)
        dusk_end = self._minutes(self.time_dusk_end)
        if dawn_start < dawn_end <= dusk_start < dusk_end:
            self.s["dawn_start"] = dawn_start
            self.s["dawn_end"] = dawn_end
            self.s["dusk_start"] = dusk_start
            self.s["dusk_end"] = dusk_end
            self.schedule_warn.setVisible(False)
        else:
            self.schedule_warn.setVisible(True)
        save_settings(self.s)

    def _begin_capture(self, which):
        self._capturing = which
        self._refresh_hotkey_buttons()
        self.grabKeyboard()

    def _cancel_capture(self):
        if not self._capturing:
            return
        self._capturing = None
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self._refresh_hotkey_buttons()

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return
        if event.key() == _KEY_ESCAPE:
            self._cancel_capture()
            event.accept()
            return
        chord = format_chord(event)
        parsed = hotkeys.parse_hotkey(chord)
        if not chord or parsed is None or not parsed[0]:
            event.accept()
            return
        key = "hotkey_up" if self._capturing == "up" else "hotkey_down"
        self._capturing = None
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self.s[key] = chord
        save_settings(self.s)
        self._refresh_hotkey_buttons()
        self.tray_parent.rebind_hotkeys()
        event.accept()

    def wheelEvent(self, event):
        widget = QApplication.widgetAt(QCursor.pos())
        current = widget
        while current:
            if isinstance(current, (QComboBox, QAbstractSpinBox, QScrollArea)):
                super().wheelEvent(event)
                return
            current = current.parentWidget()
        if not self.slider.isEnabled():
            event.ignore()
            return
        delta = 100 if event.angleDelta().y() > 0 else -100
        self.slider.setValue(
            max(self.slider.minimum(), min(self.slider.maximum(), self.slider.value() + delta))
        )
        event.accept()

    def showEvent(self, event):
        self._wait_for_mouse_release = True
        self._pending_outside_click = False
        self.outside_click_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._cancel_capture()
        self.outside_click_timer.stop()
        self.stack.setCurrentIndex(0)
        self.setFixedSize(POPUP_W, POPUP_H)
        super().hideEvent(event)

    def _set_page(self, index):
        pos = self.pos()
        self.stack.setCurrentIndex(index)
        self.setFixedSize(POPUP_W, POPUP_H)
        if self.isVisible():
            self.move(pos)

    def show_at_cursor(self):
        self.stack.setCurrentIndex(0)
        self.setFixedSize(POPUP_W, POPUP_H)
        pos = QCursor.pos()
        x = pos.x() - (POPUP_W // 2)
        y = pos.y() - POPUP_H - 20
        screen = _screen_at(pos)
        if screen is not None:
            geo = screen.availableGeometry()
            x = min(max(x, geo.x()), geo.x() + geo.width() - POPUP_W)
            y = min(max(y, geo.y()), geo.y() + geo.height() - POPUP_H)
        self.move(x, y)
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
    def __init__(self, startup_command=None):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self.on_exit)
        self._ramp_warned = False
        self._hotkey_hwnd = None
        self._hotkey_filter = None

        self.settings = load_settings()
        if (
            startup_command
            and startup_command.startswith("temp ")
            and self.settings.get("enabled")
            and not self.settings.get("auto")
        ):
            self.settings["temp"] = snap_temp(startup_command.split()[1])
        self.backend = create_backend()
        log.info(f"Gamma Slider started (PyQt{QT_VERSION})")

        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.update_menu()
        self.update_icon(self.settings["temp"], self.settings["show_label"])

        self.ipc = IpcServer(queue.Queue())
        self.grabber = hotkeys.HotkeyGrabber()
        if sys.platform == "win32":
            self._hotkey_host = QWidget()
            self._hotkey_host.setAttribute(_WA_DONT_SHOW)
            self._hotkey_hwnd = int(self._hotkey_host.winId())
            self._hotkey_filter = _WinHotkeyFilter(self._on_win_hotkey)
            self.app.installNativeEventFilter(self._hotkey_filter)

        self.popup = PopupSlider(self.settings, self)
        self.tray.activated.connect(self.clicked)
        self.tray.show()
        self.ipc.start()
        self.rebind_hotkeys()
        self._bridge = QTimer(self)
        self._bridge.timeout.connect(self._drain_bridge)
        self._bridge.start(50)
        if startup_command:
            QTimer.singleShot(800, lambda: self.popup.handle_command(startup_command))

    def on_exit(self):
        log.info("Exiting")
        if self._hotkey_hwnd:
            try:
                hotkeys.unregister_win(self._hotkey_hwnd)
            except Exception as exc:
                log.warning("UnregisterHotKey failed: %s", exc)
        self.grabber.close()
        self.ipc.close()
        self.backend.close()

    def rebind_hotkeys(self):
        enabled = bool(self.settings.get("hotkeys", 1))
        up = str(self.settings.get("hotkey_up", DEFAULTS["hotkey_up"]))
        down = str(self.settings.get("hotkey_down", DEFAULTS["hotkey_down"]))
        if sys.platform == "win32" and self._hotkey_hwnd:
            hotkeys.unregister_win(self._hotkey_hwnd)
            if enabled:
                hotkeys.register_win(self._hotkey_hwnd, hotkeys.HOTKEY_UP, up)
                hotkeys.register_win(self._hotkey_hwnd, hotkeys.HOTKEY_DOWN, down)
            return
        self.grabber.rebind(enabled, up, down)

    def _on_win_hotkey(self, hotkey_id):
        if hotkey_id == hotkeys.HOTKEY_UP:
            self.popup.handle_hotkey("up")
        elif hotkey_id == hotkeys.HOTKEY_DOWN:
            self.popup.handle_hotkey("down")

    def _drain_bridge(self):
        self._drain(self.ipc.out_queue, self.popup.handle_command)
        self._drain(self.grabber.events, self.popup.handle_hotkey)

    def _drain(self, pending, fn):
        while True:
            try:
                item = pending.get_nowait()
            except queue.Empty:
                return
            try:
                fn(item)
            except Exception as exc:
                log.error("command failed: %s", exc)

    def warn_ramp_rejected(self):
        if self._ramp_warned:
            return
        self._ramp_warned = True
        log.warning("Display driver rejected the gamma ramp")
        try:
            self.tray.showMessage(
                "Gamma Slider",
                "Display driver rejected the gamma ramp. Disable Night Light / Night Shift / HDR and try again.",
                _TRAY_WARNING,
                8000,
            )
        except Exception as e:
            log.error(f"tray warning: {e}")

    def update_menu(self):
        self.menu.clear()
        lang = LANGUAGES.get(self.settings.get("lang", "ru"), LANGUAGES["ru"])
        self.menu.addAction(lang["quit"]).triggered.connect(self.app.quit)

    def update_icon(self, val, show):
        pix = QPixmap(64, 64)
        pix.fill(_TRANSPARENT)
        p = QPainter(pix)
        p.setRenderHint(_ANTIALIAS)
        p.setBrush(QColor("#fb923c"))
        p.setPen(_NO_PEN)
        p.drawRoundedRect(2, 2, 60, 60, 8, 8)
        if show:
            text = str(val // 100)
            p.setPen(QColor("black"))
            p.setFont(QFont("Verdana", 22 if len(text) >= 3 else 28, _BOLD))
            p.drawText(pix.rect(), _ALIGN_CENTER, text)
        p.end()
        self.tray.setIcon(QIcon(pix))
        self.tray.setToolTip(f"{val} K")

    def clicked(self, reason):
        if reason == _TRAY_TRIGGER:
            if self.popup.isVisible():
                self.popup.hide_from_tray()
            elif not self.popup.should_suppress_tray_show():
                self.popup.show_at_cursor()
        elif reason == _TRAY_MIDDLE:
            self.popup.toggle_enabled()

def main():
    command = parse_cli(sys.argv[1:])
    if not acquire_single_instance():
        if not command:
            sys.exit(0)
        if send_command(command):
            sys.exit(0)
        print("gamma-slider is not accepting commands", file=sys.stderr)
        sys.exit(1)
    tray = TrayApp(command)
    sys.exit(tray.app.exec())

if __name__ == "__main__":
    main()
