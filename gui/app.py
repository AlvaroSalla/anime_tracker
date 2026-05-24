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
        self.background_color = "#0f172a"
        self.configure(fg_color=self.background_color)
        self.font_family = "Montserrat"
        self.icon_path = Path(__file__).resolve().parent.parent / "icon.ico"
        self.image_cache = {}
        self.current_view = "loading"
        self._page_info_text = ""
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
        self._main_cards = []
        self._editor_animation_job = None
        self._editor_animation_token = 0

        # Navigation state for canvas-drawn buttons (Anterior/Siguiente)
        self._nav_prev_enabled = False
        self._nav_next_enabled = False

        self._set_window_icon(self)

        ctk.set_appearance_mode("dark")
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
        self.bottom_background.tag_bind("nav_prev", "<Button-1>", self._on_nav_prev_clicked)
        self.bottom_background.tag_bind("nav_next", "<Button-1>", self._on_nav_next_clicked)
        self.bottom_background.tag_bind("nav_prev", "<Enter>", self._on_nav_prev_enter)
        self.bottom_background.tag_bind("nav_prev", "<Leave>", self._on_nav_prev_leave)
        self.bottom_background.tag_bind("nav_next", "<Enter>", self._on_nav_next_enter)
        self.bottom_background.tag_bind("nav_next", "<Leave>", self._on_nav_next_leave)
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
            widget.configure(bg_color="transparent" if is_transparent_surface else (parent_color or "#1e293b"))
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
        self._cancel_editor_animation()

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
        self._cancel_editor_animation()

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

        self._page_info_text = ""
        self._clear_frame(self.content_frame)
        self._clear_frame(self.bottom_bar)
        self.current_anime_cards = []
        self.anime_card_slots = []
        self._main_cards.clear()

    def _cancel_editor_animation(self):
        self._editor_animation_token += 1

        if self._editor_animation_job is not None:
            try:
                self.after_cancel(self._editor_animation_job)
            except (ValueError, tk.TclError):
                pass
            self._editor_animation_job = None

    def _ease_out_cubic(self, progress):
        return 1 - pow(1 - progress, 3)

    def _animate_editor_transition(self, view, opening, on_complete=None):
        if view == "add":
            grid = getattr(self, "anime_scroll", None)
            frame = getattr(self, "add_frame", None)
            panel = getattr(self, "add_editor_panel", None)
            panel_width = 430
            compact_grid_width = 740
            side_width = 448
            column_count = 6
        else:
            grid = getattr(self, "saved_grid", None)
            frame = getattr(self, "saved_frame", None)
            panel = getattr(self, "saved_editor_panel", None)
            panel_width = 430
            compact_grid_width = 740
            side_width = 448
            column_count = 3

        if grid is None or frame is None or not grid.winfo_exists():
            if on_complete is not None:
                on_complete()
            return

        self._cancel_editor_animation()
        token = self._editor_animation_token
        frames = 12
        delay = 12

        start_panel = 1 if opening else panel_width
        end_panel = panel_width if opening else 1

        try:
            grid.configure(width=compact_grid_width)
            frame.grid_columnconfigure(1, minsize=side_width)
        except (ValueError, tk.TclError):
            if on_complete is not None:
                on_complete()
            return

        if panel is not None and panel.winfo_exists():
            try:
                panel.configure(width=start_panel)
            except (ValueError, tk.TclError, AttributeError):
                pass

        def step(index=0):
            if token != self._editor_animation_token:
                return

            progress = self._ease_out_cubic(index / frames)
            current_panel_width = round(start_panel + (end_panel - start_panel) * progress)

            try:
                if panel is not None and panel.winfo_exists():
                    panel.configure(width=max(1, current_panel_width))
            except (ValueError, tk.TclError):
                return

            if index < frames:
                self._editor_animation_job = self.after(delay, lambda: step(index + 1))
                return

            self._editor_animation_job = None
            frame.grid_columnconfigure(1, minsize=side_width)
            grid.configure(width=compact_grid_width)
            if panel is not None and panel.winfo_exists():
                panel.configure(width=end_panel)

            for column in range(column_count):
                if view == "add":
                    weight = 1 if column < self.anime_columns else 0
                else:
                    weight = 1 if column < self.saved_columns else 0
                grid.grid_columnconfigure(column, weight=weight)

            if on_complete is not None:
                on_complete()

        step()

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
                fill="#f1f5f9",
                font=(self.font_family, 24, "bold")
            )
            current_canvas.create_text(
                0,
                54,
                text=subtitle,
                anchor="w",
                fill="#94a3b8",
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
            bg="#0f172a"
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
                    fill="#94a3b8",
                    font=(self.font_family, 13, "bold")
                )

            background.move("all", -offset_x, -offset_y)
            return

        background.create_rectangle(0, 0, width, height, fill="#0f172a", outline="")

        washes = [
            ("#1e293b", (-240, -80, 470, 370)),
            ("#1e293b", (width - 420, -170, width + 250, 330)),
            ("#1e293b", (width - 360, height - 300, width + 210, height + 180)),
            ("#1e293b", (-230, height - 260, 360, height + 150)),
            ("#1e293b", (width * 0.34, -150, width * 0.75, 180)),
            ("#1e293b", (width * 0.25, height - 205, width * 0.62, height + 120)),
        ]

        for color, bounds in washes:
            background.create_oval(*bounds, fill=color, outline="")

        for offset, color in [(0, "#1e293b"), (80, "#1e293b")]:
            for x in range(-80 + offset, width + 180, 170):
                background.create_line(x, 0, x - 110, height, fill=color, width=1)

        for y in range(74, height + 120, 132):
            background.create_line(0, y, width, y - 62, fill="#1e293b", width=1)

        ribbons = [
            ("#334155", 5, [(-120, 122), (135, 54), (380, 124), (635, 70), (width + 120, 150)]),
            ("#334155", 4, [(-80, height - 168), (200, height - 238), (470, height - 180), (780, height - 270), (width + 85, height - 215)]),
            ("#334155", 5, [(width - 440, -70), (width - 300, 115), (width - 110, 185), (width + 80, 340)]),
            ("#334155", 3, [(70, height * 0.52), (210, height * 0.46), (360, height * 0.54), (540, height * 0.48)]),
            ("#334155", 3, [(width * 0.20, 42), (width * 0.31, 92), (width * 0.43, 48), (width * 0.58, 104)]),
            ("#334155", 2, [(width * 0.60, height - 78), (width * 0.72, height - 135), (width * 0.84, height - 92), (width * 0.96, height - 150)]),
        ]

        for color, line_width, points in ribbons:
            coords = [coordinate for point in points for coordinate in point]
            background.create_line(*coords, fill=color, width=line_width, smooth=True, capstyle=tk.ROUND)

        marks = [
            (width * 0.48, 76, "#475569"),
            (width * 0.72, 316, "#475569"),
            (width * 0.16, height * 0.56, "#475569"),
            (width * 0.86, height * 0.62, "#475569"),
            (width - 128, 78, "#475569"),
            (138, 284, "#475569"),
        ]

        for x, y, color in marks:
            background.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="")
            background.create_line(x - 12, y, x + 12, y, fill="#64748b", width=2)
            background.create_line(x, y - 12, x, y + 12, fill="#64748b", width=2)

        for x in range(38, width, 235):
            y = 36 + (x % 4) * 31
            background.create_arc(x, y, x + 58, y + 58, start=18, extent=252, outline="#334155", width=2, style=tk.ARC)

        title_lines = [
            (width * 0.39, height * 0.36, 74),
            (width * 0.46, height * 0.40, 112),
            (width * 0.53, height * 0.36, 74),
        ]

        for x, y, length in title_lines:
            background.create_line(x - length / 2, y, x + length / 2, y, fill="#334155", width=5, capstyle=tk.ROUND)

        if background is getattr(self, "content_background", None) and self.current_view == "main":
            background.create_text(
                width / 2,
                118,
                text="Anime Tracker",
                fill="#f1f5f9",
                font=(self.font_family, 38, "bold")
            )
            background.create_text(
                width / 2,
                180,
                text="Tu biblioteca de anime, organizada y lista para seguir mirando.",
                fill="#94a3b8",
                font=(self.font_family, 13, "bold")
            )

        if background is getattr(self, "bottom_background", None) and self.current_view not in ("loading", "main") and self._page_info_text:
            background.create_text(
                width / 2,
                height - 30,
                text=self._page_info_text,
                fill="#f1f5f9",
                font=(self.font_family, 15, "bold"),
                anchor="center"
            )

            prev_fill = "#f1f5f9" if self._nav_prev_enabled else "#475569"
            next_fill = "#f1f5f9" if self._nav_next_enabled else "#475569"
            background.create_text(
                width - 230,
                height - 30,
                text="← Anterior",
                fill=prev_fill,
                font=(self.font_family, 15, "bold"),
                anchor="center",
                tags=("nav_prev",)
            )
            background.create_text(
                width - 100,
                height - 30,
                text="Siguiente →",
                fill=next_fill,
                font=(self.font_family, 15, "bold"),
                anchor="center",
                tags=("nav_next",)
            )

        background.move("all", -offset_x, -offset_y)

    def _redraw_bottom_text(self):
        if hasattr(self, "bottom_background") and self.bottom_background.winfo_exists():
            self._draw_background(self.bottom_background)

    def _on_nav_prev_clicked(self, event):
        if not self._nav_prev_enabled:
            return
        if self.current_view == "add":
            self._change_anime_page(-1)
        elif self.current_view == "saved":
            self._change_saved_page(-1)

    def _on_nav_next_clicked(self, event):
        if not self._nav_next_enabled:
            return
        if self.current_view == "add":
            self._change_anime_page(1)
        elif self.current_view == "saved":
            self._change_saved_page(1)

    def _on_nav_prev_enter(self, event):
        if self._nav_prev_enabled:
            self.bottom_background.itemconfigure("nav_prev", fill="#60a5fa")

    def _on_nav_prev_leave(self, event):
        self.bottom_background.itemconfigure("nav_prev", fill="#f1f5f9" if self._nav_prev_enabled else "#475569")

    def _on_nav_next_enter(self, event):
        if self._nav_next_enabled:
            self.bottom_background.itemconfigure("nav_next", fill="#60a5fa")

    def _on_nav_next_leave(self, event):
        self.bottom_background.itemconfigure("nav_next", fill="#f1f5f9" if self._nav_next_enabled else "#475569")

    def _style_scroll_background(self, scroll_frame):
        try:
            canvas = scroll_frame._parent_canvas
            inner_frame = scroll_frame._scrollable_frame
        except AttributeError:
            return

        canvas.configure(bg="#0f172a", highlightthickness=0, bd=0)

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
        if self.current_view == "main" and len(self._main_cards) == 2:
            self.update_idletasks()
            win_width = max(self.winfo_width(), 1280)
            card_w = 290
            gap = 80
            start_x = (win_width - (card_w * 2 + gap)) // 2
            self._main_cards[0].place_configure(x=start_x)
            self._main_cards[1].place_configure(x=start_x + card_w + gap)
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
        canvas.configure(bg="#1e293b", highlightthickness=1, highlightbackground="#475569")

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
        canvas.configure(bg="#1e293b", highlightthickness=1, highlightbackground="#475569")

    def _draw_scroll_background(self, canvas):
        if not canvas.winfo_exists():
            return

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        canvas.delete("scroll_bg")

        canvas.create_rectangle(0, 0, width, height, fill=self.background_color, outline="", tags="scroll_bg")

        for x in range(24, max(width, 1), 145):
            canvas.create_line(x, 0, x - 78, height, fill="#1e293b", width=1, tags="scroll_bg")

        for y in range(58, max(height, 1), 124):
            canvas.create_line(0, y, width, y - 42, fill="#1e293b", width=1, tags="scroll_bg")

        paths = [
            ("#334155", 3, [(-40, 62), (width * 0.20, 26), (width * 0.42, 70), (width * 0.65, 36), (width + 40, 84)]),
            ("#334155", 3, [(-35, height - 78), (width * 0.22, height - 118), (width * 0.47, height - 88), (width * 0.76, height - 132), (width + 34, height - 96)]),
            ("#334155", 2, [(width - 225, 10), (width - 140, 96), (width - 42, 118), (width + 28, 205)]),
        ]

        for color, line_width, points in paths:
            coords = [coordinate for point in points for coordinate in point]
            canvas.create_line(*coords, fill=color, width=line_width, smooth=True, capstyle=tk.ROUND, tags="scroll_bg")

        for x, y, color in [
            (width * 0.36, 64, "#475569"),
            (width * 0.68, 112, "#475569"),
            (width * 0.18, height - 86, "#475569"),
            (width * 0.86, height - 68, "#475569"),
        ]:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="", tags="scroll_bg")
            canvas.create_line(x - 10, y, x + 10, y, fill="#64748b", width=2, tags="scroll_bg")
            canvas.create_line(x, y - 10, x, y + 10, fill="#64748b", width=2, tags="scroll_bg")

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

        self.update_idletasks()
        win_width = max(self.winfo_width(), 1280)
        card_w = 290
        gap = 80
        start_x = (win_width - (card_w * 2 + gap)) // 2

        self._main_cards.clear()
        card1 = self._create_action_card(
            self.content_frame,
            x=start_x,
            y=230,
            title="Agregar anime",
            detail="Buscar y sumar series",
            color="#2563eb",
            hover="#1d4ed8",
            command=self.show_add_anime_view
        )
        self._main_cards.append(card1)
        card2 = self._create_action_card(
            self.content_frame,
            x=start_x + card_w + gap,
            y=230,
            title="Ver animes guardados",
            detail="Revisar y editar progreso",
            color="#0f766e",
            hover="#115e59",
            command=self.show_saved_anime_view
        )
        self._main_cards.append(card2)

        exit_button = ctk.CTkButton(
            self.bottom_bar,
            text="Salir",
            width=150,
            height=46,
            fg_color="#475569",
            hover_color="#64748b",
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
        self.saved_frame.grid(row=0, column=0, sticky="nsew", padx=68, pady=(12, 22))
        self._attach_view_background(self.saved_frame)
        self.saved_frame.grid_columnconfigure(0, weight=1)
        self.saved_frame.grid_columnconfigure(1, weight=0)
        self.saved_frame.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self.saved_frame, fg_color="transparent", height=74)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header_frame.grid_columnconfigure(0, weight=1, minsize=540)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_columnconfigure(2, weight=0)
        header_frame.grid_propagate(False)
        self._attach_header_background(header_frame, "Animes guardados", "Revisá tu progreso, capítulos vistos y estado actual.")

        self.saved_search_entry = ctk.CTkEntry(
            header_frame,
            width=300,
            height=42,
            placeholder_text="Buscar guardado...",
            fg_color="transparent",
            border_width=2,
            border_color="#64748b",
            text_color="#f1f5f9",
            placeholder_text_color="#94a3b8",
            font=ctk.CTkFont(family=self.font_family, size=14)
        )
        self.saved_search_entry.grid(row=0, column=1, padx=(0, 12), pady=(14, 0))
        self.saved_search_entry.bind("<KeyRelease>", self._on_saved_filter_changed)

        filter_frame = ctk.CTkFrame(header_frame, fg_color="transparent", border_width=2, border_color="#64748b", corner_radius=6, width=164, height=46)
        filter_frame.grid(row=0, column=2, pady=(14, 0))
        filter_frame.grid_propagate(False)

        self.saved_state_filter = ctk.CTkOptionMenu(
            filter_frame,
            width=160,
            height=42,
            values=["Todos", "En proceso", "Completo", "Planeado", "En espera", "Abandonado"],
            fg_color="#1e293b",
            button_color="#475569",
            button_hover_color="#64748b",
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14),
            command=lambda _: self._apply_saved_filter()
        )
        self.saved_state_filter.grid(row=0, column=0, padx=2, pady=2)
        self.saved_state_filter.set("Todos")

        self.saved_grid = ctk.CTkScrollableFrame(
            self.saved_frame,
            fg_color="#0f172a",
            width=1138,
            height=520,
            border_width=0,
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
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
            width=120,
            height=38,
            fg_color="#475569",
            hover_color="#64748b",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
            command=self.show_main_view
        )
        back_button.grid(row=0, column=0, sticky="w", padx=32, pady=0)

        self._nav_prev_enabled = False
        self._nav_next_enabled = False

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

        if not page_items:
            empty_label = ctk.CTkLabel(
                self.saved_grid,
                text="No hay animes guardados para mostrar.",
                text_color="#94a3b8",
                font=ctk.CTkFont(family=self.font_family, size=16)
            )
            empty_label.grid(row=0, column=0, columnspan=self.saved_columns, pady=90)
            self._update_saved_page_controls()
            return

        sin_total = [a for a in page_items if a["caps_totales"] is None]
        if sin_total:
            ids = [str(a["id_api"]) for a in sin_total if a.get("id_api")]
            if ids:
                q = "query($ids:[Int]){Page(page:1,perPage:50){media(id_in:$ids,type:ANIME){id episodes nextAiringEpisode{episode}}}}"
                ids_int = [a["id_api"] for a in sin_total if a.get("id_api")]
                try:
                    r = requests.post("https://graphql.anilist.co", json={"query": q, "variables": {"ids": ids_int}}, timeout=10)
                    d = r.json()
                    for media in d.get("data", {}).get("Page", {}).get("media", []):
                        mid = media["id"]
                        eps = media.get("episodes") or media.get("nextAiringEpisode", {}).get("episode")
                        if eps:
                            actuales = eps - 1 if media.get("nextAiringEpisode") and not media.get("episodes") else eps
                            for a in sin_total:
                                if a.get("id_api") == mid:
                                    a["caps_totales"] = actuales
                except Exception:
                    pass

        for position, anime in enumerate(page_items):
            row = position // self.saved_columns
            column = position % self.saved_columns
            self._create_saved_anime_card(self.saved_grid, anime, row, column)

        self._update_saved_page_controls()
        self._transparent_widget_backgrounds(self.saved_grid)

    def _update_saved_page_controls(self):
        if not self.saved_items:
            self._page_info_text = "Sin resultados"
            self._nav_prev_enabled = False
            self._nav_next_enabled = False
            self._redraw_bottom_text()
            return

        total_pages = self._total_saved_pages()
        start = self.saved_page * self.saved_page_size + 1
        end = min((self.saved_page + 1) * self.saved_page_size, len(self.saved_items))
        self._page_info_text = f"Pagina {self.saved_page + 1}/{total_pages} · {start}-{end} de {len(self.saved_items)}"

        self._nav_prev_enabled = self.saved_page > 0
        self._nav_next_enabled = self.saved_page < total_pages - 1
        self._redraw_bottom_text()

    def _create_saved_anime_card(self, parent, anime, row, column):
        card_width = 338 if self.saved_editor_open else 350
        text_width = 206 if self.saved_editor_open else 218

        card = ctk.CTkFrame(
            parent,
            width=card_width,
            height=176,
            fg_color="#1e293b",
            corner_radius=8,
            border_width=2,
            border_color="#475569"
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
            fg_color="#0f172a",
            text_color="#64748b",
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
            text_color="#f1f5f9",
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
            text_color="#94a3b8",
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
            text_color="#94a3b8",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        score_label.grid(row=0, column=1, sticky="e")

        card.anime_data = anime
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
        is_switch = self.saved_editor_open or self.saved_editor_panel is not None

        if is_switch:
            self._cancel_editor_animation()
            self._close_all_dropdowns()
            self._clear_saved_highlight()
            old_panel = self.saved_editor_panel
            self._build_saved_panel(anime)
            if old_panel is not None:
                try:
                    if old_panel.winfo_exists():
                        old_panel.grid_forget()
                        old_panel.destroy()
                except tk.TclError:
                    pass
            self._apply_saved_highlight()
            return

        self._close_saved_editor(reset_grid=False)
        self._set_saved_editor_layout(True, rerender=True, animated=True)
        self._build_saved_panel(anime)
        self._animate_editor_transition("saved", True)
        self._apply_saved_highlight()

    def _build_saved_panel(self, anime):
        for index, saved_anime in enumerate(self.saved_items):
            if saved_anime["id"] == anime["id"]:
                self.saved_page = index // self.saved_page_size
                break

        panel = ctk.CTkScrollableFrame(
            self.saved_frame,
            width=430,
            height=520,
            fg_color="#1e293b",
            corner_radius=8,
            border_width=2,
            border_color="#475569",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
        )
        panel.grid(row=1, column=1, sticky="nsew", padx=(18, 0))
        panel.grid_columnconfigure(0, weight=1)
        self.saved_editor_panel = panel
        self._highlighted_saved_id = anime.get("id")

        close_button = ctk.CTkButton(
            panel,
            text="Cerrar",
            width=92,
            height=34,
            fg_color="#475569",
            hover_color="#64748b",
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
            fg_color="#0f172a",
            text_color="#64748b",
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
            text_color="#f1f5f9",
            width=350,
            height=66,
            wraplength=350,
            justify="center",
            font=ctk.CTkFont(family=self.font_family, size=21, weight="bold")
        )
        title_label.grid(row=2, column=0, padx=24, pady=(0, 6))

        estado_api = self._estado_api_label(anime.get("estado_api"))
        self.saved_api_status_label = ctk.CTkLabel(
            panel,
            text=estado_api["text"],
            text_color="#ffffff",
            fg_color=estado_api["color"],
            corner_radius=7,
            width=110,
            height=26,
            font=ctk.CTkFont(family=self.font_family, size=12, weight="bold")
        )
        self.saved_api_status_label.grid(row=3, column=0, pady=(0, 12))

        form_frame = ctk.CTkFrame(panel, fg_color="transparent")
        form_frame.grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 24))
        form_frame.grid_columnconfigure(0, weight=1)

        caps_total_value = anime["caps_totales"]
        caps_totales = str(caps_total_value) if caps_total_value is not None else "?"
        max_caps = caps_total_value
        if max_caps is None:
            try:
                q = "query($id:Int){Media(id:$id,type:ANIME){episodes nextAiringEpisode{episode}}}"
                r = requests.post("https://graphql.anilist.co", json={"query": q, "variables": {"id": anime["id_api"]}}, timeout=8)
                d = r.json()
                m = d.get("data", {}).get("Media", {})
                eps = m.get("episodes") or m.get("nextAiringEpisode", {}).get("episode")
                if eps:
                    max_caps = eps - 1 if m.get("nextAiringEpisode") and not m.get("episodes") else eps
                    caps_totales = str(max_caps)
            except Exception:
                pass
            if max_caps is None:
                max_caps = 9999
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
            fg_color="#334155",
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
        caps_input_frame = ctk.CTkFrame(saved_caps_border, fg_color="#0f172a", border_width=0, corner_radius=6)
        caps_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        caps_input_frame.grid_columnconfigure(0, weight=1)
        caps_input_frame.grid_columnconfigure(1, weight=0)

        self.saved_caps_entry = ctk.CTkEntry(
            caps_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#f1f5f9",
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
            fg_color="#0f172a",
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_saved_caps_dropdown
        )
        arrow_btn.grid(row=0, column=1, sticky="e")

        self.saved_caps_dropdown = None

        estado_label = ctk.CTkLabel(
            form_frame,
            text="Estado",
            text_color="#ffffff",
            fg_color="#334155",
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

        saved_estado_input_frame = ctk.CTkFrame(saved_estado_border, fg_color="#0f172a", border_width=0, corner_radius=6)
        saved_estado_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        saved_estado_input_frame.grid_columnconfigure(0, weight=1)
        saved_estado_input_frame.grid_columnconfigure(1, weight=0)

        self.saved_estado_entry = ctk.CTkEntry(
            saved_estado_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            justify="left"
        )
        self.saved_estado_entry.grid(row=0, column=0, sticky="ew", padx=(4, 0))
        saved_estado_value = anime.get("estado") or "Planeado"
        self.saved_estado_entry.insert(0, saved_estado_value)
        self.saved_estado_entry.configure(state="readonly")

        saved_estado_arrow_btn = ctk.CTkButton(
            saved_estado_input_frame,
            text="▼",
            width=24,
            height=42,
            fg_color="#0f172a",
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_saved_estado_dropdown
        )
        saved_estado_arrow_btn.grid(row=0, column=1, sticky="e")

        self.saved_estado_dropdown = None

        score_label = ctk.CTkLabel(
            form_frame,
            text="Score",
            text_color="#ffffff",
            fg_color="#334155",
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

        saved_score_input_frame = ctk.CTkFrame(saved_score_border, fg_color="#0f172a", border_width=0, corner_radius=6)
        saved_score_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        saved_score_input_frame.grid_columnconfigure(0, weight=1)
        saved_score_input_frame.grid_columnconfigure(1, weight=0)

        self.saved_score_entry = ctk.CTkEntry(
            saved_score_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#f1f5f9",
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
            fg_color="#0f172a",
            hover_color="#334155",
            text_color="#f1f5f9",
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
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=lambda: self._save_saved_anime_changes(anime)
        )
        save_button.grid(row=7, column=0, sticky="ew")

        self.saved_editor_panel.configure(width=430)
        self._style_scroll_background(self.saved_grid)

    def _apply_saved_highlight(self):
        target = getattr(self, "_highlighted_saved_id", None)
        if target is None:
            return
        for widget in self.saved_grid.winfo_children():
            ad = getattr(widget, "anime_data", None)
            if ad and ad.get("id") == target:
                try:
                    widget.configure(fg_color="#1e293b", border_color="#22c55e")
                except (ValueError, tk.TclError):
                    pass
                break

    def _render_saved_editor(self):
        self.update_idletasks()
        self._render_saved_page()

    def _set_saved_editor_layout(self, editor_open, rerender=True, animated=False):
        if not hasattr(self, "saved_grid") or not self.saved_grid.winfo_exists():
            return

        self.saved_editor_open = editor_open
        self.saved_columns = 2 if editor_open else 3
        self.saved_page_size = 8 if editor_open else 9

        if animated:
            self.saved_grid.configure(width=740)
            self.saved_frame.grid_columnconfigure(1, minsize=448)
        else:
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

        max_val = self.saved_caps_max if self.saved_caps_max is not None else 9999
        values = list(range(0, max_val + 1))

        if not values:
            return

        try:
            entry_x = self.saved_caps_entry.winfo_rootx()
            entry_y = self.saved_caps_entry.winfo_rooty() + self.saved_caps_entry.winfo_height()
        except tk.TclError:
            return

        dropdown_height = min(len(values) * 28, 400)

        self.saved_caps_dropdown = ctk.CTkToplevel(self)
        self.saved_caps_dropdown.overrideredirect(True)
        self.saved_caps_dropdown.attributes('-topmost', True)

        scroll_frame = ctk.CTkScrollableFrame(
            self.saved_caps_dropdown,
            width=95,
            height=dropdown_height,
            fg_color="#1e293b",
            scrollbar_button_color="#475569",
            scrollbar_button_hover_color="#64748b"
        )
        scroll_frame.pack()

        for val in values:
            btn = ctk.CTkButton(
                scroll_frame,
                text=str(val),
                width=76,
                height=28,
                fg_color="transparent",
                hover_color="#334155",
                text_color="#f1f5f9",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=val: self._select_saved_caps_value(v)
            )
            btn.pack(pady=0, padx=2)

        self.saved_caps_dropdown.geometry(f"95x{dropdown_height}+{entry_x}+{entry_y}")

        self._bind_dropdown_close(self.saved_caps_dropdown, self._close_saved_caps_dropdown)
        self._on_master_click_handler(self._close_saved_caps_dropdown)

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
            bg="#1e293b",
            highlightthickness=1,
            highlightbackground="#475569"
        )
        frame.pack(fill="both", expand=False)

        for estado in estados:
            btn = ctk.CTkButton(
                frame,
                text=estado,
                width=170,
                height=28,
                fg_color="transparent",
                hover_color="#334155",
                text_color="#f1f5f9",
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
            bg="#1e293b",
            highlightthickness=1,
            highlightbackground="#475569"
        )
        canvas.pack(fill="both", expand=False)

        frame = tk.Frame(canvas, bg="#1e293b")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        for score in scores:
            btn = ctk.CTkButton(
                frame,
                text=score,
                width=70,
                height=28,
                fg_color="transparent",
                hover_color="#334155",
                text_color="#f1f5f9",
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
        self._close_saved_editor(animated=False)
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

    def _close_saved_editor(self, reset_grid=True, animated=True):
        self._close_all_dropdowns()
        self._clear_saved_highlight()

        panel = self.saved_editor_panel

        def finish_close():
            if panel is not None:
                try:
                    if panel.winfo_exists():
                        panel.grid_forget()
                        panel.destroy()
                except tk.TclError:
                    pass

            self.saved_editor_panel = None
            self.saved_editor_open = False
            self.update_idletasks()

            if hasattr(self, "saved_grid") and self.saved_grid.winfo_exists():
                for widget in self.saved_grid.winfo_children():
                    widget.destroy()
                if reset_grid:
                    try:
                        if self.saved_grid.winfo_exists():
                            self._set_saved_editor_layout(False, rerender=True, animated=False)
                            self.update_idletasks()
                            return
                    except tk.TclError:
                        pass

            self.update_idletasks()

        if animated and reset_grid and panel is not None:
            self.saved_editor_open = False
            self.saved_columns = 3
            self.saved_page_size = 9
            self._animate_editor_transition("saved", False, finish_close)
            return

        if panel is not None:
            try:
                if panel.winfo_exists():
                    panel.grid_forget()
                    panel.destroy()
            except tk.TclError:
                pass

        self.saved_editor_panel = None
        self.saved_editor_open = False
        self.update_idletasks()

        if hasattr(self, "saved_grid") and self.saved_grid.winfo_exists():
            for widget in self.saved_grid.winfo_children():
                widget.destroy()
            if reset_grid:
                try:
                    if self.saved_grid.winfo_exists():
                        self._set_saved_editor_layout(False, rerender=True)
                        self.update_idletasks()
                        return
                except tk.TclError:
                    pass

        self.update_idletasks()

    def _clear_saved_highlight(self):
        self._highlighted_saved_id = None
        if hasattr(self, "saved_grid") and self.saved_grid.winfo_exists():
            for widget in self.saved_grid.winfo_children():
                try:
                    widget.configure(fg_color="#1e293b", border_color="#475569")
                except (ValueError, tk.TclError):
                    pass

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

    def _estado_api_label(self, status):
        labels = {
            "FINISHED": {"text": "Terminado", "color": "#0f766e"},
            "RELEASING": {"text": "En emisión", "color": "#2563eb"},
            "NOT_YET_RELEASED": {"text": "No estrenado", "color": "#7c3aed"},
            "CANCELLED": {"text": "Cancelado", "color": "#dc2626"},
            "HIATUS": {"text": "En pausa", "color": "#f59e0b"}
        }
        return labels.get(status, {"text": "Desconocido", "color": "#64748b"})
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
        self.add_frame.grid(row=0, column=0, sticky="nsew", padx=68, pady=(12, 22))
        self._attach_view_background(self.add_frame)
        self.add_frame.grid_columnconfigure(0, weight=1)
        self.add_frame.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self.add_frame, fg_color="transparent", height=74)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header_frame.grid_columnconfigure(0, weight=1, minsize=540)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_columnconfigure(2, weight=0)
        header_frame.grid_propagate(False)
        self._attach_header_background(header_frame, "Agregar anime", "Elegí uno de los animes populares para empezar a guardarlo.")

        self.search_entry = ctk.CTkEntry(
            header_frame,
            width=300,
            height=42,
            placeholder_text="Buscar anime...",
            fg_color="transparent",
            border_width=2,
            border_color="#64748b",
            text_color="#f1f5f9",
            placeholder_text_color="#94a3b8",
            font=ctk.CTkFont(family=self.font_family, size=14)
        )
        self.search_entry.grid(row=0, column=1, padx=(0, 12), pady=(14, 0))
        self.search_entry.configure(state="disabled")
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)

        filter_frame = ctk.CTkFrame(header_frame, fg_color="transparent", border_width=2, border_color="#64748b", corner_radius=6, width=154, height=46)
        filter_frame.grid(row=0, column=2, pady=(14, 0))
        filter_frame.grid_propagate(False)

        self.add_status_filter = ctk.CTkOptionMenu(
            filter_frame,
            width=150,
            height=42,
            values=["Todos", "En emisión", "Terminado", "No estrenado", "Cancelado", "En pausa"],
            fg_color="#1e293b",
            button_color="#475569",
            button_hover_color="#64748b",
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14),
            command=lambda _: self._apply_anime_filter()
        )
        self.add_status_filter.grid(row=0, column=0, padx=2, pady=2)
        self.add_status_filter.set("Todos")

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
            width=120,
            height=38,
            fg_color="#475569",
            hover_color="#64748b",
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
            command=self.show_main_view
        )
        back_button.grid(row=0, column=0, sticky="w", padx=32, pady=0)

        self._nav_prev_enabled = False
        self._nav_next_enabled = False

    def _show_anime_grid(self, animes):
        if self.current_view != "add":
            return

        self.all_anime_items = animes
        self.anime_items = animes

        if not self.anime_items:
            empty_label = ctk.CTkLabel(
                self.add_frame,
                text="No hay animes disponibles para mostrar.",
                text_color="#94a3b8",
                font=ctk.CTkFont(family=self.font_family, size=16)
            )
            empty_label.grid(row=1, column=0, sticky="n", pady=(92, 0))
            return

        self.anime_scroll = ctk.CTkScrollableFrame(
            self.add_frame,
            fg_color="#0f172a",
            width=1138,
            height=520,
            border_width=0,
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
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
        status_filter = self.add_status_filter.get()

        status_map = {
            "En emisión": "RELEASING",
            "Terminado": "FINISHED",
            "No estrenado": "NOT_YET_RELEASED",
            "Cancelado": "CANCELLED",
            "En pausa": "HIATUS"
        }
        target_status = status_map.get(status_filter)

        filtered = self.all_anime_items

        if query:
            filtered = [
                anime for anime in filtered
                if query in anime.get("title", {}).get("romaji", "").lower()
            ]

        if target_status:
            filtered = [
                anime for anime in filtered
                if anime.get("status") == target_status
            ]

        self.anime_items = filtered
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
            self._page_info_text = "Sin resultados"
            self._nav_prev_enabled = False
            self._nav_next_enabled = False
            self._redraw_bottom_text()
            return

        total_pages = self._total_anime_pages()
        start = self.anime_page * self.anime_page_size + 1
        end = min((self.anime_page + 1) * self.anime_page_size, len(self.anime_items))
        self._page_info_text = f"Pagina {self.anime_page + 1}/{total_pages} · {start}-{end} de {len(self.anime_items)}"

        self._nav_prev_enabled = self.anime_page > 0
        self._nav_next_enabled = self.anime_page < total_pages - 1
        self._redraw_bottom_text()

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
            text_color="#94a3b8",
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
            fg_color="#1e293b",
            corner_radius=8,
            border_width=2,
            border_color="#475569"
        )
        card.grid(row=row, column=column, padx=10, pady=10, sticky="n")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)

        image_label = ctk.CTkLabel(
            card,
            text="Cargando...",
            width=118,
            height=166,
            fg_color="#0f172a",
            text_color="#64748b",
            corner_radius=7,
            font=ctk.CTkFont(family=self.font_family, size=12)
        )
        image_label.grid(row=0, column=0, padx=12, pady=(12, 8))
        image_label.expected_image_url = None

        name_label = ctk.CTkLabel(
            card,
            text="",
            text_color="#f1f5f9",
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

        is_switch = self.add_editor_open or self.add_editor_panel is not None

        if is_switch:
            self._cancel_editor_animation()
            self._close_all_dropdowns()
            self._clear_add_highlight()
            old_panel = self.add_editor_panel
            self._build_add_panel(anime)
            if old_panel is not None:
                try:
                    if old_panel.winfo_exists():
                        old_panel.grid_forget()
                        old_panel.destroy()
                except tk.TclError:
                    pass
            self._apply_add_highlight()
            return

        self._close_add_panel(reset_grid=False)
        self._set_add_editor_layout(True, rerender=True, animated=True)
        self._build_add_panel(anime)
        self._animate_editor_transition("add", True)
        self._apply_add_highlight()

    def _build_add_panel(self, anime):
        for index, add_anime in enumerate(self.anime_items):
            if add_anime.get("id") == anime.get("id"):
                self.anime_page = index // self.anime_page_size
                break

        panel = ctk.CTkScrollableFrame(
            self.add_frame,
            width=430,
            height=520,
            fg_color="#1e293b",
            corner_radius=8,
            border_width=2,
            border_color="#475569",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
        )
        panel.grid(row=1, column=1, sticky="nsew", padx=(18, 0))
        panel.grid_columnconfigure(0, weight=1)
        self.add_editor_panel = panel
        self._highlighted_anime_id = anime.get("id")

        close_button = ctk.CTkButton(
            panel,
            text="Cerrar",
            width=92,
            height=34,
            fg_color="#475569",
            hover_color="#64748b",
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
            fg_color="#0f172a",
            text_color="#64748b",
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
            text_color="#f1f5f9",
            width=350,
            height=58,
            wraplength=350,
            justify="center",
            font=ctk.CTkFont(family=self.font_family, size=20, weight="bold")
        )
        title_label.grid(row=2, column=0, padx=24, pady=(0, 6))

        estado_api = self._estado_api_label(anime.get("status"))
        self.add_api_status_label = ctk.CTkLabel(
            panel,
            text=estado_api["text"],
            text_color="#ffffff",
            fg_color=estado_api["color"],
            corner_radius=7,
            width=110,
            height=26,
            font=ctk.CTkFont(family=self.font_family, size=12, weight="bold")
        )
        self.add_api_status_label.grid(row=3, column=0, pady=(0, 12))

        form_frame = ctk.CTkFrame(panel, fg_color="transparent")
        form_frame.grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 24))
        form_frame.grid_columnconfigure(0, weight=1)

        caps_total = anime.get("episodes")
        next_airing = anime.get("nextAiringEpisode")
        next_ep = next_airing.get("episode") if isinstance(next_airing, dict) else None
        caps_disponibles = (next_ep - 1) if next_ep is not None else None
        caps_total_text = str(caps_total) if caps_total is not None else (str(caps_disponibles) if caps_disponibles is not None else "?")
        max_caps = caps_total if caps_total is not None else (caps_disponibles if caps_disponibles is not None else 9999)
        self.add_caps_max = max_caps
        self.add_caps_progress_label = None
        self.add_caps_total_text = caps_total_text

        total_ep_label = ctk.CTkLabel(
            form_frame,
            text=f"Capitulos totales: {caps_total_text}",
            text_color="#ffffff",
            fg_color="#334155",
            corner_radius=7,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        total_ep_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        caps_label = ctk.CTkLabel(
            form_frame,
            text="Capitulos",
            text_color="#ffffff",
            fg_color="#334155",
            corner_radius=7,
            width=86,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        caps_label.grid(row=1, column=0, sticky="w", pady=(0, 6))

        add_caps_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        add_caps_border.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        add_caps_border.grid_columnconfigure(0, weight=1)
        add_caps_border.grid_propagate(False)

        caps_input_frame = ctk.CTkFrame(add_caps_border, fg_color="#0f172a", border_width=0, corner_radius=6)
        caps_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        caps_input_frame.grid_columnconfigure(0, weight=1)
        caps_input_frame.grid_columnconfigure(1, weight=0)

        self.add_caps_entry = ctk.CTkEntry(
            caps_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#f1f5f9",
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
            fg_color="#0f172a",
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_add_caps_dropdown
        )
        arrow_btn.grid(row=0, column=1, sticky="e")

        self.add_caps_total_value = caps_total
        self.add_caps_total_text = caps_total_text
        self.add_caps_max = max_caps
        self.add_caps_dropdown = None

        estado_label = ctk.CTkLabel(
            form_frame,
            text="Estado",
            text_color="#ffffff",
            fg_color="#334155",
            corner_radius=7,
            width=82,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        estado_label.grid(row=3, column=0, sticky="w", pady=(0, 6))

        add_estado_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        add_estado_border.grid(row=4, column=0, sticky="ew", pady=(0, 14))
        add_estado_border.grid_columnconfigure(0, weight=1)
        add_estado_border.grid_propagate(False)

        add_estado_input_frame = ctk.CTkFrame(add_estado_border, fg_color="#0f172a", border_width=0, corner_radius=6)
        add_estado_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        add_estado_input_frame.grid_columnconfigure(0, weight=1)
        add_estado_input_frame.grid_columnconfigure(1, weight=0)

        self.add_estado_entry = ctk.CTkEntry(
            add_estado_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#f1f5f9",
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
            fg_color="#0f172a",
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"),
            command=self._show_add_estado_dropdown
        )
        estado_arrow_btn.grid(row=0, column=1, sticky="e")

        self.add_estado_dropdown = None

        score_label = ctk.CTkLabel(
            form_frame,
            text="Score",
            text_color="#ffffff",
            fg_color="#334155",
            corner_radius=7,
            width=68,
            height=28,
            anchor="center",
            font=ctk.CTkFont(family=self.font_family, size=13, weight="bold")
        )
        score_label.grid(row=5, column=0, sticky="w", pady=(0, 6))

        add_score_border = tk.Frame(
            form_frame,
            height=50,
            bg="#000000",
            bd=0,
            highlightthickness=0
        )
        add_score_border.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        add_score_border.grid_columnconfigure(0, weight=1)
        add_score_border.grid_propagate(False)

        add_score_input_frame = ctk.CTkFrame(add_score_border, fg_color="#0f172a", border_width=0, corner_radius=6)
        add_score_input_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        add_score_input_frame.grid_columnconfigure(0, weight=1)
        add_score_input_frame.grid_columnconfigure(1, weight=0)

        self.add_score_entry = ctk.CTkEntry(
            add_score_input_frame,
            width=10,
            height=42,
            fg_color="transparent",
            border_width=0,
            text_color="#f1f5f9",
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
            fg_color="#0f172a",
            hover_color="#334155",
            text_color="#f1f5f9",
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
        self.add_editor_message.grid(row=7, column=0, sticky="ew", pady=(0, 10))

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
        add_button.grid(row=8, column=0, sticky="ew")


    def _apply_add_highlight(self):
        target = getattr(self, "_highlighted_anime_id", None)
        if target is None:
            return
        for slot in self.anime_card_slots:
            a = slot.get("anime")
            if a and a.get("id") == target:
                try:
                    slot["card"].configure(fg_color="#1e293b", border_color="#22c55e")
                except (ValueError, tk.TclError):
                    pass
                break

    def _set_add_editor_layout(self, editor_open, rerender=True, animated=False):
        if not hasattr(self, "anime_scroll") or not self.anime_scroll.winfo_exists():
            return

        self.add_editor_open = editor_open
        self.anime_columns = 4 if editor_open else 6
        self.anime_page_size = 32 if editor_open else 50

        if animated:
            self.anime_scroll.configure(width=740)
            self.add_frame.grid_columnconfigure(1, minsize=448)
        else:
            self.anime_scroll.configure(width=740 if editor_open else 1138)
            self.add_frame.grid_columnconfigure(1, minsize=448 if editor_open else 0)

        for column in range(6):
            weight = 1 if column < self.anime_columns else 0
            self.anime_scroll.grid_columnconfigure(column, weight=weight)

        if self.anime_page >= self._total_anime_pages():
            self.anime_page = max(0, self._total_anime_pages() - 1)

        if rerender:
            self._render_anime_page()


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

        max_val = self.add_caps_max if self.add_caps_max is not None else 9999
        values = list(range(0, max_val + 1))

        if not values:
            return

        try:
            entry_x = self.add_caps_entry.winfo_rootx()
            entry_y = self.add_caps_entry.winfo_rooty() + self.add_caps_entry.winfo_height()
        except tk.TclError:
            return

        dropdown_height = min(len(values) * 28, 400)

        self.add_caps_dropdown = ctk.CTkToplevel(self)
        self.add_caps_dropdown.overrideredirect(True)
        self.add_caps_dropdown.attributes('-topmost', True)

        scroll_frame = ctk.CTkScrollableFrame(
            self.add_caps_dropdown,
            width=95,
            height=dropdown_height,
            fg_color="#1e293b",
            scrollbar_button_color="#475569",
            scrollbar_button_hover_color="#64748b"
        )
        scroll_frame.pack()

        for val in values:
            btn = ctk.CTkButton(
                scroll_frame,
                text=str(val),
                width=76,
                height=28,
                fg_color="transparent",
                hover_color="#334155",
                text_color="#f1f5f9",
                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),
                command=lambda v=val: self._select_add_caps_value(v)
            )
            btn.pack(pady=0, padx=2)

        self.add_caps_dropdown.geometry(f"95x{dropdown_height}+{entry_x}+{entry_y}")

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
            bg="#1e293b",
            highlightthickness=1,
            highlightbackground="#475569"
        )
        canvas.pack(fill="both", expand=False)

        frame = tk.Frame(canvas, bg="#1e293b")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        for estado in estados:
            btn = ctk.CTkButton(
                frame,
                text=estado,
                width=170,
                height=28,
                fg_color="transparent",
                hover_color="#334155",
                text_color="#f1f5f9",
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
            bg="#1e293b",
            highlightthickness=1,
            highlightbackground="#475569"
        )
        canvas.pack(fill="both", expand=False)

        frame = tk.Frame(canvas, bg="#1e293b")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        for score in scores:
            btn = ctk.CTkButton(
                frame,
                text=score,
                width=70,
                height=28,
                fg_color="transparent",
                hover_color="#334155",
                text_color="#f1f5f9",
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
        caps_total = anime.get("episodes")
        if caps_total is None:
            next_airing = anime.get("nextAiringEpisode")
            next_ep = next_airing.get("episode") if isinstance(next_airing, dict) else None
            caps_totales = (next_ep - 1) if next_ep is not None else None
        else:
            caps_totales = caps_total

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

        estado_api = anime.get("status")

        agregar_anime(
            nombre,
            caps_vistos,
            caps_totales,
            estado,
            score,
            anime.get("id"),
            anime.get("coverImage", {}).get("medium"),
            estado_api
        )
        self.add_editor_message.configure(text="Anime guardado.", text_color="#0f766e")

    def _anime_already_saved(self, nombre):
        return any(anime["nombre"] == nombre for anime in obtener_animes_usuario())

    def _close_add_panel(self, reset_grid=True, animated=True):
        self._close_all_dropdowns()

        try:
            self._clear_add_highlight()
        except Exception:
            pass

        panel = self.add_editor_panel

        def finish_close():
            if panel is not None:
                try:
                    if panel.winfo_exists():
                        panel.grid_forget()
                        panel.destroy()
                except tk.TclError:
                    pass

            self.add_editor_panel = None
            self.add_editor_open = False
            self.update_idletasks()

            try:
                self._hide_all_anime_slots()
            except Exception:
                pass

            if reset_grid:
                try:
                    if hasattr(self, "anime_scroll") and self.anime_scroll.winfo_exists():
                        self._set_add_editor_layout(False, rerender=True, animated=False)
                        self.update_idletasks()
                        return
                except Exception:
                    pass

            self.update_idletasks()

        if animated and reset_grid and panel is not None:
            self.add_editor_open = False
            self.anime_columns = 6
            self.anime_page_size = 50
            self._animate_editor_transition("add", False, finish_close)
            return

        if panel is not None:
            try:
                if panel.winfo_exists():
                    panel.grid_forget()
                    panel.destroy()
            except tk.TclError:
                pass

        self.add_editor_panel = None
        self.add_editor_open = False
        self.update_idletasks()

        try:
            self._hide_all_anime_slots()
        except Exception:
            pass

        if reset_grid:
            try:
                if hasattr(self, "anime_scroll") and self.anime_scroll.winfo_exists():
                    self._set_add_editor_layout(False, rerender=True)
                    self.update_idletasks()
                    return
            except Exception:
                pass

        self.update_idletasks()

    def _clear_add_highlight(self):
        self._highlighted_anime_id = None
        for slot in getattr(self, "anime_card_slots", []):
                try:
                    slot["card"].configure(fg_color="#1e293b", border_color="#475569")
                except (ValueError, tk.TclError):
                    pass
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
            fg_color="#1e293b",
            corner_radius=8,
            border_width=2,
            border_color="#475569"
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
            text_color="#f1f5f9",
            font=ctk.CTkFont(family=self.font_family, size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="w", padx=22, pady=(22, 4))

        detail_label = ctk.CTkLabel(
            card,
            text=detail,
            text_color="#94a3b8",
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
        return card


if __name__ == "__main__":
    app = AnimeTrackerApp()
    app.mainloop()
