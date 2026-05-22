from io import BytesIO
from pathlib import Path
import math
import threading
import tkinter as tk

import customtkinter as ctk
import requests
from PIL import Image

from database.queries import (
    agregar_anime,
    actualizar_caps_anime,
    actualizar_estado_anime,
    actualizar_score_anime,
    obtener_animes_usuario,
)
from services.anime_services import obtener_animes_populares


class AnimeTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ANIME TRACKER")
        self.geometry("1280x720")
        self.minsize(1280, 720)
        self.fullscreen = False
        self.windowed_geometry = "1280x720"
        self.background_color = "#edf4fb"
        self.configure(fg_color=self.background_color)
        self.font_family = "Montserrat"
        self.icon_path = Path(__file__).resolve().parent.parent / "icon.ico"
        self.image_cache = {}
        self.current_view = "loading"
        self.preloaded_anime_items = []
        self.all_anime_items = []
        self.anime_items = []
        self.search_after_id = None
        self.anime_page = 0
        self.anime_page_size = 50
        self.anime_columns = 6
        self.current_anime_cards = []
        self.anime_card_slots = []
        self.add_editor_panel = None
        self.add_editor_open = False
        self.saved_all_items = []
        self.saved_items = []
        self.saved_page = 0
        self.saved_page_size = 9
        self.saved_columns = 3
        self.saved_search_after_id = None
        self.saved_editor_panel = None
        self.saved_editor_open = False

        self._set_window_icon(self)

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.bind("<F11>", self._toggle_fullscreen)


        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.bind("<Unmap>", lambda e: self._close_all_dropdowns())
        self.bind("<Map>", lambda e: self._close_all_dropdowns())
        self._reposition_job = None
        self.bind("<Configure>", lambda e: self._schedule_reposition_on_resize())

        self.content_frame = tk.Frame(self, bg=self.background_color, bd=0, highlightthickness=0)
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_background = self._create_background(self.content_frame)

        self.bottom_bar = tk.Frame(self, bg=self.background_color, bd=0, highlightthickness=0, height=60)
        self.bottom_bar.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        self.bottom_bar.grid_propagate(False)
        self.bottom_bar.grid_columnconfigure(0, weight=1)
        self.bottom_bar.grid_columnconfigure(1, weight=0)
        self.bottom_bar.grid_columnconfigure(2, weight=1)
        self.bottom_background = self._create_background(self.bottom_bar)
        self.show_loading_view()
        threading.Thread(target=self._preload_anime_items, daemon=True).start()

    def _widget_fg_color(self, widget):
        try:
            color = widget.cget("fg_color")
        except (ValueError, tk.TclError, AttributeError):
            return None

        if isinstance(color, (tuple, list)):
            return color[0]

        return color

    def _transparent_widget_backgrounds(self, widget, parent_color=None):
        own_color = self._widget_fg_color(widget)
        is_transparent_surface = own_color in (None, "transparent")
        surface_color = parent_color if is_transparent_surface else own_color

        try:
            widget.configure(bg_color="transparent" if is_transparent_surface else (parent_color or self.background_color))
        except (ValueError, tk.TclError, AttributeError):
            pass

        for child in widget.winfo_children():
            self._transparent_widget_backgrounds(child, surface_color)

    def _set_window_icon(self, window):
        if self.icon_path.exists():
            window.iconbitmap(str(self.icon_path))

    def _toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_geometry = self.geometry()
            self.attributes('-fullscreen', True)
        else:
            self.attributes('-fullscreen', False)
            self.geometry(self.windowed_geometry)
        
        # Actualizar interfaz después de cambiar fullscreen
        self._refresh_after_fullscreen_job = self.after(50, self._refresh_after_fullscreen)
    
    def _refresh_after_fullscreen(self):
        """Refresca la interfaz después de cambiar a/desde fullscreen"""
        if hasattr(self, 'content_background') and self.content_background.winfo_exists():
            self._draw_background(self.content_background)
        if hasattr(self, 'bottom_background') and self.bottom_background.winfo_exists():
            self._draw_background(self.bottom_background)
        self.update_idletasks()
        self.update()
        
        # Forzar redibujado de todas las vistas
        if hasattr(self, 'current_view'):
            if self.current_view == "saved" and hasattr(self, 'saved_grid') and self.saved_grid.winfo_exists():
                self._style_scroll_background(self.saved_grid)
            if self.current_view == "add" and hasattr(self, 'anime_scroll') and self.anime_scroll.winfo_exists():
                self._style_scroll_background(self.anime_scroll)

    def destroy(self):
        """Override destroy to cleanup pending after callbacks before destroying the window"""
        self._cancel_all_after_callbacks()
        super().destroy()
        
    def _cancel_all_after_callbacks(self):
        """Cancel all pending after callbacks to prevent Tcl errors on exit"""
        # Cancel search after callbacks
        if hasattr(self, 'search_after_id') and self.search_after_id is not None:
            try:
                self.after_cancel(self.search_after_id)
            except (ValueError, tk.TclError):
                pass
            self.search_after_id = None
            
        # Cancel saved search after callbacks
        if hasattr(self, 'saved_search_after_id') and self.saved_search_after_id is not None:
            try:
                self.after_cancel(self.saved_search_after_id)
            except (ValueError, tk.TclError):
                pass
            self.saved_search_after_id = None
            
        # Cancel estado draw job
        if hasattr(self, '_estado_draw_job') and self._estado_draw_job is not None:
            try:
                self.after_cancel(self._estado_draw_job)
            except (ValueError, tk.TclError):
                pass
            self._estado_draw_job = None
            
        # Cancel score draw job
        if hasattr(self, '_score_draw_job') and self._score_draw_job is not None:
            try:
                self.after_cancel(self._score_draw_job)
            except (ValueError, tk.TclError):
                pass
            self._score_draw_job = None
            
        # Cancel refresh after fullscreen job
        if hasattr(self, '_refresh_after_fullscreen_job') and self._refresh_after_fullscreen_job is not None:
            try:
                self.after_cancel(self._refresh_after_fullscreen_job)
            except (ValueError, tk.TclError):
                pass
            self._refresh_after_fullscreen_job = None

        # Cancel scroll polling jobs
        for canvas, info in list(getattr(self, '_scroll_tracking', {}).items()):
            job = info.get("job")
            if job is not None:
                try:
                    self.after_cancel(job)
                except (ValueError, tk.TclError):
                    pass
        self._scroll_tracking.clear()
            
        # Cancel any other potential after callbacks by tracking them
        # This is a safety net - cancel all jobs in the after queue
        # Note: This is more aggressive but prevents the Tcl error
        try:
            # Get all pending after callbacks and cancel them
            # We can't directly get the list, but we can try to cancel common ones
            # or use a try/except loop for a range of IDs (not ideal but safe)
            pass
        except:
            pass

    def _clear_frame(self, frame):
        for widget in frame.winfo_children():
            if widget in (getattr(self, "content_background", None), getattr(self, "bottom_background", None)):
                continue
            widget.destroy()
    def _clear_view(self):
        if self.search_after_id is not None:
            self.after_cancel(self.search_after_id)
            self.search_after_id = None

        if self.saved_search_after_id is not None:
            self.after_cancel(self.saved_search_after_id)
            self.saved_search_after_id = None
        
        # Cancel drawing jobs to prevent errors on exit
        estado_draw_job = getattr(self, '_estado_draw_job', None)
        if estado_draw_job is not None:
            self.after_cancel(estado_draw_job)
            self._estado_draw_job = None
            
        score_draw_job = getattr(self, '_score_draw_job', None)
        if score_draw_job is not None:
            self.after_cancel(score_draw_job)
            self._score_draw_job = None
            
        # Cancel any refresh after fullscreen jobs
        refresh_job = getattr(self, '_refresh_after_fullscreen_job', None)
        if refresh_job is not None:
            self.after_cancel(refresh_job)
            self._refresh_after_fullscreen_job = None

        self.add_editor_panel = None
        self.add_editor_open = False
        self.saved_editor_panel = None
        self.saved_editor_open = False

        self._clear_frame(self.content_frame)
        self._clear_frame(self.bottom_bar)
        self.current_anime_cards = []
        self.anime_card_slots = []

    def _attach_view_background(self, frame):
        frame.configure(fg_color=self.background_color)
        return None

    def _attach_header_background(self, frame, title, subtitle):
        background = tk.Canvas(frame, highlightthickness=0, bd=0, bg=self.background_color)
        background.place(x=0, y=0, relwidth=1, relheight=1)

        def draw(event=None, current_canvas=background):
            self._draw_background(current_canvas)
            current_canvas.create_text(
                0,
                18,
                text=title,
                anchor="w",
                fill="#172033",
                font=(self.font_family, 24, "bold")
            )
            current_canvas.create_text(
                0,
                54,
                text=subtitle,
                anchor="w",
                fill="#667085",
                font=(self.font_family, 11, "bold")
            )

        background.bind("<Configure>", draw)
        self.after_idle(draw)
        return background

    def _create_background(self, parent):
        background = tk.Canvas(
            parent,
            highlightthickness=0,
            bd=0,
            bg="#eef3f8"
        )
        background.place(x=0, y=0, relwidth=1, relheight=1)
        background.bind("<Configure>", lambda event: self._draw_background(background))
        return background

    def _draw_background(self, background):
        local_width = background.winfo_width()
        local_height = background.winfo_height()
        width = max(self.winfo_width(), local_width)
        height = max(self.winfo_height(), local_height)

        try:
            offset_x = background.winfo_rootx() - self.winfo_rootx()
            offset_y = background.winfo_rooty() - self.winfo_rooty()
        except tk.TclError:
            offset_x = 0
            offset_y = 0

        background.delete("all")

        if self.current_view == "loading":
            background.create_rectangle(0, 0, width, height, fill="#05070b", outline="")

            if background is getattr(self, "content_background", None):
                background.create_text(
                    width / 2,
                    height / 2 - 80,
                    text="Anime Tracker",
                    fill="#ffffff",
                    font=(self.font_family, 38, "bold")
                )
                background.create_text(
                    width / 2,
                    height / 2 - 26,
                    text="Cargando catalogo de animes...",
                    fill="#dbeafe",
                    font=(self.font_family, 13, "bold")
                )

            background.move("all", -offset_x, -offset_y)
            return

        background.create_rectangle(0, 0, width, height, fill="#edf4fb", outline="")

        washes = [
            ("#dbeafe", (-240, -80, 470, 370)),
            ("#fce7f3", (width - 420, -170, width + 250, 330)),
            ("#ccfbf1", (width - 360, height - 300, width + 210, height + 180)),
            ("#fef3c7", (-230, height - 260, 360, height + 150)),
            ("#ede9fe", (width * 0.34, -150, width * 0.75, 180)),
            ("#e0f2fe", (width * 0.25, height - 205, width * 0.62, height + 120)),
        ]

        for color, bounds in washes:
            background.create_oval(*bounds, fill=color, outline="")

        for offset, color in [(0, "#dbe7f3"), (80, "#e7eef7")]:
            for x in range(-80 + offset, width + 180, 170):
                background.create_line(x, 0, x - 110, height, fill=color, width=1)

        for y in range(74, height + 120, 132):
            background.create_line(0, y, width, y - 62, fill="#dfeaf5", width=1)

        ribbons = [
            ("#60a5fa", 5, [(-120, 122), (135, 54), (380, 124), (635, 70), (width + 120, 150)]),
            ("#a78bfa", 4, [(-80, height - 168), (200, height - 238), (470, height - 180), (780, height - 270), (width + 85, height - 215)]),
            ("#2dd4bf", 5, [(width - 440, -70), (width - 300, 115), (width - 110, 185), (width + 80, 340)]),
            ("#fb7185", 3, [(70, height * 0.52), (210, height * 0.46), (360, height * 0.54), (540, height * 0.48)]),
            ("#f59e0b", 3, [(width * 0.20, 42), (width * 0.31, 92), (width * 0.43, 48), (width * 0.58, 104)]),
            ("#22c55e", 2, [(width * 0.60, height - 78), (width * 0.72, height - 135), (width * 0.84, height - 92), (width * 0.96, height - 150)]),
        ]

        for color, line_width, points in ribbons:
            coords = [coordinate for point in points for coordinate in point]
            background.create_line(*coords, fill=color, width=line_width, smooth=True, capstyle=tk.ROUND)

        marks = [
            (width * 0.48, 76, "#38bdf8"),
            (width * 0.72, 316, "#f59e0b"),
            (width * 0.16, height * 0.56, "#10b981"),
            (width * 0.86, height * 0.62, "#6366f1"),
            (width - 128, 78, "#8b5cf6"),
            (138, 284, "#f43f5e"),
        ]

        for x, y, color in marks:
            background.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="")
            background.create_line(x - 12, y, x + 12, y, fill="#ffffff", width=2)
            background.create_line(x, y - 12, x, y + 12, fill="#ffffff", width=2)

        for x in range(38, width, 235):
            y = 36 + (x % 4) * 31
            background.create_arc(x, y, x + 58, y + 58, start=18, extent=252, outline="#c4b5fd", width=2, style=tk.ARC)

        title_lines = [
            (width * 0.39, height * 0.36, 74),
            (width * 0.46, height * 0.40, 112),
            (width * 0.53, height * 0.36, 74),
        ]

        for x, y, length in title_lines:
            background.create_line(x - length / 2, y, x + length / 2, y, fill="#d8e3ef", width=5, capstyle=tk.ROUND)

        if background is getattr(self, "content_background", None) and self.current_view == "main":
            background.create_text(
                width / 2,
                118,
                text="Anime Tracker",
                fill="#172033",
                font=(self.font_family, 38, "bold")
            )
            background.create_text(
                width / 2,
                180,
                text="Tu biblioteca de anime, organizada y lista para seguir mirando.",
                fill="#667085",
                font=(self.font_family, 13, "bold")
            )

        background.move("all", -offset_x, -offset_y)

    def _style_scroll_background(self, scroll_frame):
        try:
            canvas = scroll_frame._parent_canvas
            inner_frame = scroll_frame._scrollable_frame
        except AttributeError:
            return

        canvas.configure(bg="#ffffff", highlightthickness=0, bd=0)

    def _bind_dropdown_close(self, toplevel, callback):
        pass

    _scroll_tracking = {}

    def _schedule_reposition_on_resize(self):
        if self._reposition_job is not None:
            try:
                self.after_cancel(self._reposition_job)
            except (ValueError, tk.TclError):
                pass
        self._reposition_job = self.after(50, self._do_reposition_on_resize)

    def _do_reposition_on_resize(self):
        self._reposition_job = None
        self._reposition_open_dropdown()

    def _bind_scroll_reposition(self, scroll_frame):
        pass

    def _cancel_scroll_polling(self, canvas):
        pass

    def _poll_scroll_position(self, canvas):
        pass

    def _reposition_open_dropdown(self):
        """Reposiciona el dropdown activo para que quede pegado al entry,
        sin importar si el usuario scroleo el panel."""
        self.update_idletasks()
        dropdowns = [
            ("add_caps_dropdown", "add_caps_entry"),
            ("add_estado_dropdown", "add_estado_entry"),
            ("add_score_dropdown", "add_score_entry"),
            ("saved_caps_dropdown", "saved_caps_entry"),
            ("saved_estado_dropdown", "saved_estado_entry"),
            ("saved_score_dropdown", "saved_score_entry"),
        ]

        for attr_name, entry_name in dropdowns:
            dropdown = getattr(self, attr_name, None)
            entry = getattr(self, entry_name, None)

            if dropdown is None or entry is None:
                continue

            if not dropdown.winfo_exists() or not entry.winfo_exists():
                continue

            try:
                entry_x = entry.winfo_rootx()
                entry_y = entry.winfo_rooty() + entry.winfo_height()
                dropdown.geometry(f"+{entry_x}+{entry_y}")
            except tk.TclError:
                continue

    def _on_master_click_handler(self, close_fn):
        self._current_dropdown_close_fn = self._close_all_dropdowns
        self._current_dropdown_close_id = self.bind("<Button-1>", self._on_global_button, add="+")

    def _on_global_button(self, event):
        fn = getattr(self, "_current_dropdown_close_fn", None)
        cid = getattr(self, "_current_dropdown_close_id", None)
        if fn is not None and cid is not None:
            try:
                self.unbind("<Button-1>", cid)
            except tk.TclError:
                pass
            self._current_dropdown_close_fn = None
            self._current_dropdown_close_id = None
            fn()

    def _close_all_dropdowns(self):
        for name, close_fn in [
            ("saved_caps_dropdown", self._close_saved_caps_dropdown),
            ("saved_estado_dropdown", self._close_saved_estado_dropdown),
            ("saved_score_dropdown", self._close_saved_score_dropdown),
            ("add_caps_dropdown", self._close_add_caps_dropdown),
            ("add_estado_dropdown", self._close_add_estado_dropdown),
            ("add_score_dropdown", self._close_add_score_dropdown),
        ]:
            w = getattr(self, name, None)
            if w is not None:
                try:
                    if w.winfo_exists():
                        w.destroy()
                except tk.TclError:
                    pass
                setattr(self, name, None)
        self._current_dropdown_close_fn = None
        cid = getattr(self, "_current_dropdown_close_id", None)
        if cid is not None:
            try:
                self.unbind("<Button-1>", cid)
            except tk.TclError:
                pass
            self._current_dropdown_close_id = None


    def _draw_scroll_estado_style(self, canvas):
        if not canvas.winfo_exists():
            return
        self._do_draw_estado_style(canvas)

    def _do_draw_estado_style(self, canvas):
        if not canvas.winfo_exists():
            return
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        canvas.delete("estado_bg")
        canvas.configure(bg="#f1f5f9", highlightthickness=1, highlightbackground="#cbd5e1")

    def _draw_scroll_score_style(self, canvas):
        if not canvas.winfo_exists():
            return
        self._do_draw_score_style(canvas)

    def _do_draw_score_style(self, canvas):
        if not canvas.winfo_exists():
            return
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        canvas.delete("score_bg")
        canvas.configure(bg="#f1f5f9", highlightthickness=1, highlightbackground="#cbd5e1")

    def _draw_scroll_background(self, canvas):
        if not canvas.winfo_exists():
            return

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        canvas.delete("scroll_bg")

        canvas.create_rectangle(0, 0, width, height, fill=self.background_color, outline="", tags="scroll_bg")

        for x in range(24, max(width, 1), 145):
            canvas.create_line(x, 0, x - 78, height, fill="#dbe7f3", width=1, tags="scroll_bg")

        for y in range(58, max(height, 1), 124):
            canvas.create_line(0, y, width, y - 42, fill="#e5edf7", width=1, tags="scroll_bg")

        paths = [
            ("#93c5fd", 3, [(-40, 62), (width * 0.20, 26), (width * 0.42, 70), (width * 0.65, 36), (width + 40, 84)]),
            ("#c4b5fd", 3, [(-35, height - 78), (width * 0.22, height - 118), (width * 0.47, height - 88), (width * 0.76, height - 132), (width + 34, height - 96)]),
            ("#5eead4", 2, [(width - 225, 10), (width - 140, 96), (width - 42, 118), (width + 28, 205)]),
        ]

        for color, line_width, points in paths:
            coords = [coordinate for point in points for coordinate in point]
            canvas.create_line(*coords, fill=color, width=line_width, smooth=True, capstyle=tk.ROUND, tags="scroll_bg")

        for x, y, color in [
            (width * 0.36, 64, "#60a5fa"),
            (width * 0.68, 112, "#f59e0b"),
            (width * 0.18, height - 86, "#10b981"),
            (width * 0.86, height - 68, "#8b5cf6"),
        ]:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="", tags="scroll_bg")
            canvas.create_line(x - 10, y, x + 10, y, fill="#ffffff", width=2, tags="scroll_bg")
            canvas.create_line(x, y - 10, x, y + 10, fill="#ffffff", width=2, tags="scroll_bg")

        canvas.tag_lower("scroll_bg")

    def show_loading_view(self):
        self.current_view = "loading"
        self._clear_view()
        self.title("ANIME TRACKER")

        self._draw_background(self.content_background)

        loading_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        loading_frame.place(relx=0.5, rely=0.5, y=28, anchor="n")

        progress = ctk.CTkProgressBar(
            loading_frame,
            width=360,
            height=12,
            mode="indeterminate",
            progress_color="#2563eb"
        )
        progress.grid(row=2, column=0)
        progress.start()
        self._transparent_widget_backgrounds(self.content_frame)

    def _preload_anime_items(self):
        animes = obtener_animes_populares(1000)
        self.after(0, lambda: self._finish_preload(animes))

    def _finish_preload(self, animes):
        self.preloaded_anime_items = animes
        self.show_main_view()

    def show_main_view(self):
        self.current_view = "main"
        self._clear_view()
        self.title("ANIME TRACKER")
        self._draw_background(self.content_background)

        self._create_action_card(
            self.content_frame,
            x=289,
            y=230,
            title="Agregar anime",
            detail="Buscar y sumar series",
            color="#2563eb",
            hover="#1d4ed8",
            command=self.show_add_anime_view
        )
        self._create_action_card(
            self.content_frame,
            x=659,
            y=230,
            title="Ver animes guardados",
            detail="Revisar y editar progreso",
            color="#0f766e",
            hover="#115e59",
            command=self.show_saved_anime_view
        )

        exit_button = ctk.CTkButton(
            self.bottom_bar,
            text="Salir",
            width=150,
            height=46,
            fg_color="#334155",
            hover_color="#1e293b",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=16, weight="bold"),
            command=self.destroy
        )
        exit_button.grid(row=0, column=2, sticky="e", padx=32, pady=0)
        self._draw_background(self.bottom_background)
        self._transparent_widget_backgrounds(self.content_frame)
        self._transparent_widget_backgrounds(self.bottom_bar)

    def show_saved_anime_view(self):
        self.current_view = "saved"
        self._clear_view()
        self.title("ANIME TRACKER")
        self.saved_all_items = obtener_animes_usuario()
        self.saved_items = self.saved_all_items
        self.saved_page = 0

        self.saved_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.saved_frame.grid(row=0, column=0, sticky="nsew", padx=42, pady=(34, 0))
        self._attach_view_background(self.saved_frame)
        self.saved_frame.grid_columnconfigure(0, weight=1)
        self.saved_frame.grid_columnconfigure(1, weight=0)
        self.saved_frame.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self.saved_frame, fg_color="transparent", height=74)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header_frame.grid_columnconfigure(0, weight=1, minsize=540)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_propagate(False)
        self._attach_header_background(header_frame, "Animes guardados", "Revisá tu progreso, capítulos vistos y estado actual.")
        controls_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=1, sticky="e")

        self.saved_search_entry = ctk.CTkEntry(
            controls_frame,
            width=300,
            height=42,
            placeholder_text="Buscar guardado...",
            fg_color="#ffffff",
            border_color="#172033",
            text_color="#172033",
            placeholder_text_color="#94a3b8",
            font=ctk.CTkFont(family=self.font_family, size=14)
        )
        self.saved_search_entry.grid(row=0, column=0, padx=(0, 12))
        self.saved_search_entry.bind("<KeyRelease>", self._on_saved_filter_changed)

        self.saved_state_filter = ctk.CTkOptionMenu(
            controls_frame,
            width=160,
            height=42,
            values=["Todos", "En proceso", "Completo", "Planeado", "En espera", "Abandonado"],
            fg_color="#ffffff",
            button_color="#0f766e",
            button_hover_color="#115e59",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14),
            command=lambda _: self._apply_saved_filter()
        )
        self.saved_state_filter.grid(row=0, column=1)
        self.saved_state_filter.set("Todos")

        self.saved_grid = ctk.CTkScrollableFrame(
            self.saved_frame,
            fg_color="#edf4fb",
            width=1138,
            height=520,
            border_width=2,
            border_color="#172033",
            scrollbar_button_color="#bfdbfe",
            scrollbar_button_hover_color="#93c5fd"
        )
        self.saved_grid.grid(row=1, column=0, sticky="nsew")
        self._style_scroll_background(self.saved_grid)
        self._bind_scroll_reposition(self.saved_grid)

        for column in range(self.saved_columns):
            self.saved_grid.grid_columnconfigure(column, weight=1)

        self._create_saved_bottom_bar()
        self._render_saved_page()
        if hasattr(self, "bottom_background"):
            self._draw_background(self.bottom_background)
        self._transparent_widget_backgrounds(self.content_frame)
        self._transparent_widget_backgrounds(self.bottom_bar)

    def _create_saved_bottom_bar(self):
        back_button = ctk.CTkButton(
            self.bottom_bar,
            text="Volver",
            width=150,
            height=46,
            fg_color="#334155",
            hover_color="#1e293b",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=16, weight="bold"),
            command=self.show_main_view
        )
        back_button.grid(row=0, column=0, sticky="w", padx=32, pady=0)

        self.saved_page_info_label = ctk.CTkLabel(
            self.bottom_bar,
            text="",
            text_color="#172033",
            fg_color="transparent",
            bg_color="transparent",
            font=ctk.CTkFont(family=self.font_family, size=15, weight="bold")
        )
        self.saved_page_info_label.grid(row=0, column=1, pady=0)

        nav_frame = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        nav_frame.grid(row=0, column=2, sticky="e", padx=32, pady=0)

        self.saved_prev_page_button = ctk.CTkButton(
            nav_frame,
            text="Anterior",
            width=120,
            height=42,
            fg_color="#475569",
            hover_color="#334155",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._change_saved_page(-1)
        )
        self.saved_prev_page_button.grid(row=0, column=0, padx=(0, 10))
        self.saved_prev_page_button.configure(border_width=2, border_color="#172033")

        self.saved_next_page_button = ctk.CTkButton(
            nav_frame,
            text="Siguiente",
            width=120,
            height=42,
            fg_color="#0f766e",
            hover_color="#115e59",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._change_saved_page(1)
        )
        self.saved_next_page_button.grid(row=0, column=1)
        self.saved_next_page_button.configure(border_width=2, border_color="#172033")

    def _on_saved_filter_changed(self, event=None):
        if self.saved_search_after_id is not None:
            self.after_cancel(self.saved_search_after_id)

        self.saved_search_after_id = self.after(160, self._apply_saved_filter)

    def _apply_saved_filter(self):
        self.saved_search_after_id = None
        self._close_saved_editor()
        query = self.saved_search_entry.get().strip().lower()
        estado = self.saved_state_filter.get()

        self.saved_items = []

        for anime in self.saved_all_items:
            nombre = anime["nombre"].lower()
            coincide_nombre = query in nombre
            coincide_estado = estado == "Todos" or anime["estado"] == estado

            if coincide_nombre and coincide_estado:
                self.saved_items.append(anime)

        self.saved_page = 0
        self._render_saved_page()

    def _total_saved_pages(self):
        if not self.saved_items:
            return 1
        return math.ceil(len(self.saved_items) / self.saved_page_size)

    def _change_saved_page(self, direction):
        next_page = self.saved_page + direction

        if next_page < 0 or next_page >= self._total_saved_pages():
            return

        self.saved_page = next_page
        self._render_saved_page()

    def _render_saved_page(self):
        for widget in self.saved_grid.winfo_children():
            widget.destroy()

        start = self.saved_page * self.saved_page_size
        end = min(start + self.saved_page_size, len(self.saved_items))
        page_items = self.saved_items[start:end]

        try:
            self.saved_grid._parent_canvas.yview_moveto(0)
        except AttributeError:
            pass

        if not page_items:
            empty_label = ctk.CTkLabel(
                self.saved_grid,
                text="No hay animes guardados para mostrar.",
                text_color="#667085",
                font=ctk.CTkFont(family=self.font_family, size=16)
            )
            empty_label.grid(row=0, column=0, columnspan=self.saved_columns, pady=90)
            self._update_saved_page_controls()
            return

        for position, anime in enumerate(page_items):
            row = position // self.saved_columns
            column = position % self.saved_columns
            self._create_saved_anime_card(self.saved_grid, anime, row, column)

        self._update_saved_page_controls()
        self._transparent_widget_backgrounds(self.saved_grid)

    def _update_saved_page_controls(self):
        if not self.saved_items:
            self.saved_page_info_label.configure(text="Sin resultados")
            self.saved_prev_page_button.configure(state="disabled")
            self.saved_next_page_button.configure(state="disabled")
            return

        total_pages = self._total_saved_pages()
        start = self.saved_page * self.saved_page_size + 1
        end = min((self.saved_page + 1) * self.saved_page_size, len(self.saved_items))
        self.saved_page_info_label.configure(
            text=f"Pagina {self.saved_page + 1}/{total_pages} · {start}-{end} de {len(self.saved_items)}"
        )

        self.saved_prev_page_button.configure(state="normal" if self.saved_page > 0 else "disabled")
        self.saved_next_page_button.configure(
            state="normal" if self.saved_page < total_pages - 1 else "disabled"
        )

    def _create_saved_anime_card(self, parent, anime, row, column):
        card_width = 338 if self.saved_editor_open else 350
        text_width = 206 if self.saved_editor_open else 218

        card = ctk.CTkFrame(
            parent,
            width=card_width,
            height=176,
            fg_color="#ffffff",
            corner_radius=8,
            border_width=2,
            border_color="#172033"
        )
        card.grid(row=row, column=column, padx=12, pady=12, sticky="n")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)

        image_url = anime.get("imagen")
        image_label = ctk.CTkLabel(
            card,
            text="Cargando...",
            width=76,
            height=108,
            fg_color="#e5edf6",
            text_color="#667085",
            corner_radius=7,
            font=ctk.CTkFont(family=self.font_family, size=11)
        )
        image_label.grid(row=0, column=0, rowspan=3, padx=(16, 12), pady=16, sticky="n")
        image_label.expected_image_url = image_url

        if image_url:
            self._load_card_image(image_url, image_label, size=(76, 108))
        else:
            self._clear_card_image(image_label, "Sin imagen")

        title = self._shorten_saved_name(anime["nombre"])
        title_label = ctk.CTkLabel(
            card,
            text=title,
            text_color="#172033",
            width=text_width,
            height=48,
            wraplength=text_width,
            anchor="w",
            justify="left",
            font=ctk.CTkFont(family=self.font_family, size=17, weight="bold")
        )
        title_label.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(16, 6))

        caps_totales = anime["caps_totales"] if anime["caps_totales"] is not None else "?"
        caps_text = f"Capitulos: {anime['caps_vistos']}/{caps_totales}"
        caps_label = ctk.CTkLabel(
            card,
            text=caps_text,
            text_color="#475569",
            anchor="w",
            font=ctk.CTkFont(family=self.font_family, size=14)
        )
        caps_label.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 8))

        footer_frame = ctk.CTkFrame(card, fg_color="transparent")
        footer_frame.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=(0, 14))
        footer_frame.grid_columnconfigure(0, weight=1)

        estado_label = ctk.CTkLabel(
            footer_frame,
            text=anime["estado"],
            text_color="#ffffff",
            fg_color=self._state_color(anime["estado"]),
            corner_radius=8,
            width=118,
            height=28,
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        estado_label.grid(row=0, column=0, sticky="w")

        score_label = ctk.CTkLabel(
            footer_frame,
            text=f"Score: {anime['score']}",
            text_color="#667085",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        score_label.grid(row=0, column=1, sticky="e")

        self._bind_saved_card_click(card, anime)

    def _bind_saved_card_click(self, widget, anime):
        widget.bind("<Button-1>", lambda event: self._open_saved_editor(anime))

        try:
            widget.configure(cursor="hand2")
        except (ValueError, tk.TclError):
            pass

        for child in widget.winfo_children():
            self._bind_saved_card_click(child, anime)

    def _open_saved_editor(self, anime):
        self._close_saved_editor(reset_grid=False)

        # Set layout and create panel immediately, then render in one go
        self._set_saved_editor_layout(True, rerender=False)

        for index, saved_anime in enumerate(self.saved_items):
            if saved_anime["id"] == anime["id"]:
                self.saved_page = index // self.saved_page_size
                break

        panel = ctk.CTkScrollableFrame(
            self.saved_frame,
            width=430,
            height=520,
            fg_color="#ffffff",
            corner_radius=8,
            border_width=2,
            border_color="#172033",
            scrollbar_button_color="#bfdbfe",
            scrollbar_button_hover_color="#93c5fd"
        )
        panel.grid(row=1, column=1, sticky="nsew", padx=(18, 0))
        panel.grid_columnconfigure(0, weight=1)
        self.saved_editor_panel = panel

        close_button = ctk.CTkButton(
            panel,
            text="Cerrar",
            width=92,
            height=34,
            fg_color="#475569",
            hover_color="#334155",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
            command=self._close_saved_editor
        )
        close_button.grid(row=0, column=0, sticky="e", padx=20, pady=(18, 0))

        image_label = ctk.CTkLabel(
            panel,
            text="Cargando...",
            width=150,
            height=212,
            fg_color="#e5edf6",
            text_color="#667085",
            corner_radius=8,
            font=ctk.CTkFont(family=self.font_family, size=12)
        )
        image_label.grid(row=1, column=0, pady=(10, 16))
        image_label.expected_image_url = anime.get("imagen")

        if anime.get("imagen"):
            self._load_card_image(anime["imagen"], image_label, size=(150, 212))
        else:
            self._clear_card_image(image_label, "Sin imagen")

        title_label = ctk.CTkLabel(
            panel,
            text=anime["nombre"],
            text_color="#172033",
            width=350,
            height=66,
            wraplength=350,
            justify="center",
            font=ctk.CTkFont(family=self.font_family, size=21, weight="bold")
        )
        title_label.grid(row=2, column=0, padx=24, pady=(0, 18))

        form_frame = ctk.CTkFrame(panel, fg_color="transparent")
        form_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 24))
        form_frame.grid_columnconfigure(0, weight=1)

        caps_total_value = anime["caps_totales"]
        caps_totales = caps_total_value if caps_total_value is not None else "?"
        max_caps = caps_total_value if caps_total_value is not None else 100
        self.saved_caps_max = max_caps
        self.saved_caps_slice_size = 12
        self.saved_caps_slice_start = 0
        self.saved_caps_progress_label = None
        self.saved_caps_total_text = caps_totales

        # Label que muestra el progreso (ej: 59/64)
        self.saved_caps_progress_label = ctk.CTkLabel(
            form_frame,
            text=f"{anime['caps_vistos']}/{caps_totales}",
            text_color="#ffffff",
            fg_color="#172033",
            corner_radius=7,
            width=86,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        self.saved_caps_progress_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        saved_caps_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        saved_caps_border.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        saved_caps_border.grid_columnconfigure(0, weight=1)
        saved_caps_border.grid_propagate(False)

        # Dropdown personalizado con scroll
        caps_input_frame = ctk.CTkFrame(saved_caps_border, fg_color="#f8fafc", border_width=0, corner_radius=6)
        caps_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        caps_input_frame.grid_columnconfigure(0, weight=1)
        caps_input_frame.grid_columnconfigure(1, weight=0)

        self.saved_caps_entry = ctk.CTkEntry(
            caps_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.saved_caps_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        self.saved_caps_entry.insert(0, str(anime["caps_vistos"]))
        self.saved_caps_entry.bind("<Return>", lambda e: self._on_saved_caps_entry_change())
        self.saved_caps_entry.bind("<FocusOut>", lambda e: self._on_saved_caps_entry_change())

        arrow_btn = ctk.CTkButton(
            caps_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#f8fafc",
            hover_color="#99f6e4",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_saved_caps_dropdown
        )
        arrow_btn.grid(row=0, column=1, sticky="e")

        self.saved_caps_dropdown = None

        estado_label = ctk.CTkLabel(
            form_frame,
            text="Estado",
            text_color="#ffffff",
            fg_color="#172033",
            corner_radius=7,
            width=82,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        estado_label.grid(row=2, column=0, sticky="w", pady=(0, 6))

        saved_estado_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        saved_estado_border.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        saved_estado_border.grid_columnconfigure(0, weight=1)
        saved_estado_border.grid_propagate(False)

        saved_estado_input_frame = ctk.CTkFrame(saved_estado_border, fg_color="#f8fafc", border_width=0, corner_radius=6)
        saved_estado_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        saved_estado_input_frame.grid_columnconfigure(0, weight=1)
        saved_estado_input_frame.grid_columnconfigure(1, weight=0)

        self.saved_estado_entry = ctk.CTkEntry(
            saved_estado_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.saved_estado_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        self.saved_estado_entry.insert(0, anime["estado"])
        self.saved_estado_entry.configure(state="readonly")

        saved_estado_arrow_btn = ctk.CTkButton(
            saved_estado_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#f8fafc",
            hover_color="#99f6e4",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_saved_estado_dropdown
        )
        saved_estado_arrow_btn.grid(row=0, column=1, sticky="e")

        self.saved_estado_dropdown = None

        score_label = ctk.CTkLabel(
            form_frame,
            text="Score",
            text_color="#ffffff",
            fg_color="#172033",
            corner_radius=7,
            width=68,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        score_label.grid(row=4, column=0, sticky="w", pady=(0, 6))

        saved_score_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        saved_score_border.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        saved_score_border.grid_columnconfigure(0, weight=1)
        saved_score_border.grid_propagate(False)

        saved_score_input_frame = ctk.CTkFrame(saved_score_border, fg_color="#f8fafc", border_width=0, corner_radius=6)
        saved_score_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        saved_score_input_frame.grid_columnconfigure(0, weight=1)
        saved_score_input_frame.grid_columnconfigure(1, weight=0)

        self.saved_score_entry = ctk.CTkEntry(
            saved_score_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.saved_score_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        anime_score = anime["score"] if isinstance(anime["score"], int) else 1
        current_score = anime_score if 1 <= anime_score <= 10 else 1
        self.saved_score_entry.insert(0, str(current_score))
        self.saved_score_entry.configure(state="readonly")

        saved_score_arrow_btn = ctk.CTkButton(
            saved_score_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#f8fafc",
            hover_color="#99f6e4",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_saved_score_dropdown
        )
        saved_score_arrow_btn.grid(row=0, column=1, sticky="e")

        self.saved_score_dropdown = None
        self.saved_editor_message = ctk.CTkLabel(
            form_frame,
            text="",
            text_color="#dc2626",
            width=340,
            height=42,
            wraplength=340,
            font=ctk.CTkFont(family=self.font_family, size=12)
        )
        self.saved_editor_message.grid(row=6, column=0, sticky="ew", pady=(0, 10))

        save_button = ctk.CTkButton(
            form_frame,
            text="Guardar cambios",
            height=44,
            fg_color="#0f766e",
            hover_color="#115e59",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._save_saved_anime_changes(anime)
        )
        save_button.grid(row=7, column=0, sticky="ew")

        self.saved_editor_panel.configure(width=430)
        self._style_scroll_background(self.saved_grid)
        self.update_idletasks()
        self.after_idle(self._render_saved_page)

    def _render_saved_editor(self):
        self.update_idletasks()
        self._render_saved_page()

    def _set_saved_editor_layout(self, editor_open, rerender=True):
        if not hasattr(self, "saved_grid") or not self.saved_grid.winfo_exists():
            return

        self.saved_editor_open = editor_open
        self.saved_columns = 2 if editor_open else 3
        self.saved_page_size = 8 if editor_open else 9
        self.saved_grid.configure(width=740 if editor_open else 1138)
        self.saved_frame.grid_columnconfigure(1, minsize=448 if editor_open else 0)

        for column in range(3):
            weight = 1 if column < self.saved_columns else 0
            self.saved_grid.grid_columnconfigure(column, weight=weight)

        if self.saved_page >= self._total_saved_pages():
            self.saved_page = max(0, self._total_saved_pages() - 1)

        if rerender:
            self._render_saved_page()

    def _on_saved_caps_entry_change(self):
        """Actualiza el valor del entry de capítulos en el panel saved"""
        if not hasattr(self, "saved_caps_entry") or not self.saved_caps_entry.winfo_exists():
            return

        try:
            value = int(self.saved_caps_entry.get())
        except ValueError:
            value = 0

        if value < 0:
            value = 0
            self.saved_caps_entry.delete(0, "end")
            self.saved_caps_entry.insert(0, "0")

        if self.saved_caps_max is not None:
            caps_total = self.saved_caps_max
            if caps_total is not None and value > caps_total:
                value = caps_total
                self.saved_caps_entry.delete(0, "end")
                self.saved_caps_entry.insert(0, str(caps_total))

        self._close_saved_caps_dropdown()

    def _show_saved_caps_dropdown(self, event=None):
        """Muestra el dropdown de capítulos con scroll"""
        if hasattr(self, "saved_caps_dropdown") and self.saved_caps_dropdown is not None and self.saved_caps_dropdown.winfo_exists():
            self._close_saved_caps_dropdown()
            return

        self._close_all_dropdowns()

        max_val = self.saved_caps_max if self.saved_caps_max is not None else 100
        values = list(range(0, max_val + 1))

        if not values:
            return

        try:
            entry_x = self.saved_caps_entry.winfo_rootx()
            entry_y = self.saved_caps_entry.winfo_rooty() + self.saved_caps_entry.winfo_height()
        except tk.TclError:
            return

        self.saved_caps_dropdown = ctk.CTkToplevel(self)
        self.saved_caps_dropdown.overrideredirect(True)
        self.saved_caps_dropdown.attributes('-topmost', True)
        self.saved_caps_dropdown.geometry(f"+{entry_x}+{entry_y}")

        scroll_frame = ctk.CTkScrollableFrame(
            self.saved_caps_dropdown,
            width=80,
            height=min(len(values) * 32, 350),
            fg_color="#f1f5f9",
            border_width=1,
            border_color="#cbd5e1"
        )
        scroll_frame.pack(fill="both", expand=False, padx=0, pady=0)

        scroll_frame._parent_canvas.bind("<Map>", lambda e: self._draw_scroll_caps_spin_style(scroll_frame._parent_canvas))
        self._draw_scroll_caps_spin_style(scroll_frame._parent_canvas)

        for val in values:
            btn = ctk.CTkButton(
                scroll_frame,
                text=str(val),
                width=72,
                height=28,
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#172033",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=val: self._select_saved_caps_value(v)
            )
            btn.pack(pady=0, padx=1)

        self._bind_dropdown_close(self.saved_caps_dropdown, self._close_saved_caps_dropdown)
        self._on_master_click_handler(self._close_saved_caps_dropdown)

    def _draw_scroll_caps_spin_style(self, canvas):
        if not canvas.winfo_exists():
            return
        canvas.configure(bg="#f1f5f9", highlightthickness=1, highlightbackground="#cbd5e1")

    def _select_saved_caps_value(self, value):
        """Selecciona un valor del dropdown y lo pone en el entry"""
        if hasattr(self, "saved_caps_entry") and self.saved_caps_entry.winfo_exists():
            self.saved_caps_entry.delete(0, "end")
            self.saved_caps_entry.insert(0, value)
            self._on_saved_caps_entry_change()

    def _close_saved_caps_dropdown(self):
        """Cierra el dropdown de capítulos"""
        if hasattr(self, "saved_caps_dropdown") and self.saved_caps_dropdown is not None and self.saved_caps_dropdown.winfo_exists():
            self.saved_caps_dropdown.destroy()
            self.saved_caps_dropdown = None

    def _show_saved_estado_dropdown(self, event=None):
        if hasattr(self, "saved_estado_dropdown") and self.saved_estado_dropdown is not None and self.saved_estado_dropdown.winfo_exists():
            self._close_saved_estado_dropdown()
            return

        self._close_all_dropdowns()

        estados = ["En proceso", "Completo", "Planeado", "En espera", "Abandonado"]

        try:
            entry_x = self.saved_estado_entry.winfo_rootx()
            entry_y = self.saved_estado_entry.winfo_rooty() + self.saved_estado_entry.winfo_height()
        except tk.TclError:
            return

        self.saved_estado_dropdown = ctk.CTkToplevel(self)
        self.saved_estado_dropdown.overrideredirect(True)
        self.saved_estado_dropdown.attributes('-topmost', True)
        self.saved_estado_dropdown.geometry(f"+{entry_x}+{entry_y}")

        frame = tk.Frame(
            self.saved_estado_dropdown,
            width=180,
            height=len(estados) * 28,
            bg="#f1f5f9",
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        frame.pack(fill="both", expand=False)

        for estado in estados:
            btn = ctk.CTkButton(
                frame,
                text=estado,
                width=170,
                height=28,
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#172033",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=estado: self._select_saved_estado_value(v)
            )
            btn.pack(pady=0, padx=1, fill="x")
        self._bind_dropdown_close(self.saved_estado_dropdown, self._close_saved_estado_dropdown)
        self._on_master_click_handler(self._close_saved_estado_dropdown)

    def _select_saved_estado_value(self, value):
        if hasattr(self, "saved_estado_entry") and self.saved_estado_entry.winfo_exists():
            self.saved_estado_entry.configure(state="normal")
            self.saved_estado_entry.delete(0, "end")
            self.saved_estado_entry.insert(0, value)
            self.saved_estado_entry.configure(state="readonly")
            self._close_saved_estado_dropdown()

    def _close_saved_estado_dropdown(self):
        if hasattr(self, "saved_estado_dropdown") and self.saved_estado_dropdown is not None and self.saved_estado_dropdown.winfo_exists():
            self.saved_estado_dropdown.destroy()
            self.saved_estado_dropdown = None

    def _show_saved_score_dropdown(self, event=None):
        if hasattr(self, "saved_score_dropdown") and self.saved_score_dropdown is not None and self.saved_score_dropdown.winfo_exists():
            self._close_saved_score_dropdown()
            return

        self._close_all_dropdowns()

        scores = [str(n) for n in range(1, 11)]

        try:
            entry_x = self.saved_score_entry.winfo_rootx()
            entry_y = self.saved_score_entry.winfo_rooty() + self.saved_score_entry.winfo_height()
        except tk.TclError:
            return

        self.saved_score_dropdown = ctk.CTkToplevel(self)
        self.saved_score_dropdown.overrideredirect(True)
        self.saved_score_dropdown.attributes('-topmost', True)
        self.saved_score_dropdown.geometry(f"+{entry_x}+{entry_y}")

        canvas = tk.Canvas(
            self.saved_score_dropdown,
            width=80,
            height=len(scores) * 28,
            bg="#f1f5f9",
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        canvas.pack(fill="both", expand=False)

        frame = tk.Frame(canvas, bg="#f1f5f9")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        for score in scores:
            btn = ctk.CTkButton(
                frame,
                text=score,
                width=70,
                height=28,
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#172033",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=score: self._select_saved_score_value(v)
            )
            btn.pack(pady=0, padx=1, fill="x")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_configure)

        self._bind_dropdown_close(self.saved_score_dropdown, self._close_saved_score_dropdown)
        self._on_master_click_handler(self._close_saved_score_dropdown)

    def _select_saved_score_value(self, value):
        if hasattr(self, "saved_score_entry") and self.saved_score_entry.winfo_exists():
            self.saved_score_entry.configure(state="normal")
            self.saved_score_entry.delete(0, "end")
            self.saved_score_entry.insert(0, value)
            self.saved_score_entry.configure(state="readonly")
            self._close_saved_score_dropdown()

    def _close_saved_score_dropdown(self):
        if hasattr(self, "saved_score_dropdown") and self.saved_score_dropdown is not None and self.saved_score_dropdown.winfo_exists():
            self.saved_score_dropdown.destroy()
            self.saved_score_dropdown = None

    def _save_saved_anime_changes(self, anime):
        try:
            caps_vistos = int(self.saved_caps_entry.get())
            score = int(self.saved_score_entry.get())
            estado_val = self.saved_estado_entry.get()
        except ValueError:
            self.saved_editor_message.configure(text="Capitulos y score tienen que ser numeros.")
            return

        caps_totales = anime["caps_totales"]

        if caps_vistos < 0:
            self.saved_editor_message.configure(text="Los capitulos vistos no pueden ser negativos.")
            return

        if caps_totales is not None and caps_vistos > caps_totales:
            self.saved_editor_message.configure(text="Los capitulos vistos no pueden superar el total.")
            return

        if score < 1 or score > 10:
            self.saved_editor_message.configure(text="El score tiene que estar entre 1 y 10.")
            return

        estado = estado_val
        caps_changed = caps_vistos != anime["caps_vistos"]

        if caps_changed:
            actualizar_caps_anime(anime["id"], caps_vistos)
        else:
            if caps_totales is not None and caps_vistos == caps_totales and estado != "Completo":
                self.saved_editor_message.configure(
                    text="Para cambiar el estado de un anime completo, primero bajá los capitulos vistos."
                )
                return

            actualizar_estado_anime(anime["id"], estado)

        actualizar_score_anime(anime["id"], score)
        self._close_saved_editor()
        self._reload_saved_items()

    def _reload_saved_items(self):
        current_query = self.saved_search_entry.get().strip().lower()
        current_estado = self.saved_state_filter.get()
        self.saved_all_items = obtener_animes_usuario()
        self.saved_items = []

        for anime in self.saved_all_items:
            nombre = anime["nombre"].lower()
            coincide_nombre = current_query in nombre
            coincide_estado = current_estado == "Todos" or anime["estado"] == current_estado

            if coincide_nombre and coincide_estado:
                self.saved_items.append(anime)

        if self.saved_page >= self._total_saved_pages():
            self.saved_page = max(0, self._total_saved_pages() - 1)

        self._render_saved_page()

    def _close_saved_editor(self, reset_grid=True):
        if hasattr(self, "saved_frame") and self.saved_frame.winfo_exists():
            for widget in self.saved_frame.grid_slaves(row=1, column=1):
                widget.grid_forget()
                widget.destroy()

        if self.saved_editor_panel is not None and self.saved_editor_panel.winfo_exists():
            self.saved_editor_panel.grid_forget()
            self.saved_editor_panel.destroy()

        self.saved_editor_panel = None
        self.update_idletasks()

        if reset_grid and self.saved_editor_open:
            self._set_saved_editor_layout(False)
        else:
            self.saved_editor_open = False

    def _shorten_saved_name(self, name):
        max_length = 50

        if len(name) <= max_length:
            return name

        return f"{name[:max_length - 3].rstrip()}..."

    def _state_color(self, estado):
        colors = {
            "En proceso": "#2563eb",
            "Completo": "#0f766e",
            "Planeado": "#7c3aed",
            "En espera": "#f59e0b",
            "Abandonado": "#dc2626"
        }
        return colors.get(estado, "#334155")
    def show_add_anime_view(self):
        self.current_view = "add"
        self._clear_view()
        self.title("ANIME TRACKER")
        self.all_anime_items = self.preloaded_anime_items
        self.anime_items = self.preloaded_anime_items
        self.search_after_id = None
        self.anime_page = 0
        self.current_anime_cards = []

        self.add_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.add_frame.grid(row=0, column=0, sticky="nsew", padx=42, pady=(34, 0))
        self._attach_view_background(self.add_frame)
        self.add_frame.grid_columnconfigure(0, weight=1)
        self.add_frame.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self.add_frame, fg_color="transparent", height=74)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header_frame.grid_columnconfigure(0, weight=1, minsize=540)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_propagate(False)
        self._attach_header_background(header_frame, "Agregar anime", "Elegí uno de los animes populares para empezar a guardarlo.")
        self.search_entry = ctk.CTkEntry(
            header_frame,
            width=340,
            height=42,
            placeholder_text="Buscar anime...",
            fg_color="#ffffff",
            border_color="#172033",
            text_color="#172033",
            placeholder_text_color="#94a3b8",
            font=ctk.CTkFont(family=self.font_family, size=14)
        )
        self.search_entry.grid(row=0, column=1, sticky="e")
        self.search_entry.configure(state="disabled")
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)

        self._create_add_bottom_bar()
        self._show_anime_grid(self.preloaded_anime_items)
        if hasattr(self, "bottom_background"):
            self._draw_background(self.bottom_background)
        self._transparent_widget_backgrounds(self.content_frame)
        self._transparent_widget_backgrounds(self.bottom_bar)

    def _create_add_bottom_bar(self):
        back_button = ctk.CTkButton(
            self.bottom_bar,
            text="Volver",
            width=150,
            height=46,
            fg_color="#334155",
            hover_color="#1e293b",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=16, weight="bold"),
            command=self.show_main_view
        )
        back_button.grid(row=0, column=0, sticky="w", padx=32, pady=0)

        self.page_info_label = ctk.CTkLabel(
            self.bottom_bar,
            text="",
            text_color="#172033",
            fg_color="transparent",
            bg_color="transparent",
            font=ctk.CTkFont(family=self.font_family, size=15, weight="bold")
        )
        self.page_info_label.grid(row=0, column=1, pady=0)

        nav_frame = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        nav_frame.grid(row=0, column=2, sticky="e", padx=32, pady=0)

        self.prev_page_button = ctk.CTkButton(
            nav_frame,
            text="Anterior",
            width=120,
            height=42,
            fg_color="#475569",
            hover_color="#334155",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._change_anime_page(-1)
        )
        self.prev_page_button.grid(row=0, column=0, padx=(0, 10))
        self.prev_page_button.configure(border_width=2, border_color="#172033")

        self.next_page_button = ctk.CTkButton(
            nav_frame,
            text="Siguiente",
            width=120,
            height=42,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._change_anime_page(1)
        )
        self.next_page_button.grid(row=0, column=1)
        self.next_page_button.configure(border_width=2, border_color="#172033")

    def _show_anime_grid(self, animes):
        if self.current_view != "add":
            return

        self.all_anime_items = animes
        self.anime_items = animes

        if not self.anime_items:
            empty_label = ctk.CTkLabel(
                self.add_frame,
                text="No hay animes disponibles para mostrar.",
                text_color="#667085",
                font=ctk.CTkFont(family=self.font_family, size=16)
            )
            empty_label.grid(row=1, column=0, sticky="n", pady=(92, 0))
            return

        self.anime_scroll = ctk.CTkScrollableFrame(
            self.add_frame,
            fg_color="#edf4fb",
            width=1138,
            height=520,
            border_width=2,
            border_color="#172033",
            scrollbar_button_color="#bfdbfe",
            scrollbar_button_hover_color="#93c5fd"
        )
        self.anime_scroll.grid(row=1, column=0, sticky="nsew")
        self._style_scroll_background(self.anime_scroll)
        self._bind_scroll_reposition(self.anime_scroll)

        for column in range(self.anime_columns):
            self.anime_scroll.grid_columnconfigure(column, weight=1)

        self._create_anime_card_slots()
        self.search_entry.configure(state="normal")
        self._render_anime_page()

    def _on_search_changed(self, event=None):
        if self.search_after_id is not None:
            self.after_cancel(self.search_after_id)

        self.search_after_id = self.after(180, self._apply_anime_filter)

    def _apply_anime_filter(self):
        self.search_after_id = None
        self._close_add_panel()
        query = self.search_entry.get().strip().lower()

        if query:
            self.anime_items = [
                anime for anime in self.all_anime_items
                if query in anime.get("title", {}).get("romaji", "").lower()
            ]
        else:
            self.anime_items = self.all_anime_items

        self.anime_page = 0

        if self.current_view != "add":
            return

        self._render_anime_page()

    def _total_anime_pages(self):
        if not self.anime_items:
            return 1
        return math.ceil(len(self.anime_items) / self.anime_page_size)

    def _update_page_controls(self):
        if not self.anime_items:
            self.page_info_label.configure(text="Sin resultados")
            self.prev_page_button.configure(state="disabled")
            self.next_page_button.configure(state="disabled")
            return

        total_pages = self._total_anime_pages()
        start = self.anime_page * self.anime_page_size + 1
        end = min((self.anime_page + 1) * self.anime_page_size, len(self.anime_items))
        self.page_info_label.configure(
            text=f"Pagina {self.anime_page + 1}/{total_pages} · {start}-{end} de {len(self.anime_items)}"
        )

        self.prev_page_button.configure(state="normal" if self.anime_page > 0 else "disabled")
        self.next_page_button.configure(
            state="normal" if self.anime_page < total_pages - 1 else "disabled"
        )

    def _change_anime_page(self, direction):
        next_page = self.anime_page + direction

        if next_page < 0 or next_page >= self._total_anime_pages():
            return

        self.anime_page = next_page
        self._render_anime_page()

    def _render_anime_page(self):
        start = self.anime_page * self.anime_page_size
        end = min(start + self.anime_page_size, len(self.anime_items))
        page_items = self.anime_items[start:end]

        try:
            self.anime_scroll._parent_canvas.yview_moveto(0)
        except AttributeError:
            pass

        if not page_items:
            self._hide_all_anime_slots()
            self.no_results_label.grid(row=0, column=0, columnspan=self.anime_columns, pady=90)
            self._update_page_controls()
            return

        self.no_results_label.grid_remove()

        for position, slot in enumerate(self.anime_card_slots):
            if position < len(page_items):
                anime = page_items[position]
                row = position // self.anime_columns
                column = position % self.anime_columns
                slot["card"].grid(row=row, column=column, padx=10, pady=10, sticky="n")
                self._update_anime_card_slot(slot, anime)
            else:
                slot["card"].grid_remove()

        self.current_anime_cards = [
            slot["card"] for slot in self.anime_card_slots[:len(page_items)]
        ]
        self._update_page_controls()
        self._transparent_widget_backgrounds(self.anime_scroll)

    def _hide_all_anime_slots(self):
        for slot in self.anime_card_slots:
            slot["card"].grid_remove()

    def _create_anime_card_slots(self):
        self.anime_card_slots = []
        self.no_results_label = ctk.CTkLabel(
            self.anime_scroll,
            text="No se encontraron animes con ese filtro.",
            text_color="#667085",
            font=ctk.CTkFont(family=self.font_family, size=16)
        )
        self.no_results_label.grid_remove()

        for position in range(self.anime_page_size):
            row = position // self.anime_columns
            column = position % self.anime_columns
            slot = self._create_anime_card_slot(self.anime_scroll, row, column)
            self.anime_card_slots.append(slot)

    def _create_anime_card_slot(self, parent, row, column):
        card = ctk.CTkFrame(
            parent,
            width=158,
            height=254,
            fg_color="#ffffff",
            corner_radius=8,
            border_width=2,
            border_color="#172033"
        )
        card.grid(row=row, column=column, padx=10, pady=10, sticky="n")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)

        image_label = ctk.CTkLabel(
            card,
            text="Cargando...",
            width=118,
            height=166,
            fg_color="#e5edf6",
            text_color="#667085",
            corner_radius=7,
            font=ctk.CTkFont(family=self.font_family, size=12)
        )
        image_label.grid(row=0, column=0, padx=12, pady=(12, 8))
        image_label.expected_image_url = None

        name_label = ctk.CTkLabel(
            card,
            text="",
            text_color="#172033",
            width=132,
            height=48,
            wraplength=132,
            justify="center",
            font=ctk.CTkFont(family=self.font_family, size=12, weight="bold")
        )
        name_label.grid(row=1, column=0, padx=10, pady=(0, 12))

        slot = {
            "card": card,
            "image_label": image_label,
            "name_label": name_label,
            "anime": None
        }
        self._bind_add_card_click(card, slot)
        return slot

    def _bind_add_card_click(self, widget, slot):
        widget.bind("<Button-1>", lambda event: self._open_add_anime_panel(slot.get("anime")))

        try:
            widget.configure(cursor="hand2")
        except (ValueError, tk.TclError):
            pass

        for child in widget.winfo_children():
            self._bind_add_card_click(child, slot)

    def _open_add_anime_panel(self, anime):
        if anime is None:
            return

        self._close_add_panel(reset_grid=False)

        # Set layout and create panel immediately, then render in one go
        self._set_add_editor_layout(True, rerender=False)

        for index, add_anime in enumerate(self.anime_items):
            if add_anime.get("id") == anime.get("id"):
                self.anime_page = index // self.anime_page_size
                break

        panel = ctk.CTkScrollableFrame(
            self.add_frame,
            width=430,
            height=520,
            fg_color="#ffffff",
            corner_radius=8,
            border_width=2,
            border_color="#172033",
            scrollbar_button_color="#bfdbfe",
            scrollbar_button_hover_color="#93c5fd"
        )
        panel.grid(row=1, column=1, sticky="nsew", padx=(18, 0))
        panel.grid_columnconfigure(0, weight=1)
        self.add_editor_panel = panel

        close_button = ctk.CTkButton(
            panel,
            text="Cerrar",
            width=92,
            height=34,
            fg_color="#475569",
            hover_color="#334155",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
            command=self._close_add_panel
        )
        close_button.grid(row=0, column=0, sticky="e", padx=18, pady=(16, 0))

        image_url = anime.get("coverImage", {}).get("medium")
        image_label = ctk.CTkLabel(
            panel,
            text="Cargando...",
            width=132,
            height=186,
            fg_color="#e5edf6",
            text_color="#667085",
            corner_radius=8,
            font=ctk.CTkFont(family=self.font_family, size=12)
        )
        image_label.grid(row=1, column=0, pady=(8, 12))
        image_label.expected_image_url = image_url

        if image_url:
            self._load_card_image(image_url, image_label, size=(132, 186))
        else:
            self._clear_card_image(image_label, "Sin imagen")

        title = anime.get("title", {}).get("romaji", "Sin nombre")
        title_label = ctk.CTkLabel(
            panel,
            text=title,
            text_color="#172033",
            width=350,
            height=58,
            wraplength=350,
            justify="center",
            font=ctk.CTkFont(family=self.font_family, size=20, weight="bold")
        )
        title_label.grid(row=2, column=0, padx=24, pady=(0, 16))

        form_frame = ctk.CTkFrame(panel, fg_color="transparent")
        form_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 24))
        form_frame.grid_columnconfigure(0, weight=1)

        caps_total = anime.get("episodes")
        caps_total_text = caps_total if caps_total is not None else "?"
        max_caps = caps_total if caps_total is not None else 100
        self.add_caps_max = max_caps
        self.add_caps_slice_size = 12
        self.add_caps_slice_start = 0
        self.add_caps_progress_label = None
        self.add_caps_total_text = caps_total_text

        caps_label = ctk.CTkLabel(
            form_frame,
            text="Capitulos",
            text_color="#ffffff",
            fg_color="#172033",
            corner_radius=7,
            width=86,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        caps_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        add_caps_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        add_caps_border.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        add_caps_border.grid_columnconfigure(0, weight=1)
        add_caps_border.grid_propagate(False)

        caps_input_frame = ctk.CTkFrame(add_caps_border, fg_color="#f8fafc", border_width=0, corner_radius=6)
        caps_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        caps_input_frame.grid_columnconfigure(0, weight=1)
        caps_input_frame.grid_columnconfigure(1, weight=0)

        self.add_caps_entry = ctk.CTkEntry(
            caps_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.add_caps_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        self.add_caps_entry.insert(0, "0")
        self.add_caps_entry.bind("<Return>", lambda e: self._on_add_caps_entry_change())
        self.add_caps_entry.bind("<FocusOut>", lambda e: self._on_add_caps_entry_change())

        arrow_btn = ctk.CTkButton(
            caps_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#f8fafc",
            hover_color="#c7d2fe",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_add_caps_dropdown
        )
        arrow_btn.grid(row=0, column=1, sticky="e")

        self.add_caps_total_value = caps_total
        self.add_caps_total_text = caps_total_text
        self.add_caps_max = max_caps
        self.add_caps_slice_size = 10
        self.add_caps_slice_start = 0
        self.add_caps_dropdown = None

        estado_label = ctk.CTkLabel(
            form_frame,
            text="Estado",
            text_color="#ffffff",
            fg_color="#172033",
            corner_radius=7,
            width=82,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        estado_label.grid(row=2, column=0, sticky="w", pady=(0, 6))

        add_estado_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        add_estado_border.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        add_estado_border.grid_columnconfigure(0, weight=1)
        add_estado_border.grid_propagate(False)

        add_estado_input_frame = ctk.CTkFrame(add_estado_border, fg_color="#f8fafc", border_width=0, corner_radius=6)
        add_estado_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        add_estado_input_frame.grid_columnconfigure(0, weight=1)
        add_estado_input_frame.grid_columnconfigure(1, weight=0)

        self.add_estado_entry = ctk.CTkEntry(
            add_estado_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.add_estado_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        self.add_estado_entry.insert(0, "Planeado")
        self.add_estado_entry.configure(state="readonly")

        estado_arrow_btn = ctk.CTkButton(
            add_estado_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#f8fafc",
            hover_color="#c7d2fe",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_add_estado_dropdown
        )
        estado_arrow_btn.grid(row=0, column=1, sticky="e")

        self.add_estado_dropdown = None

        score_label = ctk.CTkLabel(
            form_frame,
            text="Score",
            text_color="#ffffff",
            fg_color="#172033",
            corner_radius=7,
            width=68,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        score_label.grid(row=4, column=0, sticky="w", pady=(0, 6))

        add_score_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        add_score_border.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        add_score_border.grid_columnconfigure(0, weight=1)
        add_score_border.grid_propagate(False)

        add_score_input_frame = ctk.CTkFrame(add_score_border, fg_color="#f8fafc", border_width=0, corner_radius=6)
        add_score_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        add_score_input_frame.grid_columnconfigure(0, weight=1)
        add_score_input_frame.grid_columnconfigure(1, weight=0)

        self.add_score_entry = ctk.CTkEntry(
            add_score_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.add_score_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        self.add_score_entry.insert(0, "1")
        self.add_score_entry.configure(state="readonly")

        score_arrow_btn = ctk.CTkButton(
            add_score_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#f8fafc",
            hover_color="#c7d2fe",
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_add_score_dropdown
        )
        score_arrow_btn.grid(row=0, column=1, sticky="e")

        self.add_score_dropdown = None

        self.add_editor_message = ctk.CTkLabel(
            form_frame,
            text="",
            text_color="#dc2626",
            width=340,
            height=42,
            wraplength=340,
            font=ctk.CTkFont(family=self.font_family, size=12)
        )
        self.add_editor_message.grid(row=6, column=0, sticky="ew", pady=(0, 10))

        add_button = ctk.CTkButton(
            form_frame,
            text="Guardar anime",
            height=44,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._save_new_anime(anime)
        )
        add_button.grid(row=7, column=0, sticky="ew")

        self.update_idletasks()
        self.after_idle(self._render_anime_page)


    def _set_add_editor_layout(self, editor_open, rerender=True):
        if not hasattr(self, "anime_scroll") or not self.anime_scroll.winfo_exists():
            return

        self.add_editor_open = editor_open
        self.anime_columns = 4 if editor_open else 6
        self.anime_page_size = 32 if editor_open else 50
        self.anime_scroll.configure(width=740 if editor_open else 1138)
        self.add_frame.grid_columnconfigure(1, minsize=448 if editor_open else 0)

        for column in range(6):
            weight = 1 if column < self.anime_columns else 0
            self.anime_scroll.grid_columnconfigure(column, weight=weight)

        if self.anime_page >= self._total_anime_pages():
            self.anime_page = max(0, self._total_anime_pages() - 1)

    def _update_add_caps_menu_values(self):
        """Actualiza los valores del menú de capítulos para el panel de agregar anime"""
        if not hasattr(self, "add_caps_menu") or not self.add_caps_menu.winfo_exists():
            return
        
        max_val = self.add_caps_max if self.add_caps_max is not None else 100
        start = self.add_caps_slice_start
        end = min(start + self.add_caps_slice_size, max_val + 1)
        values = [str(number) for number in range(start, end)]
        self.add_caps_menu.configure(values=values)
    
    def _on_add_caps_menu_change(self, value):
        """Callback cuando se selecciona un valor en el menú de capítulos"""
        if hasattr(self, "add_caps_progress_label") and self.add_caps_progress_label.winfo_exists():
            self.add_caps_progress_label.configure(text=f"{value}/{self.add_caps_total_text}")
    
    def _change_add_caps_slice(self, direction):
        """Cambia el slice de valores visibles en el menú de capítulos"""
        max_val = self.add_caps_max if self.add_caps_max is not None else 100
        last_start = (max_val // self.add_caps_slice_size) * self.add_caps_slice_size
        next_start = self.add_caps_slice_start + (direction * self.add_caps_slice_size)
        self.add_caps_slice_start = max(0, min(next_start, last_start))
        self._update_add_caps_menu_values()

    def _on_add_caps_entry_change(self):
        if not hasattr(self, "add_caps_entry") or not self.add_caps_entry.winfo_exists():
            return

        try:
            value = int(self.add_caps_entry.get())
        except ValueError:
            value = 0

        if value < 0:
            value = 0
            self.add_caps_entry.delete(0, "end")
            self.add_caps_entry.insert(0, "0")

        if self.add_caps_max is not None:
            caps_total = self.add_caps_max
            if caps_total is not None and value > caps_total:
                value = caps_total
                self.add_caps_entry.delete(0, "end")
                self.add_caps_entry.insert(0, str(caps_total))

        if hasattr(self, "add_caps_progress_label") and self.add_caps_progress_label is not None and self.add_caps_progress_label.winfo_exists():
            self.add_caps_progress_label.configure(text=f"{value}/{self.add_caps_total_text}")

        self._close_add_caps_dropdown()

    def _show_add_caps_dropdown(self, event=None):
        if hasattr(self, "add_caps_dropdown") and self.add_caps_dropdown is not None and self.add_caps_dropdown.winfo_exists():
            self._close_add_caps_dropdown()
            return

        self._close_all_dropdowns()

        max_val = self.add_caps_max if self.add_caps_max is not None else 100
        values = list(range(0, max_val + 1))

        if not values:
            return

        try:
            entry_x = self.add_caps_entry.winfo_rootx()
            entry_y = self.add_caps_entry.winfo_rooty() + self.add_caps_entry.winfo_height()
        except tk.TclError:
            return

        self.add_caps_dropdown = ctk.CTkToplevel(self)
        self.add_caps_dropdown.overrideredirect(True)
        self.add_caps_dropdown.attributes('-topmost', True)
        self.add_caps_dropdown.geometry(f"+{entry_x}+{entry_y}")

        scroll_frame = ctk.CTkScrollableFrame(
            self.add_caps_dropdown,
            width=80,
            height=min(len(values) * 32, 350),
            fg_color="#f1f5f9",
            border_width=1,
            border_color="#cbd5e1"
        )
        scroll_frame.pack(fill="both", expand=False, padx=0, pady=0)

        scroll_frame._parent_canvas.bind("<Map>", lambda e: self._draw_scroll_caps_spin_style(scroll_frame._parent_canvas))
        self._draw_scroll_caps_spin_style(scroll_frame._parent_canvas)

        for val in values:
            btn = ctk.CTkButton(
                scroll_frame,
                text=str(val),
                width=72,
                height=28,
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#172033",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=val: self._select_add_caps_value(v)
            )
            btn.pack(pady=0, padx=1)

        self._bind_dropdown_close(self.add_caps_dropdown, self._close_add_caps_dropdown)
        self._on_master_click_handler(self._close_add_caps_dropdown)

    def _select_add_caps_value(self, value):
        if hasattr(self, "add_caps_entry") and self.add_caps_entry.winfo_exists():
            self.add_caps_entry.delete(0, "end")
            self.add_caps_entry.insert(0, value)
            self._on_add_caps_entry_change()

    def _close_add_caps_dropdown(self):
        if hasattr(self, "add_caps_dropdown") and self.add_caps_dropdown is not None and self.add_caps_dropdown.winfo_exists():
            self.add_caps_dropdown.destroy()
            self.add_caps_dropdown = None

    def _show_add_estado_dropdown(self, event=None):
        if hasattr(self, "add_estado_dropdown") and self.add_estado_dropdown is not None and self.add_estado_dropdown.winfo_exists():
            self._close_add_estado_dropdown()
            return

        self._close_all_dropdowns()

        estados = ["En proceso", "Completo", "Planeado", "En espera", "Abandonado"]

        try:
            entry_x = self.add_estado_entry.winfo_rootx()
            entry_y = self.add_estado_entry.winfo_rooty() + self.add_estado_entry.winfo_height()
        except tk.TclError:
            return

        self.add_estado_dropdown = ctk.CTkToplevel(self)
        self.add_estado_dropdown.overrideredirect(True)
        self.add_estado_dropdown.attributes('-topmost', True)
        self.add_estado_dropdown.geometry(f"+{entry_x}+{entry_y}")

        canvas = tk.Canvas(
            self.add_estado_dropdown,
            width=180,
            height=len(estados) * 28,
            bg="#f1f5f9",
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        canvas.pack(fill="both", expand=False)

        frame = tk.Frame(canvas, bg="#f1f5f9")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        for estado in estados:
            btn = ctk.CTkButton(
                frame,
                text=estado,
                width=170,
                height=28,
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#172033",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=estado: self._select_add_estado_value(v)
            )
            btn.pack(pady=0, padx=1, fill="x")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_configure)

        self._bind_dropdown_close(self.add_estado_dropdown, self._close_add_estado_dropdown)
        self._on_master_click_handler(self._close_add_estado_dropdown)

    def _select_add_estado_value(self, value):
        if hasattr(self, "add_estado_entry") and self.add_estado_entry.winfo_exists():
            self.add_estado_entry.configure(state="normal")
            self.add_estado_entry.delete(0, "end")
            self.add_estado_entry.insert(0, value)
            self.add_estado_entry.configure(state="readonly")
            self._close_add_estado_dropdown()

    def _close_add_estado_dropdown(self):
        if hasattr(self, "add_estado_dropdown") and self.add_estado_dropdown is not None and self.add_estado_dropdown.winfo_exists():
            self.add_estado_dropdown.destroy()
            self.add_estado_dropdown = None

    def _show_add_score_dropdown(self, event=None):
        if hasattr(self, "add_score_dropdown") and self.add_score_dropdown is not None and self.add_score_dropdown.winfo_exists():
            self._close_add_score_dropdown()
            return

        self._close_all_dropdowns()

        scores = [str(n) for n in range(1, 11)]

        try:
            entry_x = self.add_score_entry.winfo_rootx()
            entry_y = self.add_score_entry.winfo_rooty() + self.add_score_entry.winfo_height()
        except tk.TclError:
            return

        self.add_score_dropdown = ctk.CTkToplevel(self)
        self.add_score_dropdown.overrideredirect(True)
        self.add_score_dropdown.attributes('-topmost', True)
        self.add_score_dropdown.geometry(f"+{entry_x}+{entry_y}")

        canvas = tk.Canvas(
            self.add_score_dropdown,
            width=80,
            height=len(scores) * 28,
            bg="#f1f5f9",
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        canvas.pack(fill="both", expand=False)

        frame = tk.Frame(canvas, bg="#f1f5f9")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        for score in scores:
            btn = ctk.CTkButton(
                frame,
                text=score,
                width=70,
                height=28,
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#172033",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=score: self._select_add_score_value(v)
            )
            btn.pack(pady=0, padx=1, fill="x")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_configure)

        self._bind_dropdown_close(self.add_score_dropdown, self._close_add_score_dropdown)
        self._on_master_click_handler(self._close_add_score_dropdown)

    def _select_add_score_value(self, value):
        if hasattr(self, "add_score_entry") and self.add_score_entry.winfo_exists():
            self.add_score_entry.configure(state="normal")
            self.add_score_entry.delete(0, "end")
            self.add_score_entry.insert(0, value)
            self.add_score_entry.configure(state="readonly")
            self._close_add_score_dropdown()

    def _close_add_score_dropdown(self):
        if hasattr(self, "add_score_dropdown") and self.add_score_dropdown is not None and self.add_score_dropdown.winfo_exists():
            self.add_score_dropdown.destroy()
            self.add_score_dropdown = None

    def _save_new_anime(self, anime):
        try:
            caps_vistos = int(self.add_caps_entry.get())
            score = int(self.add_score_entry.get())
        except ValueError:
            self.add_editor_message.configure(text="Capitulos y score tienen que ser numeros.")
            return

        nombre = anime.get("title", {}).get("romaji", "Sin nombre")
        caps_totales = anime.get("episodes")

        if self._anime_already_saved(nombre):
            self.add_editor_message.configure(text="Ese anime ya esta guardado.")
            return

        if caps_vistos < 0:
            self.add_editor_message.configure(text="Los capitulos vistos no pueden ser negativos.")
            return

        if caps_totales is not None and caps_vistos > caps_totales:
            self.add_editor_message.configure(text="Los capitulos vistos no pueden superar el total.")
            return

        estado = self.add_estado_entry.get()
        if estado == "Completo" and caps_totales is not None:
            caps_vistos = caps_totales

        agregar_anime(
            nombre,
            caps_vistos,
            caps_totales,
            estado,
            score,
            anime.get("id"),
            anime.get("coverImage", {}).get("medium")
        )
        self.add_editor_message.configure(text="Anime guardado.", text_color="#0f766e")

    def _anime_already_saved(self, nombre):
        return any(anime["nombre"] == nombre for anime in obtener_animes_usuario())

    def _close_add_panel(self, reset_grid=True):
        if hasattr(self, "add_frame") and self.add_frame.winfo_exists():
            for widget in self.add_frame.grid_slaves(row=1, column=1):
                widget.grid_forget()
                widget.destroy()

        if self.add_editor_panel is not None and self.add_editor_panel.winfo_exists():
            self.add_editor_panel.grid_forget()
            self.add_editor_panel.destroy()

        self.add_editor_panel = None
        self.update_idletasks()

        if reset_grid and self.add_editor_open:
            self._set_add_editor_layout(False)
        else:
            self.add_editor_open = False
    def _update_anime_card_slot(self, slot, anime):
        slot["anime"] = anime
        name = self._shorten_anime_name(anime.get("title", {}).get("romaji", "Sin nombre"))
        slot["name_label"].configure(text=name)

        image_label = slot["image_label"]
        image_url = anime.get("coverImage", {}).get("medium")
        image_label.expected_image_url = image_url
        self._clear_card_image(image_label, "Cargando...")

        if image_url:
            self._load_card_image(image_url, image_label)
        else:
            self._clear_card_image(image_label, "Sin imagen")

    def _shorten_anime_name(self, name):
        max_length = 46

        if len(name) <= max_length:
            return name

        return f"{name[:max_length - 3].rstrip()}..."

    def _load_card_image(self, image_url, image_label, size=(118, 166)):
        cached_image = self.image_cache.get(image_url)

        if cached_image is not None:
            self._set_card_image(image_label, image_url, cached_image, size)
            return

        threading.Thread(
            target=self._download_card_image,
            args=(image_url, image_label, size),
            daemon=True
        ).start()

    def _download_card_image(self, image_url, image_label, size):
        try:
            response = requests.get(image_url, timeout=12)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
        except (requests.RequestException, OSError):
            self.after(0, lambda: self._set_missing_image(image_label, image_url))
            return

        self.image_cache[image_url] = image
        self.after(0, lambda: self._set_card_image(image_label, image_url, image, size))

    def _set_card_image(self, image_label, image_url, pil_image, size):
        if self.current_view not in ("add", "saved") or not image_label.winfo_exists():
            return
        if getattr(image_label, "expected_image_url", None) != image_url:
            return

        ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)
        self._clear_card_image(image_label, "")
        image_label.configure(image=ctk_image, text="")
        image_label.image = ctk_image
    
    def _set_missing_image(self, image_label, image_url):
        if self.current_view not in ("add", "saved") or not image_label.winfo_exists():
            return
        if getattr(image_label, "expected_image_url", None) != image_url:
            return

        self._clear_card_image(image_label, "Sin imagen")

    def _clear_card_image(self, image_label, text=""):
        if not image_label.winfo_exists():
            return

        image_label.image = None

        try:
            image_label._label.configure(image="")
        except (AttributeError, tk.TclError):
            pass

        image_label.configure(text=text)

    def _create_action_card(self, parent, title, detail, color, hover, command=None, column=None, x=None, y=None):
        card = ctk.CTkFrame(
            parent,
            width=290,
            height=164,
            fg_color="#ffffff",
            corner_radius=8,
            border_width=2,
            border_color="#172033"
        )
        if x is not None and y is not None:
            card.place(x=x, y=y)
        else:
            card.grid(row=0, column=column, padx=20)
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            card,
            text=title,
            text_color="#172033",
            font=ctk.CTkFont(family=self.font_family, size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="w", padx=22, pady=(22, 4))

        detail_label = ctk.CTkLabel(
            card,
            text=detail,
            text_color="#667085",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold")
        )
        detail_label.grid(row=1, column=0, sticky="w", padx=22, pady=(0, 22))

        button = ctk.CTkButton(
            card,
            text="Abrir",
            width=128,
            height=38,
            fg_color=color,
            hover_color=hover,
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=command
        )
        button.grid(row=2, column=0, sticky="w", padx=22)


if __name__ == "__main__":
    app = AnimeTrackerApp()
    app.mainloop()