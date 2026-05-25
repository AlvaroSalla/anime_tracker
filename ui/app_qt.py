import sys
import os
import time
import requests
from io import BytesIO
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget,
    QScrollArea, QGridLayout, QLineEdit,
    QComboBox, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor
from PIL import Image

BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

import session
from database.queries import (
    agregar_anime,
    actualizar_caps_anime,
    actualizar_estado_anime,
    actualizar_score_anime,
    eliminar_anime_usuario,
    obtener_animes_usuario,
    register_user,
    login_user,
)
from services.anime_services import (
    ANIMES_POPULARES_TOTAL,
    obtener_animes_populares,
    sincronizar_animes_populares_background,
)

# ── Colores / Tema ────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "BG": "#0f172a", "SURFACE": "#1e293b", "BORDER": "#475569",
        "TEXT": "#f1f5f9", "MUTED": "#94a3b8",
        "BLUE": "#2563eb", "TEAL": "#0f766e", "RED": "#dc2626", "GREEN": "#22c55e",
    },
    "light": {
        "BG": "#e2e8f0", "SURFACE": "#f8fafc", "BORDER": "#cbd5e1",
        "TEXT": "#0f172a", "MUTED": "#475569",
        "BLUE": "#2563eb", "TEAL": "#0f766e", "RED": "#dc2626", "GREEN": "#22c55e",
    },
}

_theme_mode = "dark"

def _apply_theme(mode):
    global _theme_mode, BG, SURFACE, BORDER, TEXT, MUTED, BLUE, TEAL, RED, GREEN, STYLE
    _theme_mode = mode
    c = THEMES[mode]
    BG = c["BG"]; SURFACE = c["SURFACE"]; BORDER = c["BORDER"]
    TEXT = c["TEXT"]; MUTED = c["MUTED"]
    BLUE = c["BLUE"]; TEAL = c["TEAL"]; RED = c["RED"]; GREEN = c["GREEN"]
    STYLE = f"""
QMainWindow, QWidget  {{ background: {BG}; color: {TEXT}; font-family: Segoe UI; }}
QScrollArea           {{ border: none; background: transparent; }}
QScrollBar:vertical   {{ background: {BG}; width: 8px; border-radius: 4px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

def toggle_theme():
    new = "light" if _theme_mode == "dark" else "dark"
    _apply_theme(new)

_apply_theme("dark")

STATUS_COLORS = {
    "En proceso": "#2563eb",
    "Completo":   "#0f766e",
    "Planeado":   "#7c3aed",
    "En espera":  "#f59e0b",
    "Abandonado": "#dc2626",
}

# ── Traducciones ──────────────────────────────────────────────────────────────
class Lang:
    _current = "en"

    _strings = {
        "en": {
            "app_title": "ANIME TRACKER",
            "loading_title": "Anime Tracker",
            "loading_status": "Loading anime catalog...",
            "loading_progress": "Preloaded images: {done}/{total}",
            "preload_status": "Preloading the first 50 images...",
            "loading_img": "Loading...",
            "no_image": "No image",
            "open": "Open",
            "back": "Back",
            "save": "Save anime",
            "save_changes": "Save changes",
            "delete": "Delete",
            "close": "Close",
            "exit": "Exit",
            "next": "Next →",
            "prev": "← Previous",
            "search_anime": "Search anime...",
            "search_saved": "Search saved...",
            "no_results": "No animes found with that filter.",
            "no_saved": "No saved animes to show.",
            "no_results_short": "No results",
            "page_info": "Page {page}/{total} · {start}-{end} of {count}",
            "all": "All",
            "watching": "Watching",
            "completed": "Completed",
            "planned": "Planned",
            "on_hold": "On Hold",
            "dropped": "Dropped",
            "airing": "Airing",
            "finished": "Finished",
            "not_yet_aired": "Not yet aired",
            "cancelled": "Cancelled",
            "paused": "Paused",
            "unknown_status": "Unknown",
            "episodes": "Episodes",
            "caps_total": "Total episodes: {n}",
            "caps_fmt": "Episodes: {v}/{t}",
            "score": "Score: {s}",
            "status": "Status",
            "score_label": "Score",
            "episodes_label": "Episodes",
            "state_label": "State",
            "num_error": "Episodes and score must be numbers.",
            "duplicate_error": "That anime is already saved.",
            "caps_negative_error": "Episodes cannot be negative.",
            "caps_exceed_error": "Episodes cannot exceed the total.",
            "score_range_error": "Score must be between 1 and 10.",
            "state_change_error": "To change the status, first lower the episodes.",
            "save_success": "Anime saved!",
            "no_name": "Unnamed",
            "main_title": "Anime Tracker",
            "main_sub": "Your anime library, organized and ready to keep watching.",
            "add_anime": "Add anime",
            "add_detail": "Search and add series",
            "saved_anime": "Saved animes",
            "saved_detail": "Review and edit progress",
            "add_view_title": "Add anime",
            "add_view_sub": "Choose a popular anime to start tracking it.",
            "saved_view_title": "Saved animes",
            "saved_view_sub": "Check your progress, watched episodes and current status.",
            "es": "Spanish",
            "en": "English",
            "pt": "Portuguese",
        },
        "es": {
            "app_title": "ANIME TRACKER",
            "loading_title": "Anime Tracker",
            "loading_status": "Cargando catálogo de animes...",
            "loading_progress": "Imágenes precargadas: {done}/{total}",
            "preload_status": "Precargando las primeras 50 imágenes...",
            "loading_img": "Cargando...",
            "no_image": "Sin imagen",
            "open": "Abrir",
            "back": "Volver",
            "save": "Guardar anime",
            "save_changes": "Guardar cambios",
            "delete": "Eliminar",
            "close": "Cerrar",
            "exit": "Salir",
            "next": "Siguiente →",
            "prev": "← Anterior",
            "search_anime": "Buscar anime...",
            "search_saved": "Buscar guardado...",
            "no_results": "No se encontraron animes con ese filtro.",
            "no_saved": "No hay animes guardados para mostrar.",
            "no_results_short": "Sin resultados",
            "page_info": "Página {page}/{total} · {start}-{end} de {count}",
            "all": "Todos",
            "watching": "En proceso",
            "completed": "Completo",
            "planned": "Planeado",
            "on_hold": "En espera",
            "dropped": "Abandonado",
            "airing": "En emisión",
            "finished": "Terminado",
            "not_yet_aired": "No estrenado",
            "cancelled": "Cancelado",
            "paused": "En pausa",
            "unknown_status": "Desconocido",
            "episodes": "Capítulos",
            "caps_total": "Capítulos totales: {n}",
            "caps_fmt": "Capítulos: {v}/{t}",
            "score": "Score: {s}",
            "status": "Estado",
            "score_label": "Score",
            "episodes_label": "Capítulos",
            "state_label": "Estado",
            "num_error": "Capítulos y score tienen que ser números.",
            "duplicate_error": "Ese anime ya está guardado.",
            "caps_negative_error": "Los capítulos no pueden ser negativos.",
            "caps_exceed_error": "Los capítulos no pueden superar el total.",
            "score_range_error": "El score tiene que estar entre 1 y 10.",
            "state_change_error": "Para cambiar el estado bajá primero los capítulos.",
            "save_success": "¡Anime guardado!",
            "no_name": "Sin nombre",
            "main_title": "Anime Tracker",
            "main_sub": "Tu biblioteca de anime, organizada y lista para seguir mirando.",
            "add_anime": "Agregar anime",
            "add_detail": "Buscar y sumar series",
            "saved_anime": "Ver animes guardados",
            "saved_detail": "Revisar y editar progreso",
            "add_view_title": "Agregar anime",
            "add_view_sub": "Elegí uno de los animes populares para empezar a guardarlo.",
            "saved_view_title": "Animes guardados",
            "saved_view_sub": "Revisá tu progreso, capítulos vistos y estado actual.",
            "es": "Español",
            "en": "Inglés",
            "pt": "Portugués",
        },
        "pt": {
            "app_title": "ANIME TRACKER",
            "loading_title": "Anime Tracker",
            "loading_status": "Carregando catálogo de animes...",
            "loading_progress": "Imagens pré-carregadas: {done}/{total}",
            "preload_status": "Pré-carregando as primeiras 50 imagens...",
            "loading_img": "Carregando...",
            "no_image": "Sem imagem",
            "open": "Abrir",
            "back": "Voltar",
            "save": "Salvar anime",
            "save_changes": "Salvar alterações",
            "delete": "Excluir",
            "close": "Fechar",
            "exit": "Sair",
            "next": "Seguinte →",
            "prev": "← Anterior",
            "search_anime": "Buscar anime...",
            "search_saved": "Buscar salvos...",
            "no_results": "Nenhum anime encontrado com esse filtro.",
            "no_saved": "Nenhum anime salvo para mostrar.",
            "no_results_short": "Sem resultados",
            "page_info": "Página {page}/{total} · {start}-{end} de {count}",
            "all": "Todos",
            "watching": "Em andamento",
            "completed": "Completo",
            "planned": "Planejado",
            "on_hold": "Em espera",
            "dropped": "Abandonado",
            "airing": "Em exibição",
            "finished": "Finalizado",
            "not_yet_aired": "Não lançado",
            "cancelled": "Cancelado",
            "paused": "Em pausa",
            "unknown_status": "Desconhecido",
            "episodes": "Capítulos",
            "caps_total": "Total de episódios: {n}",
            "caps_fmt": "Capítulos: {v}/{t}",
            "score": "Score: {s}",
            "status": "Status",
            "score_label": "Score",
            "episodes_label": "Capítulos",
            "state_label": "Estado",
            "num_error": "Capítulos e score devem ser números.",
            "duplicate_error": "Esse anime já está salvo.",
            "caps_negative_error": "Os capítulos não podem ser negativos.",
            "caps_exceed_error": "Os capítulos não podem exceder o total.",
            "score_range_error": "O score deve estar entre 1 e 10.",
            "state_change_error": "Para mudar o status, primeiro reduza os capítulos.",
            "save_success": "Anime salvo!",
            "no_name": "Sem nome",
            "main_title": "Anime Tracker",
            "main_sub": "Sua biblioteca de anime, organizada e pronta para acompanhar.",
            "add_anime": "Adicionar anime",
            "add_detail": "Buscar e adicionar séries",
            "saved_anime": "Animes salvos",
            "saved_detail": "Rever e editar progresso",
            "add_view_title": "Adicionar anime",
            "add_view_sub": "Escolha um anime popular para começar a salvá-lo.",
            "saved_view_title": "Animes salvos",
            "saved_view_sub": "Verifique seu progresso, episódios assistidos e status atual.",
            "es": "Espanhol",
            "en": "Inglês",
            "pt": "Português",
        },
    }

    @classmethod
    def tr(cls, key, **kwargs):
        val = cls._strings[cls._current].get(key, key)
        if kwargs:
            return val.format(**kwargs)
        return val

    @classmethod
    def set(cls, code):
        if code in cls._strings:
            cls._current = code

    @classmethod
    def current(cls):
        return cls._current

    _status_key_map = {
        "En proceso": "watching",
        "Completo":   "completed",
        "Planeado":   "planned",
        "En espera":  "on_hold",
        "Abandonado": "dropped",
    }

    @classmethod
    def translate_status(cls, db_status):
        key = cls._status_key_map.get(db_status)
        return cls.tr(key) if key else db_status

    @classmethod
    def reverse_status(cls, translated):
        for db_val, key in cls._status_key_map.items():
            if cls.tr(key) == translated:
                return db_val
        return translated

    @classmethod
    def status_labels(cls):
        c = cls._current
        return {
            "watching":  cls.tr("watching"),
            "completed": cls.tr("completed"),
            "planned":   cls.tr("planned"),
            "on_hold":   cls.tr("on_hold"),
            "dropped":   cls.tr("dropped"),
        }

    @classmethod
    def api_status_map(cls):
        c = cls._current
        return {
            cls.tr("airing"):        "RELEASING",
            cls.tr("finished"):      "FINISHED",
            cls.tr("not_yet_aired"): "NOT_YET_RELEASED",
            cls.tr("cancelled"):     "CANCELLED",
            cls.tr("paused"):        "HIATUS",
        }

    @classmethod
    def api_status_labels(cls):
        c = cls._current
        return {
            "FINISHED":         (cls.tr("finished"),      "#22c55e"),
            "RELEASING":        (cls.tr("airing"),        "#2563eb"),
            "NOT_YET_RELEASED": (cls.tr("not_yet_aired"), "#f59e0b"),
            "CANCELLED":        (cls.tr("cancelled"),     "#dc2626"),
            "HIATUS":           (cls.tr("paused"),        "#f59e0b"),
        }


class LangDropdown(QFrame):
    language_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(220)
        self.setStyleSheet(
            f"QFrame{{ background:{SURFACE}; border:2px solid {BORDER}; border-radius:8px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        for code in ["es", "en", "pt"]:
            row = QWidget()
            row.setFixedHeight(52)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setStyleSheet(
                f"QWidget{{background:transparent;border-radius:6px;}}"
                f"QWidget:hover{{background:{BORDER};}}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 0, 10, 0)
            rl.setSpacing(12)

            flag = QLabel()
            flag.setFixedSize(60, 40)
            flag.setStyleSheet("background:transparent;border:none;")
            path = os.path.join(BASE_DIR, "resources", f"flag_{code}.jpg")
            pix = QPixmap(path)
            if pix.isNull():
                pix = QPixmap(60, 40)
                pix.fill(Qt.GlobalColor.gray)
            flag.setPixmap(pix.scaled(60, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

            name = QLabel(Lang.tr(code))
            name.setStyleSheet(f"font-size:16px;color:{TEXT};background:transparent;border:none;")

            rl.addWidget(flag)
            rl.addWidget(name)
            rl.addStretch()

            row.mousePressEvent = lambda e, c=code: self.language_selected.emit(c)
            layout.addWidget(row)


# ── Threads ───────────────────────────────────────────────────────────────────
class WorkerThread(QThread):
    finished = pyqtSignal(list)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn   = fn
        self.args = args

    def run(self):
        self.finished.emit(self.fn(*self.args))


class PreloadWorker(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()

    def __init__(self, animes, cache, start_idx, count, delay=0):
        super().__init__()
        self.animes    = animes
        self.cache     = cache
        self._start    = start_idx
        self.count     = count
        self.delay     = delay
        self._running  = True

    def stop(self):
        self._running = False

    def run(self):
        end = min(self._start + self.count, len(self.animes))
        done = 0
        for i in range(self._start, end):
            if not self._running:
                return
            anime = self.animes[i]
            url = anime.get("coverImage", {}).get("medium")
            if url and url not in self.cache:
                try:
                    r = requests.get(url, timeout=8)
                    r.raise_for_status()
                    img = Image.open(BytesIO(r.content)).convert("RGB")
                    self.cache[url] = img
                except Exception:
                    pass
            done += 1
            if self.delay and done % 20 == 0:
                time.sleep(self.delay)
            if done % 25 == 0:
                self.progress.emit(done, self.count)
        self.finished.emit()


class ImageLoader(QThread):
    loaded = pyqtSignal(object, str)

    def __init__(self, url, cache):
        super().__init__()
        self.url   = url
        self.cache = cache

    def run(self):
        if self.url in self.cache:
            self.loaded.emit(self.cache[self.url], self.url)
            return
        try:
            r = requests.get(self.url, timeout=8)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            self.cache[self.url] = img
            self.loaded.emit(img, self.url)
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────
def pil_to_pixmap(pil_image, w, h):
    img = pil_image.resize((w, h), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue())
    return pixmap


def label_btn(text, color, w=None, h=38):
    btn = QPushButton(text)
    if w:
        btn.setFixedSize(w, h)
    else:
        btn.setFixedHeight(h)
    btn.setStyleSheet(f"QPushButton {{ background: {color}; border-radius: 8px; color: white; font-size: 13px; font-weight: bold; }}")
    return btn


# ── Widgets reutilizables ─────────────────────────────────────────────────────
class ImageLabel(QLabel):
    def __init__(self, w, h):
        super().__init__(Lang.tr("loading_img"))
        self.setFixedSize(w, h)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"background: {BG}; border-radius: 7px; color: {MUTED}; font-size: 11px;")
        self.img_w = w
        self.img_h = h
        self.expected_url = None

    def set_image(self, pil_image, url):
        if url != self.expected_url:
            return
        self.setPixmap(pil_to_pixmap(pil_image, self.img_w, self.img_h))
        self.setText("")

    def load(self, url, cache, loader_refs):
        self.expected_url = url
        if not url:
            self.setText(Lang.tr("no_image"))
            return
        if url in cache:
            self.set_image(cache[url], url)
            return
        loader = ImageLoader(url, cache)
        loader.loaded.connect(self.set_image)
        loader.start()
        loader_refs.append(loader)


class DropdownEntry(QFrame):
    value_changed = pyqtSignal(str)

    def __init__(self, options, initial="", readonly=True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setStyleSheet(f"QFrame {{ background: {BG}; border-radius: 6px; border: 2px solid {BORDER}; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)

        self.entry = QLineEdit(initial)
        self.entry.setStyleSheet(f"background: transparent; border: none; color: {TEXT}; font-size: 14px; font-weight: bold;")
        if readonly:
            self.entry.setReadOnly(True)
        layout.addWidget(self.entry)

        arrow = QPushButton("▼")
        arrow.setFixedSize(24, 42)
        arrow.setStyleSheet(f"background: transparent; border: none; color: {TEXT}; font-size: 12px;")
        arrow.clicked.connect(self._toggle)
        layout.addWidget(arrow)

        self.options   = options
        self.dropdown  = None

    def _toggle(self):
        if self.dropdown and self.dropdown.isVisible():
            self.dropdown.hide()
            return
        self.dropdown = QFrame(self.window(), Qt.WindowType.Popup)
        self.dropdown.setStyleSheet(f"QFrame {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(min(len(self.options) * 34 + 10, 200))
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollBar:vertical { background: #1e293b; width: 6px; border-radius: 3px; } QScrollBar::handle:vertical { background: #475569; border-radius: 3px; min-height: 20px; } QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(0)
        for opt in self.options:
            btn = QPushButton(opt)
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {TEXT}; text-align: left; padding: 6px 10px; border: none; font-size: 13px; }} QPushButton:hover {{ background: {BORDER}; border-radius: 4px; }}")
            btn.clicked.connect(lambda _, o=opt: self._select(o))
            v.addWidget(btn)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self.dropdown)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        gx = self.mapToGlobal(self.rect().bottomLeft())
        self.dropdown.move(gx)
        self.dropdown.setFixedWidth(self.width())
        self.dropdown.show()

    def _select(self, value):
        self.entry.setText(value)
        if self.dropdown:
            self.dropdown.hide()
        self.value_changed.emit(value)

    def get(self):
        return self.entry.text()

    def set(self, value):
        self.entry.setText(value)


# ── Vista: Carga ───────────────────────────────────────────────────────────────
class LoadingView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(Lang.tr("loading_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 52px; font-weight: bold; color: {TEXT};")

        self.status = QLabel(Lang.tr("loading_status"))
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"font-size: 16px; color: {MUTED};")

        self.info = QLabel("")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info.setStyleSheet(f"font-size: 14px; color: {MUTED};")

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(self.status)
        layout.addSpacing(8)
        layout.addWidget(self.info)

    def set_status(self, text):
        self.status.setText(text)

    def set_info(self, text):
        self.info.setText(text)

    def set_progress(self, done, total):
        self.info.setText(Lang.tr("loading_progress", done=done, total=total))


# ── Vista: Login / Registro ────────────────────────────────────────────────────
class LoginView(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.register_mode = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        title = QLabel(Lang.tr("app_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 52px; font-weight: bold; color: {TEXT};")
        layout.addWidget(title)
        layout.addSpacing(30)

        card = QFrame()
        card.setFixedSize(380, 390)
        card.setStyleSheet(f"QFrame {{ background: {SURFACE}; border-radius: 12px; border: 2px solid {BORDER}; }}")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(14)

        self.title_label = QLabel("Iniciar sesión")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {TEXT}; border: none; background: transparent;")
        card_layout.addWidget(self.title_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")
        self.username_input.setFixedHeight(44)
        self.username_input.setStyleSheet(
            f"QLineEdit {{ background: {BG}; border: 2px solid {BORDER}; border-radius: 8px; color: {TEXT}; font-size: 14px; padding: 0 12px; }}"
        )
        card_layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(44)
        self.password_input.setStyleSheet(
            f"QLineEdit {{ background: {BG}; border: 2px solid {BORDER}; border-radius: 8px; color: {TEXT}; font-size: 14px; padding: 0 12px; }}"
        )
        card_layout.addWidget(self.password_input)

        self.remember_cb = QCheckBox("Recordarme en este equipo")
        self.remember_cb.setStyleSheet(
            f"QCheckBox {{ color: {TEXT}; font-size: 13px; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid {BORDER}; border-radius: 3px; background: {BG}; }}"
            f"QCheckBox::indicator:checked {{ background: {BLUE}; border-color: {BLUE}; }}"
        )
        card_layout.addWidget(self.remember_cb)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #dc2626; font-size: 12px; border: none; background: transparent;")
        card_layout.addWidget(self.error_label)

        self.action_btn = QPushButton("Iniciar sesión")
        self.action_btn.setFixedHeight(44)
        self.action_btn.setStyleSheet(
            f"QPushButton {{ background: {BLUE}; border-radius: 8px; color: white; font-size: 15px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #1d4ed8; }}"
        )
        self.action_btn.clicked.connect(self._do_action)
        card_layout.addWidget(self.action_btn)

        self.toggle_btn = QPushButton("Crear cuenta nueva")
        self.toggle_btn.setFixedHeight(36)
        self.toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED}; font-size: 13px; border: none; }}"
            f"QPushButton:hover {{ color: {TEXT}; }}"
        )
        self.toggle_btn.clicked.connect(self._toggle_mode)
        card_layout.addWidget(self.toggle_btn)

        layout.addWidget(card)

        self.password_input.returnPressed.connect(self._do_action)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())

    def _toggle_mode(self):
        self.register_mode = not self.register_mode
        self.error_label.setText("")
        if self.register_mode:
            self.title_label.setText("Crear cuenta")
            self.action_btn.setText("Registrarse")
            self.toggle_btn.setText("Ya tengo cuenta")
        else:
            self.title_label.setText("Iniciar sesión")
            self.action_btn.setText("Iniciar sesión")
            self.toggle_btn.setText("Crear cuenta nueva")

    def _do_action(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            self.error_label.setText("Completá todos los campos.")
            return
        if self.register_mode:
            ok, msg = register_user(username, password)
            if ok:
                login_user(username, password)
                if self.remember_cb.isChecked():
                    session.save_remember_session(session.current_user_id, session.current_username)
                self.on_login_success()
            else:
                self.error_label.setText(msg)
        else:
            ok, msg = login_user(username, password)
            if ok:
                if self.remember_cb.isChecked():
                    session.save_remember_session(session.current_user_id, session.current_username)
                self.on_login_success()
            else:
                self.error_label.setText(msg)

    def reset(self):
        self.username_input.clear()
        self.password_input.clear()
        self.error_label.setText("")
        self.register_mode = False
        self.remember_cb.setChecked(False)
        self.title_label.setText("Iniciar sesión")
        self.action_btn.setText("Iniciar sesión")
        self.toggle_btn.setText("Crear cuenta nueva")


# ── Vista: Menú principal ─────────────────────────────────────────────────────
class ActionCard(QFrame):
    def __init__(self, title, detail, color, on_click):
        super().__init__()
        self.setFixedSize(290, 164)
        self.setStyleSheet(f"QFrame {{ background: {SURFACE}; border-radius: 8px; border: 2px solid {BORDER}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(4)

        t = QLabel(title)
        t.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT}; border: none;")
        layout.addWidget(t)

        d = QLabel(detail)
        d.setStyleSheet(f"font-size: 14px; color: {MUTED}; border: none;")
        layout.addWidget(d)

        layout.addStretch()

        btn = QPushButton(Lang.tr("open"))
        btn.setFixedSize(128, 38)
        btn.setStyleSheet(f"QPushButton {{ background: {color}; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; }}")
        btn.clicked.connect(on_click)
        layout.addWidget(btn)


class MainView(QWidget):
    def __init__(self, on_add, on_saved, on_exit, on_language=None, on_theme=None, on_logout=None):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setFixedHeight(56)
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(24, 0, 24, 0)

        self.user_label = QLabel(f"👤 {session.current_username}" if session.current_username else "")
        self.user_label.setStyleSheet(f"font-size: 14px; color: {MUTED}; background: transparent;")
        tl.addWidget(self.user_label)

        self.logout_btn = QPushButton("Cerrar sesión")
        self.logout_btn.setFixedSize(120, 34)
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED}; font-size: 13px; border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {RED}; background: {BORDER}; }}"
        )
        self.logout_btn.clicked.connect(on_logout) if on_logout else None
        tl.addWidget(self.logout_btn)
        tl.addStretch()

        self.gear = QPushButton("\u2699")
        self.gear.setFixedSize(40, 40)
        self.gear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gear.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED}; font-size: 22px; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {TEXT}; background: {BORDER}; }}"
        )
        self.theme_btn = QPushButton("\u2600" if _theme_mode == "dark" else "\u263E")
        self.theme_btn.setFixedSize(40, 40)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED}; font-size: 20px; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {TEXT}; background: {BORDER}; }}"
        )
        tl.addWidget(self.theme_btn)
        tl.addSpacing(4)
        tl.addWidget(self.gear)
        main_layout.addWidget(top_bar)

        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(12)
        cl.addSpacing(60)

        title = QLabel(Lang.tr("main_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 52px; font-weight: bold; color: {TEXT};")
        cl.addWidget(title)

        sub = QLabel(Lang.tr("main_sub"))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size: 16px; color: {MUTED};")
        cl.addWidget(sub)

        cl.addSpacing(50)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.setSpacing(80)
        row.addWidget(ActionCard(Lang.tr("add_anime"), Lang.tr("add_detail"), BLUE, on_add))
        row.addWidget(ActionCard(Lang.tr("saved_anime"), Lang.tr("saved_detail"), TEAL, on_saved))
        cl.addLayout(row)
        cl.addStretch()

        main_layout.addWidget(center, stretch=1)

        bottom = QWidget()
        bottom.setFixedHeight(60)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 32, 0)
        bl.addStretch()
        exit_btn = label_btn(Lang.tr("exit"), "#475569", w=150)
        exit_btn.clicked.connect(on_exit)
        bl.addWidget(exit_btn)
        main_layout.addWidget(bottom)

        self.dropdown = LangDropdown()
        self.dropdown.language_selected.connect(lambda code: self.dropdown.hide())
        if on_language:
            self.dropdown.language_selected.connect(on_language)
        self.gear.clicked.connect(self._toggle_dropdown)
        if on_theme:
            self.theme_btn.clicked.connect(lambda: on_theme())

    def _toggle_dropdown(self):
        d = self.dropdown
        if d.isVisible():
            d.hide()
            return
        g = self.gear.mapToGlobal(QPoint(self.gear.width(), 0))
        d.move(g.x() - d.width(), g.y() + 4)
        d.show()


# ── Vista: Agregar anime ──────────────────────────────────────────────────────
class AnimeCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, anime, cache, loader_refs, selected=False):
        super().__init__()
        self.anime = anime
        self.setFixedSize(158, 254)
        self.setObjectName("AnimeCard")
        color = GREEN if selected else BORDER
        hover = "" if selected else " QFrame#AnimeCard:hover { border-color: #60a5fa; }"
        self.setStyleSheet(f"QFrame#AnimeCard {{ background: {SURFACE}; border-radius: 8px; border: 2px solid {color}; }}" + hover)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.img = ImageLabel(118, 166)
        url = anime.get("coverImage", {}).get("medium")
        self.img.load(url, cache, loader_refs)
        layout.addWidget(self.img, alignment=Qt.AlignmentFlag.AlignCenter)

        name = anime.get("title", {}).get("romaji", Lang.tr("no_name"))
        if len(name) > 46:
            name = name[:43] + "..."
        lbl = QLabel(name)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedHeight(48)
        lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT}; border: none; background: transparent;")
        layout.addWidget(lbl)

    def mousePressEvent(self, event):
        self.clicked.emit(self.anime)


class AddAnimeView(QWidget):
    def __init__(self, animes, cache, loader_refs, on_back):
        super().__init__()
        self.animes       = animes
        self.filtered     = animes
        self.cache        = cache
        self.loader_refs  = loader_refs
        self.panel        = None
        self.selected_id  = None
        self.page         = 0
        self.page_size    = 50
        self.columns      = 6

        layout = QVBoxLayout(self)
        layout.setContentsMargins(68, 12, 68, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(74)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)

        tc = QVBoxLayout()
        t = QLabel(Lang.tr("add_view_title"))
        t.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT};")
        s = QLabel(Lang.tr("add_view_sub"))
        s.setStyleSheet(f"font-size: 11px; color: {MUTED};")
        tc.addWidget(t)
        tc.addWidget(s)
        hl.addLayout(tc)
        hl.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText(Lang.tr("search_anime"))
        self.search.setFixedSize(300, 42)
        self.search.setStyleSheet(f"QLineEdit {{ background: transparent; border: 2px solid {BORDER}; border-radius: 8px; color: {TEXT}; font-size: 14px; padding: 0 12px; }}")
        self.search.textChanged.connect(self._filter)
        hl.addWidget(self.search)

        self.status_cb = QComboBox()
        self.status_cb.addItems([Lang.tr("all"), Lang.tr("airing"), Lang.tr("finished"), Lang.tr("not_yet_aired"), Lang.tr("cancelled"), Lang.tr("paused")])
        self.status_cb.setFixedSize(154, 42)
        self.status_cb.setStyleSheet(f"QComboBox {{ background: {SURFACE}; border: 2px solid {BORDER}; border-radius: 8px; color: {TEXT}; font-size: 14px; padding: 0 12px; }} QComboBox::drop-down {{ border: none; }} QComboBox QAbstractItemView {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; selection-background-color: {BORDER}; }}")
        self.status_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self.status_cb)
        layout.addWidget(header)
        layout.addSpacing(18)

        # Contenido: grid + panel
        self.content = QHBoxLayout()
        self.content.setSpacing(18)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet(f"background: {BG};")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll.setWidget(self.grid_widget)
        self.content.addWidget(self.scroll)
        layout.addLayout(self.content)

        # Bottom bar
        bottom = QWidget()
        bottom.setFixedHeight(60)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)

        back = label_btn(Lang.tr("back"), "#475569", w=120)
        back.clicked.connect(on_back)
        bl.addWidget(back)
        bl.addStretch()

        self.page_lbl = QLabel("")
        self.page_lbl.setStyleSheet(f"font-size: 15px; color: {TEXT};")
        bl.addWidget(self.page_lbl)
        bl.addSpacing(40)

        self.prev_btn = QPushButton(Lang.tr("prev"))
        self.prev_btn.setFixedSize(110, 38)
        self.prev_btn.clicked.connect(lambda: self._change_page(-1))
        bl.addWidget(self.prev_btn)

        self.next_btn = QPushButton(Lang.tr("next"))
        self.next_btn.setFixedSize(110, 38)
        self.next_btn.clicked.connect(lambda: self._change_page(1))
        bl.addWidget(self.next_btn)

        layout.addWidget(bottom)
        self._render_page()

    def _filter(self):
        query  = self.search.text().strip().lower()
        api_map = Lang.api_status_map()
        target = api_map.get(self.status_cb.currentText())
        self.filtered = [
            a for a in self.animes
            if (not query  or query  in a.get("title", {}).get("romaji", "").lower())
            and (not target or a.get("status") == target)
        ]
        self.page = 0
        self._render_page()

    def _change_page(self, d):
        total = max(1, -(-len(self.filtered) // self.page_size))
        self.page = max(0, min(self.page + d, total - 1))
        self._render_page()

    def _render_page(self):
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        start = self.page * self.page_size
        items = self.filtered[start:start + self.page_size]

        if not items:
            lbl = QLabel(Lang.tr("no_results"))
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 16px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(lbl, 0, 0, 1, self.columns)
        else:
            for i, anime in enumerate(items):
                card = AnimeCard(anime, self.cache, self.loader_refs,
                                 selected=(anime.get("id") == self.selected_id))
                card.clicked.connect(self._open_panel)
                self.grid_layout.addWidget(card, i // self.columns, i % self.columns)

        total   = max(1, -(-len(self.filtered) // self.page_size))
        start_n = self.page * self.page_size + 1
        end_n   = min((self.page + 1) * self.page_size, len(self.filtered))
        self.page_lbl.setText(Lang.tr("page_info", page=self.page + 1, total=total, start=start_n, end=end_n, count=len(self.filtered)))

        on_color  = TEXT
        off_color = MUTED
        self.prev_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {on_color if self.page > 0 else off_color}; border: none; font-size: 14px; }}")
        self.next_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {on_color if self.page < total - 1 else off_color}; border: none; font-size: 14px; }}")

    def _open_panel(self, anime):
        if self.panel:
            self.panel.deleteLater()
            self.panel = None

        self.selected_id = anime.get("id")
        av = self.width() - 136 - 18 - 430
        self.columns     = max(1, av // 170)
        self.page_size   = 40
        self.panel = AddAnimePanel(anime, self.cache, self.loader_refs)
        self.panel.closed.connect(self._close_panel)
        self.panel.saved.connect(self._on_saved)
        self.content.addWidget(self.panel)
        self._render_page()

    def _close_panel(self):
        if self.panel:
            self.panel.deleteLater()
            self.panel = None
        self.selected_id = None
        av = self.width() - 136
        self.columns = max(1, av // 170)
        self.page_size = 50
        self._render_page()

    def _on_saved(self, name):
        self._close_panel()

    def reflow(self):
        cols = max(1, self.scroll.viewport().width() // 170)
        if cols != self.columns:
            self.columns = cols
            self._render_page()


# ── Panel lateral: agregar anime ──────────────────────────────────────────────
class AddAnimePanel(QFrame):
    closed  = pyqtSignal()
    saved   = pyqtSignal(str)

    def __init__(self, anime, cache, loader_refs):
        super().__init__()
        self.anime = anime
        self.setFixedWidth(430)
        self.setStyleSheet(f"QFrame {{ background: {SURFACE}; border-radius: 8px; border: 2px solid {BORDER}; }}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(10)

        close_btn = label_btn(Lang.tr("close"), "#475569", w=92, h=34)
        close_btn.clicked.connect(self.closed.emit)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        img = ImageLabel(132, 186)
        url = anime.get("coverImage", {}).get("medium")
        img.load(url, cache, loader_refs)
        layout.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel(anime.get("title", {}).get("romaji", Lang.tr("no_name")))
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT};")
        layout.addWidget(title)

        status_key = anime.get("status", "")
        api_labels = Lang.api_status_labels()
        status_text, status_color = api_labels.get(status_key, (Lang.tr("unknown_status"), "#64748b"))
        status_lbl = QLabel(status_text)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setFixedHeight(26)
        status_lbl.setStyleSheet(f"background: {status_color}; border-radius: 7px; color: white; font-size: 12px; font-weight: bold;")
        layout.addWidget(status_lbl)

        caps_total  = anime.get("episodes")
        next_airing = anime.get("nextAiringEpisode")
        next_ep     = next_airing.get("episode") if isinstance(next_airing, dict) else None
        caps_disp   = (next_ep - 1) if next_ep else None

        is_airing = status_key == "RELEASING"

        if not caps_total and not isinstance(next_airing, dict) and is_airing:
            try:
                r = requests.post("https://graphql.anilist.co", json={
                    "query": "query($id:Int){Media(id:$id,type:ANIME){episodes nextAiringEpisode{episode}}}",
                    "variables": {"id": anime.get("id")}
                }, timeout=10)
                d = r.json()
                m = d.get("data", {}).get("Media", {})
                if m.get("episodes"):
                    anime["episodes"] = caps_total = m["episodes"]
                na = m.get("nextAiringEpisode")
                if isinstance(na, dict) and na.get("episode"):
                    anime["nextAiringEpisode"] = next_airing = na
                    next_ep = na["episode"]
                    caps_disp = next_ep - 1
            except Exception:
                pass

        if caps_total:
            self.caps_total_val = caps_total
            caps_total_text     = str(caps_total)
        elif caps_disp:
            self.caps_total_val = caps_disp
            caps_total_text     = f"{caps_disp} ({Lang.tr('airing')})"
        elif is_airing:
            self.caps_total_val = 9999
            caps_total_text     = Lang.tr("airing")
        else:
            self.caps_total_val = 9999
            caps_total_text     = "?"

        ep_info = QLabel(Lang.tr("caps_total", n=caps_total_text))
        ep_info.setStyleSheet(f"background: {BORDER}; border-radius: 7px; color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 10px;")
        layout.addWidget(ep_info)

        layout.addWidget(self._section_label(Lang.tr("episodes_label")))
        caps_opts = ["0", "1"] if self.caps_total_val == 1 else [str(i) for i in range(0, self.caps_total_val + 1)]
        self.caps_entry = DropdownEntry(
            caps_opts,
            initial="0", readonly=False
        )
        layout.addWidget(self.caps_entry)

        layout.addWidget(self._section_label(Lang.tr("state_label")))
        sl = Lang.status_labels()
        self.estado_entry = DropdownEntry(
            [sl["watching"], sl["completed"], sl["planned"], sl["on_hold"], sl["dropped"]],
            initial=sl["planned"]
        )
        layout.addWidget(self.estado_entry)

        layout.addWidget(self._section_label(Lang.tr("score_label")))
        self.score_entry = DropdownEntry(
            [str(i) for i in range(1, 11)],
            initial="1"
        )
        layout.addWidget(self.score_entry)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setStyleSheet("color: #dc2626; font-size: 12px;")
        layout.addWidget(self.msg_lbl)

        save_btn = label_btn(Lang.tr("save"), BLUE)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"background: {BORDER}; border-radius: 7px; color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 10px;")
        lbl.setFixedHeight(28)
        return lbl

    def _save(self):
        try:
            caps = int(self.caps_entry.get())
            score = int(self.score_entry.get())
        except ValueError:
            self.msg_lbl.setText(Lang.tr("num_error"))
            return

        anime     = self.anime
        nombre    = anime.get("title", {}).get("romaji", Lang.tr("no_name"))
        caps_tot  = anime.get("episodes")
        if caps_tot is None:
            na     = anime.get("nextAiringEpisode")
            nep    = na.get("episode") if isinstance(na, dict) else None
            caps_totales = (nep - 1) if nep else None
        else:
            caps_totales = caps_tot

        saved = obtener_animes_usuario()
        if any(a["nombre"] == nombre for a in saved):
            self.msg_lbl.setText(Lang.tr("duplicate_error"))
            return

        if caps < 0:
            self.msg_lbl.setText(Lang.tr("caps_negative_error"))
            return

        if caps_totales and caps > caps_totales:
            self.msg_lbl.setText(Lang.tr("caps_exceed_error"))
            return

        if not (1 <= score <= 10):
            self.msg_lbl.setText(Lang.tr("score_range_error"))
            return

        estado = self.estado_entry.get()
        sl = Lang.status_labels()
        if estado == sl["completed"] and caps_totales:
            caps = caps_totales

        estado = Lang.reverse_status(estado)

        agregar_anime(
            nombre, caps, caps_totales, estado, score,
            anime.get("id"),
            anime.get("coverImage", {}).get("medium"),
            anime.get("status")
        )
        self.msg_lbl.setStyleSheet("color: #22c55e; font-size: 12px;")
        self.msg_lbl.setText("¡Anime guardado!")
        self.saved.emit(nombre)


# ── Vista: Animes guardados ───────────────────────────────────────────────────
class SavedAnimeCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, anime, cache, loader_refs, selected=False):
        super().__init__()
        self.anime = anime
        self.setFixedSize(350, 176)
        self.setObjectName("SavedAnimeCard")
        color = GREEN if selected else BORDER
        hover = "" if selected else " QFrame#SavedAnimeCard:hover { border-color: #60a5fa; }"
        self.setStyleSheet(f"QFrame#SavedAnimeCard {{ background: {SURFACE}; border-radius: 8px; border: 2px solid {color}; }}" + hover)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        img = ImageLabel(76, 108)
        img.load(anime.get("imagen"), cache, loader_refs)
        layout.addWidget(img, alignment=Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(4)

        name = anime["nombre"]
        if len(name) > 50:
            name = name[:47] + "..."
        name_lbl = QLabel(name)
        name_lbl.setWordWrap(True)
        name_lbl.setFixedHeight(48)
        name_lbl.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {TEXT}; background: transparent;")
        info.addWidget(name_lbl)

        caps_tot = anime["caps_totales"] if anime["caps_totales"] is not None else "?"
        caps_lbl = QLabel(Lang.tr("caps_fmt", v=anime['caps_vistos'], t=caps_tot))
        caps_lbl.setStyleSheet(f"font-size: 14px; color: {MUTED}; background: transparent;")
        info.addWidget(caps_lbl)

        info.addStretch()

        footer = QHBoxLayout()
        estado_color = STATUS_COLORS.get(anime["estado"], BORDER)
        estado_lbl = QLabel(Lang.translate_status(anime["estado"]))
        estado_lbl.setFixedSize(118, 28)
        estado_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        estado_lbl.setStyleSheet(f"background: {estado_color}; border-radius: 8px; color: white; font-size: 13px; font-weight: bold;")
        footer.addWidget(estado_lbl)

        score_lbl = QLabel(Lang.tr("score", s=anime['score']))
        score_lbl.setStyleSheet(f"font-size: 13px; color: #fbbf24; font-weight: bold; background: transparent;")
        footer.addStretch()
        footer.addWidget(score_lbl)
        info.addLayout(footer)

        layout.addLayout(info)

    def mousePressEvent(self, event):
        self.clicked.emit(self.anime)


class SavedAnimePanel(QFrame):
    closed  = pyqtSignal()
    saved   = pyqtSignal()
    deleted = pyqtSignal()

    def __init__(self, anime, cache, loader_refs):
        super().__init__()
        self.anime = anime
        self.setFixedWidth(430)
        self.setStyleSheet(f"QFrame {{ background: {SURFACE}; border-radius: 8px; border: 2px solid {BORDER}; }}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(10)

        close_btn = label_btn(Lang.tr("close"), "#475569", w=92, h=34)
        close_btn.clicked.connect(self.closed.emit)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        img = ImageLabel(150, 212)
        img.load(anime.get("imagen"), cache, loader_refs)
        layout.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel(anime["nombre"])
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 21px; font-weight: bold; color: {TEXT};")
        layout.addWidget(title)

        api_labels = Lang.api_status_labels()
        status_text, status_color = api_labels.get(anime.get("estado_api", ""), (Lang.tr("unknown_status"), "#64748b"))
        status_lbl = QLabel(status_text)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setFixedHeight(26)
        status_lbl.setStyleSheet(f"background: {status_color}; border-radius: 7px; color: white; font-size: 12px; font-weight: bold;")
        layout.addWidget(status_lbl)

        caps_tot   = anime["caps_totales"]
        est_api    = anime.get("estado_api", "")

        if caps_tot is None and est_api == "RELEASING":
            api_id = anime.get("api_id")
            if api_id:
                try:
                    r = requests.post("https://graphql.anilist.co", json={
                        "query": "query($id:Int){Media(id:$id,type:ANIME){episodes nextAiringEpisode{episode}}}",
                        "variables": {"id": api_id}
                    }, timeout=10)
                    d = r.json()
                    m = d.get("data", {}).get("Media", {})
                    if m.get("episodes"):
                        caps_tot = m["episodes"]
                        anime["caps_totales"] = caps_tot
                    else:
                        na = m.get("nextAiringEpisode")
                        if isinstance(na, dict) and na.get("episode"):
                            caps_tot = na["episode"] - 1
                            anime["caps_totales"] = caps_tot
                except Exception:
                    pass

        caps_max     = caps_tot if caps_tot is not None else 9999
        caps_tot_txt = str(caps_tot) if caps_tot is not None else (
            Lang.tr("airing") if est_api == "RELEASING" else "?")
        self.caps_max = caps_max

        prog_lbl = QLabel(f"{anime['caps_vistos']}/{caps_tot_txt}")
        prog_lbl.setStyleSheet(f"background: {BORDER}; border-radius: 7px; color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 10px;")
        prog_lbl.setFixedHeight(28)
        layout.addWidget(prog_lbl)

        layout.addWidget(self._section(Lang.tr("episodes_label")))
        caps_opts = ["0", "1"] if caps_max == 1 else [str(i) for i in range(0, caps_max + 1)]
        self.caps_entry = DropdownEntry(
            caps_opts,
            initial=str(anime["caps_vistos"]), readonly=False
        )
        layout.addWidget(self.caps_entry)

        sl = Lang.status_labels()
        db_estado = anime.get("estado", "Planeado")
        layout.addWidget(self._section(Lang.tr("state_label")))
        self.estado_entry = DropdownEntry(
            [sl["watching"], sl["completed"], sl["planned"], sl["on_hold"], sl["dropped"]],
            initial=Lang.translate_status(db_estado)
        )
        layout.addWidget(self.estado_entry)

        layout.addWidget(self._section(Lang.tr("score_label")))
        score_val = anime["score"] if isinstance(anime["score"], int) and 1 <= anime["score"] <= 10 else 1
        self.score_entry = DropdownEntry(
            [str(i) for i in range(1, 11)],
            initial=str(score_val)
        )
        layout.addWidget(self.score_entry)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setStyleSheet("color: #dc2626; font-size: 12px;")
        layout.addWidget(self.msg_lbl)

        btn_row = QHBoxLayout()
        save_btn = label_btn(Lang.tr("save_changes"), BLUE)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        del_btn = label_btn(Lang.tr("delete"), RED)
        del_btn.setFixedWidth(110)
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"background: {BORDER}; border-radius: 7px; color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 10px;")
        lbl.setFixedHeight(28)
        return lbl

    def _save(self):
        try:
            caps  = int(self.caps_entry.get())
            score = int(self.score_entry.get())
        except ValueError:
            self.msg_lbl.setText(Lang.tr("num_error"))
            return

        if not (1 <= score <= 10):
            self.msg_lbl.setText(Lang.tr("score_range_error"))
            return

        caps_tot = self.anime["caps_totales"]
        if caps_tot and caps > caps_tot:
            self.msg_lbl.setText(Lang.tr("caps_exceed_error"))
            return

        estado = Lang.reverse_status(self.estado_entry.get())

        if caps != self.anime["caps_vistos"]:
            actualizar_caps_anime(self.anime["id"], caps)
        else:
            sl = Lang.status_labels()
            if caps_tot and caps == caps_tot and estado != "Completo":
                self.msg_lbl.setText(Lang.tr("state_change_error"))
                return
            actualizar_estado_anime(self.anime["id"], estado)

        actualizar_score_anime(self.anime["id"], score)
        self.saved.emit()

    def _delete(self):
        eliminar_anime_usuario(self.anime["id"])
        self.deleted.emit()


class SavedAnimeView(QWidget):
    def __init__(self, cache, loader_refs, on_back):
        super().__init__()
        self.cache       = cache
        self.loader_refs = loader_refs
        self.all_items   = []
        self.filtered    = []
        self.page        = 0
        self.page_size   = 9
        self.columns     = 3
        self.panel       = None
        self.selected_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(68, 12, 68, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(74)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)

        tc = QVBoxLayout()
        t = QLabel(Lang.tr("saved_view_title"))
        t.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT};")
        s = QLabel(Lang.tr("saved_view_sub"))
        s.setStyleSheet(f"font-size: 11px; color: {MUTED};")
        tc.addWidget(t)
        tc.addWidget(s)
        hl.addLayout(tc)
        hl.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText(Lang.tr("search_saved"))
        self.search.setFixedSize(300, 42)
        self.search.setStyleSheet(f"QLineEdit {{ background: transparent; border: 2px solid {BORDER}; border-radius: 8px; color: {TEXT}; font-size: 14px; padding: 0 12px; }}")
        self.search.textChanged.connect(self._filter)
        hl.addWidget(self.search)

        sl = Lang.status_labels()
        self.estado_cb = QComboBox()
        self.estado_cb.addItems([Lang.tr("all"), sl["watching"], sl["completed"], sl["planned"], sl["on_hold"], sl["dropped"]])
        self.estado_cb.setFixedSize(164, 42)
        self.estado_cb.setStyleSheet(f"QComboBox {{ background: {SURFACE}; border: 2px solid {BORDER}; border-radius: 8px; color: {TEXT}; font-size: 14px; padding: 0 12px; }} QComboBox::drop-down {{ border: none; }} QComboBox QAbstractItemView {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; selection-background-color: {BORDER}; }}")
        self.estado_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self.estado_cb)
        layout.addWidget(header)
        layout.addSpacing(18)

        # Contenido: grid + panel
        self.content = QHBoxLayout()
        self.content.setSpacing(18)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet(f"background: {BG};")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll.setWidget(self.grid_widget)
        self.content.addWidget(self.scroll)
        layout.addLayout(self.content)

        # Bottom bar
        bottom = QWidget()
        bottom.setFixedHeight(60)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)

        back = label_btn(Lang.tr("back"), "#475569", w=120)
        back.clicked.connect(on_back)
        bl.addWidget(back)
        bl.addStretch()

        self.page_lbl = QLabel("")
        self.page_lbl.setStyleSheet(f"font-size: 15px; color: {TEXT};")
        bl.addWidget(self.page_lbl)
        bl.addSpacing(40)

        self.prev_btn = QPushButton(Lang.tr("prev"))
        self.prev_btn.setFixedSize(110, 38)
        self.prev_btn.clicked.connect(lambda: self._change_page(-1))
        bl.addWidget(self.prev_btn)

        self.next_btn = QPushButton(Lang.tr("next"))
        self.next_btn.setFixedSize(110, 38)
        self.next_btn.clicked.connect(lambda: self._change_page(1))
        bl.addWidget(self.next_btn)

        layout.addWidget(bottom)
        self.reload()

    def reload(self):
        self.all_items = obtener_animes_usuario()
        self._filter()

    def _filter(self):
        query  = self.search.text().strip().lower()
        estado = self.estado_cb.currentText()
        db_estado = Lang.reverse_status(estado) if estado != Lang.tr("all") else ""
        self.filtered = [
            a for a in self.all_items
            if (not query or query in a["nombre"].lower())
            and (not db_estado or a["estado"] == db_estado)
        ]
        self.page = 0
        self._render_page()

    def _change_page(self, d):
        total = max(1, -(-len(self.filtered) // self.page_size))
        self.page = max(0, min(self.page + d, total - 1))
        self._render_page()

    def _render_page(self):
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        start = self.page * self.page_size
        items = self.filtered[start:start + self.page_size]

        if not items:
            lbl = QLabel(Lang.tr("no_saved"))
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 16px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(lbl, 0, 0, 1, self.columns)
        else:
            for i, anime in enumerate(items):
                card = SavedAnimeCard(anime, self.cache, self.loader_refs,
                                      selected=(anime["id"] == self.selected_id))
                card.clicked.connect(self._open_panel)
                self.grid_layout.addWidget(card, i // self.columns, i % self.columns)

        total   = max(1, -(-len(self.filtered) // self.page_size))
        start_n = self.page * self.page_size + 1
        end_n   = min((self.page + 1) * self.page_size, len(self.filtered))
        self.page_lbl.setText(Lang.tr("page_info", page=self.page + 1, total=total, start=start_n, end=end_n, count=len(self.filtered)) if self.filtered else Lang.tr("no_results_short"))

        on_c  = TEXT
        off_c = MUTED
        self.prev_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {on_c if self.page > 0 else off_c}; border: none; font-size: 14px; }}")
        self.next_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {on_c if self.page < total - 1 else off_c}; border: none; font-size: 14px; }}")

    def _open_panel(self, anime):
        if self.panel:
            self.panel.deleteLater()
            self.panel = None

        self.selected_id = anime["id"]
        av = self.width() - 136 - 18 - 430
        self.columns     = max(1, av // 370)
        self.page_size   = 6
        self.panel = SavedAnimePanel(anime, self.cache, self.loader_refs)
        self.panel.closed.connect(self._close_panel)
        self.panel.saved.connect(self._on_saved)
        self.panel.deleted.connect(self._on_saved)
        self.content.addWidget(self.panel)
        self._render_page()

    def _close_panel(self):
        if self.panel:
            self.panel.deleteLater()
            self.panel = None
        self.selected_id = None
        av = self.width() - 136
        self.columns = max(1, av // 370)
        self.page_size   = 9
        self._render_page()

    def _on_saved(self):
        self._close_panel()
        self.reload()

    def reflow(self):
        cols = max(1, self.scroll.viewport().width() // 370)
        if cols != self.columns:
            self.columns = cols
            self._render_page()


# ── App principal ─────────────────────────────────────────────────────────────
class AnimeTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(Lang.tr("app_title"))
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(STYLE)
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, "icon.ico")))

        from database.setup import crear_tabla, crear_tablas_tracker
        crear_tabla()
        crear_tablas_tracker()

        self.image_cache    = {}
        self.loader_refs    = []
        self.preloaded      = []
        self.bg_preloader   = None
        self.preloader      = None
        self.data_ready     = False
        self._pending_login = False

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Start data fetch in background immediately
        self.data_worker = WorkerThread(obtener_animes_populares, ANIMES_POPULARES_TOTAL)
        self.data_worker.finished.connect(self._on_data_loaded)
        self.data_worker.start()

        # Check for saved session
        saved = session.load_remember_session()
        if saved and session.user_exists_in_db(saved["user_id"]):
            session.current_user_id = saved["user_id"]
            session.current_username = saved["username"]
            self._on_login_success()
        else:
            # Show login view
            self.login_view = LoginView(on_login_success=self._on_login_success)
            self.stack.addWidget(self.login_view)

    def _on_data_loaded(self, animes):
        self.preloaded = animes
        self.preloader = PreloadWorker(animes, self.image_cache, 0, 50, delay=0)
        self.preloader.finished.connect(self._on_preload_finished)
        # If loading view is already showing, connect progress
        if hasattr(self, 'loading_view') and self.loading_view is not None:
            self.preloader.progress.connect(self.loading_view.set_progress)
            self.loading_view.set_status(Lang.tr("preload_status"))
        self.preloader.start()

    def _on_preload_finished(self):
        self.data_ready = True
        # Start background preload for remaining images
        remaining = len(self.preloaded) - 50
        if remaining > 0:
            self.bg_preloader = PreloadWorker(
                self.preloaded, self.image_cache,
                50, remaining, delay=0.3
            )
            self.bg_preloader.finished.connect(self._on_bg_preload_finished)
            self.bg_preloader.start()
        # If user already logged in and waiting, go to main
        if self._pending_login:
            self._go_to_main()

    def _on_bg_preload_finished(self):
        self.bg_preloader = None

    def _on_login_success(self):
        if self.data_ready:
            self._go_to_main()
        else:
            self.loading_view = LoadingView()
            self.stack.addWidget(self.loading_view)
            self.stack.setCurrentWidget(self.loading_view)
            self._pending_login = True
            # If data is already loaded but preloader running, connect progress
            if self.preloader is not None:
                self.preloader.progress.connect(self.loading_view.set_progress)
                self.loading_view.set_status(Lang.tr("preload_status"))

    def _go_to_main(self):
        self.main_view = MainView(
            on_add      = self.show_add_view,
            on_saved    = self.show_saved_view,
            on_exit     = self.close,
            on_language = self._on_language,
            on_theme    = self._on_theme_toggle,
            on_logout   = self._on_logout,
        )
        self.stack.addWidget(self.main_view)
        self.stack.setCurrentWidget(self.main_view)
        # Clean up login & loading views
        if hasattr(self, 'login_view') and self.login_view is not None:
            self.login_view.deleteLater()
            self.login_view = None
        if hasattr(self, 'loading_view') and self.loading_view is not None:
            self.loading_view.deleteLater()
            self.loading_view = None
        self._pending_login = False

    def _on_logout(self):
        session.current_user_id = None
        session.current_username = None
        session.delete_remember_session()
        self._pending_login = False
        if hasattr(self, 'main_view') and self.main_view is not None:
            self.main_view.deleteLater()
            self.main_view = None
        if hasattr(self, 'loading_view') and self.loading_view is not None:
            self.loading_view.deleteLater()
            self.loading_view = None
        self.login_view = LoginView(on_login_success=self._on_login_success)
        self.stack.addWidget(self.login_view)
        self.stack.setCurrentWidget(self.login_view)

    def _on_language(self, code):
        Lang.set(code)
        self.main_view.deleteLater()
        self.main_view = MainView(
            on_add      = self.show_add_view,
            on_saved    = self.show_saved_view,
            on_exit     = self.close,
            on_language = self._on_language,
            on_theme    = self._on_theme_toggle,
            on_logout   = self._on_logout,
        )
        self.stack.addWidget(self.main_view)
        self.stack.setCurrentWidget(self.main_view)
        self.setWindowTitle(Lang.tr("app_title"))

    def _on_theme_toggle(self):
        toggle_theme()
        self.main_view.deleteLater()
        self.main_view = MainView(
            on_add      = self.show_add_view,
            on_saved    = self.show_saved_view,
            on_exit     = self.close,
            on_language = self._on_language,
            on_theme    = self._on_theme_toggle,
            on_logout   = self._on_logout,
        )
        self.stack.addWidget(self.main_view)
        self.stack.setCurrentWidget(self.main_view)
        self.setStyleSheet(STYLE)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            current = self.stack.currentWidget()
            if hasattr(current, "reflow"):
                current.reflow()
        else:
            super().keyPressEvent(event)

    def show_add_view(self):
        view = AddAnimeView(
            animes       = self.preloaded,
            cache        = self.image_cache,
            loader_refs  = self.loader_refs,
            on_back      = lambda: self.stack.setCurrentWidget(self.main_view),
        )
        self.add_view = view
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)

    def show_saved_view(self):
        view = SavedAnimeView(
            cache       = self.image_cache,
            loader_refs = self.loader_refs,
            on_back     = lambda: self.stack.setCurrentWidget(self.main_view)
        )
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)