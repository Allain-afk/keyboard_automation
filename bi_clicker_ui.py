"""Optimized compact CustomTkinter UI for Bi-Clicker."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
except ModuleNotFoundError:  # pragma: no cover - dependency install issue
    ctk = None  # type: ignore[assignment]

from auto_clicker import (
    DEFAULT_HOTKEY,
    HOTKEY_OPTIONS,
    IDLE_UI_POLL_INTERVAL_MS,
    RUNNING_UI_POLL_INTERVAL_MS,
    WINDOW_TITLE,
    AutoClickerController,
    ClickerSettings,
    ControllerSnapshot,
    GlobalHotkeyManager,
    _parse_click_interval_ms,
    _parse_cycle_delay_seconds,
    _parse_positive_int,
    resource_path,
)

WINDOW_SIZE = "400x250"
MINI_WINDOW_SIZE = "400x145"
NORMAL_WINDOW_DIMENSIONS = (400, 250)
MINI_WINDOW_DIMENSIONS = (400, 145)

APP_BG_COLOR = "#0d1320"
PANEL_BG_COLOR = "#131d2c"
STATUS_BG_COLOR = "#101722"
TEXT_PRIMARY_COLOR = "#f3f6fb"
TEXT_MUTED_COLOR = "#90a0b8"
ACCENT_COLOR = "#4c8bf5"
START_BUTTON_COLOR = "#1f9d74"
START_BUTTON_HOVER = "#177a5a"
STOP_BUTTON_COLOR = "#cb5b63"
STOP_BUTTON_HOVER = "#a9464d"
SECONDARY_BUTTON_COLOR = "#27374d"
SECONDARY_BUTTON_HOVER = "#33455f"
FIELD_BG_COLOR = "#182334"


def create_root() -> tk.Tk:
    """Create the CustomTkinter root window."""

    if ctk is None:
        raise RuntimeError(
            "customtkinter is required. Install dependencies with `pip install -r requirements.txt`.",
        )

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    return ctk.CTk()


def _pluralize(value: int, singular: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value} {singular}{suffix}"


class AutoClickerApp:
    """Compact fixed-size CustomTkinter app for the custom auto clicker."""

    def __init__(self, root: tk.Tk, backend: str) -> None:
        self.root = root
        self.controller = AutoClickerController(backend)
        self.ui_events: queue.Queue[str] = queue.Queue()
        self.hotkey_manager = GlobalHotkeyManager(self._queue_hotkey_toggle)

        self.click_interval_var = tk.StringVar(value="500")
        self.cycle_delay_var = tk.StringVar(value="300")
        self.repeat_mode_var = tk.StringVar(value="until_stopped")
        self.repeat_basis_var = tk.StringVar(value="cycles")
        self.repeat_count_var = tk.StringVar(value="10")
        self.hotkey_var = tk.StringVar(value=DEFAULT_HOTKEY)
        self.topmost_var = tk.BooleanVar(value=False)
        self.mini_mode_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.status_counts_var = tk.StringVar(value="Clicks: 0 | Cycles: 0")
        self.mini_counter_var = tk.StringVar(value="Clicks: 0")

        self.inputs_row: ctk.CTkFrame | None = None
        self.options_row: ctk.CTkFrame | None = None
        self.fixed_repeat_row: ctk.CTkFrame | None = None
        self.controls_row: ctk.CTkFrame | None = None
        self.start_button: ctk.CTkButton | None = None
        self.stop_button: ctk.CTkButton | None = None
        self.reset_button: ctk.CTkButton | None = None
        self.click_interval_entry: ctk.CTkEntry | None = None
        self.cycle_delay_entry: ctk.CTkEntry | None = None
        self.hotkey_menu: ctk.CTkOptionMenu | None = None
        self.repeat_mode_control: ctk.CTkSegmentedButton | None = None
        self.repeat_count_entry: ctk.CTkEntry | None = None
        self.repeat_basis_menu: ctk.CTkOptionMenu | None = None
        self.mini_counter_badge: ctk.CTkLabel | None = None

        self._last_snapshot: ControllerSnapshot | None = None
        self._last_running_state: bool | None = None
        self._last_status_text = ""
        self._last_counts_text = ""
        self._last_mini_counter_text = ""

        self._configure_window()
        self._build_ui()
        self._bind_events()

        self.hotkey_manager.set_hotkey(self.hotkey_var.get())
        self._update_fixed_repeat_visibility()
        self._refresh_input_state()
        self._poll_state()

    def _configure_window(self) -> None:
        self.root.title(WINDOW_TITLE)
        self.root.configure(fg_color=APP_BG_COLOR)
        self.root.resizable(False, False)
        self._apply_window_mode(False)

        icon_path = resource_path("ACLib/playback.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

    def _apply_window_mode(self, mini_mode: bool) -> None:
        width, height = MINI_WINDOW_DIMENSIONS if mini_mode else NORMAL_WINDOW_DIMENSIONS
        self.root.minsize(width, height)
        self.root.maxsize(width, height)
        self.root.geometry(f"{width}x{height}")

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(
            self.root,
            fg_color=PANEL_BG_COLOR,
            corner_radius=14,
            border_width=0,
        )
        container.pack(fill="both", expand=True, padx=8, pady=8)
        container.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=WINDOW_TITLE,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=TEXT_PRIMARY_COLOR,
        ).grid(row=0, column=0, sticky="w")

        toggles = ctk.CTkFrame(header, fg_color="transparent")
        toggles.grid(row=0, column=1, sticky="e")
        ctk.CTkSwitch(
            toggles,
            text="Topmost",
            variable=self.topmost_var,
            command=self._on_topmost_changed,
            progress_color=ACCENT_COLOR,
            button_color=TEXT_PRIMARY_COLOR,
            button_hover_color="#dbe5f4",
            text_color=TEXT_PRIMARY_COLOR,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkSwitch(
            toggles,
            text="Mini",
            variable=self.mini_mode_var,
            command=self._toggle_mini_mode,
            progress_color=ACCENT_COLOR,
            button_color=TEXT_PRIMARY_COLOR,
            button_hover_color="#dbe5f4",
            text_color=TEXT_PRIMARY_COLOR,
        ).pack(side="left")

        self.inputs_row = ctk.CTkFrame(container, fg_color="transparent")
        self.inputs_row.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.inputs_row.grid_columnconfigure(1, weight=1)
        self.inputs_row.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(
            self.inputs_row,
            text="Interval",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.click_interval_entry = self._create_entry(self.inputs_row, self.click_interval_var, width=84)
        self.click_interval_entry.grid(row=0, column=1, sticky="ew", padx=(6, 4))
        ctk.CTkLabel(
            self.inputs_row,
            text="ms",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=2, sticky="w", padx=(0, 10))

        ctk.CTkLabel(
            self.inputs_row,
            text="Delay",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=3, sticky="w")
        self.cycle_delay_entry = self._create_entry(self.inputs_row, self.cycle_delay_var, width=84)
        self.cycle_delay_entry.grid(row=0, column=4, sticky="ew", padx=(6, 4))
        ctk.CTkLabel(
            self.inputs_row,
            text="sec",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=5, sticky="w")

        self.options_row = ctk.CTkFrame(container, fg_color="transparent")
        self.options_row.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.options_row.grid_columnconfigure(1, weight=1)
        self.options_row.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            self.options_row,
            text="Hotkey",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.hotkey_menu = ctk.CTkOptionMenu(
            self.options_row,
            values=HOTKEY_OPTIONS,
            variable=self.hotkey_var,
            command=lambda _: None,
            fg_color=SECONDARY_BUTTON_COLOR,
            button_color=ACCENT_COLOR,
            button_hover_color="#3f78d4",
            text_color=TEXT_PRIMARY_COLOR,
            dropdown_fg_color=PANEL_BG_COLOR,
            dropdown_hover_color=FIELD_BG_COLOR,
            width=96,
        )
        self.hotkey_menu.grid(row=0, column=1, sticky="w", padx=(6, 12))

        ctk.CTkLabel(
            self.options_row,
            text="Repeat",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=2, sticky="w")
        self.repeat_mode_control = ctk.CTkSegmentedButton(
            self.options_row,
            values=["Until", "Fixed"],
            command=self._on_repeat_mode_selected,
            selected_color=ACCENT_COLOR,
            selected_hover_color="#3f78d4",
            unselected_color=SECONDARY_BUTTON_COLOR,
            unselected_hover_color=SECONDARY_BUTTON_HOVER,
            text_color=TEXT_PRIMARY_COLOR,
            width=152,
        )
        self.repeat_mode_control.grid(row=0, column=3, sticky="e", padx=(6, 0))
        self.repeat_mode_control.set("Until")

        self.fixed_repeat_row = ctk.CTkFrame(container, fg_color="transparent")
        self.fixed_repeat_row.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        self.fixed_repeat_row.grid_columnconfigure(1, weight=1)
        self.fixed_repeat_row.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            self.fixed_repeat_row,
            text="Count",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.repeat_count_entry = self._create_entry(
            self.fixed_repeat_row,
            self.repeat_count_var,
            width=96,
        )
        self.repeat_count_entry.grid(row=0, column=1, sticky="w", padx=(6, 12))

        ctk.CTkLabel(
            self.fixed_repeat_row,
            text="Basis",
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=2, sticky="w")
        self.repeat_basis_menu = ctk.CTkOptionMenu(
            self.fixed_repeat_row,
            values=["cycles", "clicks"],
            variable=self.repeat_basis_var,
            command=lambda _: None,
            fg_color=SECONDARY_BUTTON_COLOR,
            button_color=ACCENT_COLOR,
            button_hover_color="#3f78d4",
            text_color=TEXT_PRIMARY_COLOR,
            dropdown_fg_color=PANEL_BG_COLOR,
            dropdown_hover_color=FIELD_BG_COLOR,
            width=128,
        )
        self.repeat_basis_menu.grid(row=0, column=3, sticky="e", padx=(6, 0))

        self.controls_row = ctk.CTkFrame(container, fg_color="transparent")
        self.controls_row.grid(row=4, column=0, sticky="ew", padx=10, pady=(6, 8))
        for column in range(3):
            self.controls_row.grid_columnconfigure(column, weight=1)

        self.start_button = ctk.CTkButton(
            self.controls_row,
            text="Start",
            command=self._start_clicked,
            fg_color=START_BUTTON_COLOR,
            hover_color=START_BUTTON_HOVER,
            text_color=TEXT_PRIMARY_COLOR,
            corner_radius=12,
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.stop_button = ctk.CTkButton(
            self.controls_row,
            text="Stop",
            command=self._stop_clicked,
            fg_color=STOP_BUTTON_COLOR,
            hover_color=STOP_BUTTON_HOVER,
            text_color=TEXT_PRIMARY_COLOR,
            corner_radius=12,
        )
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=4)

        self.reset_button = ctk.CTkButton(
            self.controls_row,
            text="Reset",
            command=self._reset_clicked,
            fg_color=SECONDARY_BUTTON_COLOR,
            hover_color=SECONDARY_BUTTON_HOVER,
            text_color=TEXT_PRIMARY_COLOR,
            corner_radius=12,
        )
        self.reset_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.mini_counter_badge = ctk.CTkLabel(
            self.controls_row,
            textvariable=self.mini_counter_var,
            fg_color=FIELD_BG_COLOR,
            corner_radius=10,
            text_color=TEXT_PRIMARY_COLOR,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.mini_counter_badge.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.mini_counter_badge.grid_remove()

        status_bar = ctk.CTkFrame(
            container,
            fg_color=STATUS_BG_COLOR,
            corner_radius=10,
            border_width=0,
        )
        status_bar.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))
        status_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            status_bar,
            textvariable=self.status_var,
            text_color=TEXT_PRIMARY_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(10, 8), pady=7)
        ctk.CTkLabel(
            status_bar,
            textvariable=self.status_counts_var,
            text_color=TEXT_MUTED_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(8, 10), pady=7)

    def _create_entry(
        self,
        parent: ctk.CTkBaseClass,
        variable: tk.StringVar,
        *,
        width: int,
    ) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent,
            textvariable=variable,
            width=width,
            fg_color=FIELD_BG_COLOR,
            border_color=SECONDARY_BUTTON_COLOR,
            text_color=TEXT_PRIMARY_COLOR,
        )

    def _bind_events(self) -> None:
        self.repeat_mode_var.trace_add("write", self._on_repeat_options_changed)
        self.repeat_basis_var.trace_add("write", self._on_repeat_options_changed)
        self.repeat_count_var.trace_add("write", self._on_repeat_options_changed)
        self.hotkey_var.trace_add("write", self._on_hotkey_changed)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_repeat_mode_selected(self, selected_value: str) -> None:
        self.repeat_mode_var.set("fixed" if selected_value == "Fixed" else "until_stopped")

    def _on_repeat_options_changed(self, *_: object) -> None:
        self._update_fixed_repeat_visibility()
        self._refresh_input_state()

    def _on_hotkey_changed(self, *_: object) -> None:
        hotkey = self.hotkey_var.get()
        try:
            self.hotkey_manager.set_hotkey(hotkey)
        except Exception as exc:  # pragma: no cover - depends on OS hook availability
            messagebox.showerror("Hotkey Error", f"Could not register {hotkey}: {exc}")

    def _on_topmost_changed(self) -> None:
        self.root.attributes("-topmost", bool(self.topmost_var.get()))

    def _toggle_mini_mode(self) -> None:
        mini_mode = bool(self.mini_mode_var.get())

        if mini_mode:
            if self.inputs_row is not None:
                self.inputs_row.grid_remove()
            if self.options_row is not None:
                self.options_row.grid_remove()
            if self.fixed_repeat_row is not None:
                self.fixed_repeat_row.grid_remove()
            if self.reset_button is not None:
                self.reset_button.grid_remove()
            if self.mini_counter_badge is not None:
                self.mini_counter_badge.grid()
        else:
            if self.inputs_row is not None:
                self.inputs_row.grid()
            if self.options_row is not None:
                self.options_row.grid()
            if self.reset_button is not None:
                self.reset_button.grid()
            if self.mini_counter_badge is not None:
                self.mini_counter_badge.grid_remove()
            self._update_fixed_repeat_visibility()

        self._apply_window_mode(mini_mode)
        self._refresh_input_state()
        self._update_display_strings(self.controller.snapshot())

    def _update_fixed_repeat_visibility(self) -> None:
        if self.fixed_repeat_row is None:
            return

        should_show = (
            self.repeat_mode_var.get() == "fixed"
            and not bool(self.mini_mode_var.get())
        )
        if should_show:
            self.fixed_repeat_row.grid()
        else:
            self.fixed_repeat_row.grid_remove()

    def _queue_hotkey_toggle(self) -> None:
        self.ui_events.put("toggle")

    def _poll_state(self) -> None:
        while True:
            try:
                action = self.ui_events.get_nowait()
            except queue.Empty:
                break

            if action == "toggle":
                self._toggle_from_hotkey()

        snapshot = self.controller.snapshot()
        self._update_display_strings(snapshot)

        if snapshot.is_running != self._last_running_state:
            if self.start_button is not None:
                self.start_button.configure(
                    state="disabled" if snapshot.is_running else "normal",
                )
            if self.stop_button is not None:
                self.stop_button.configure(
                    state="normal" if snapshot.is_running else "disabled",
                )
            if self.reset_button is not None:
                self.reset_button.configure(
                    state="disabled" if snapshot.is_running else "normal",
                )
            self._refresh_input_state(snapshot.is_running)
            self._last_running_state = snapshot.is_running

        self._last_snapshot = snapshot
        next_poll_interval = (
            RUNNING_UI_POLL_INTERVAL_MS
            if snapshot.is_running
            else IDLE_UI_POLL_INTERVAL_MS
        )
        self.root.after(next_poll_interval, self._poll_state)

    def _update_display_strings(self, snapshot: ControllerSnapshot) -> None:
        compact_status = self._compact_status_text(snapshot)
        if compact_status != self._last_status_text:
            self.status_var.set(compact_status)
            self._last_status_text = compact_status

        counts_text = self._counts_text(snapshot)
        if counts_text != self._last_counts_text:
            self.status_counts_var.set(counts_text)
            self._last_counts_text = counts_text

        mini_counter = f"Clicks: {snapshot.clicks_completed}"
        if mini_counter != self._last_mini_counter_text:
            self.mini_counter_var.set(mini_counter)
            self._last_mini_counter_text = mini_counter

    def _compact_status_text(self, snapshot: ControllerSnapshot) -> str:
        status_text = snapshot.status_text

        if status_text.startswith("Ready"):
            return "Ready"
        if status_text.startswith("Running."):
            return "Running"
        if status_text.startswith("Running click 1"):
            return "Click 1 of 2"
        if status_text.startswith("Running click 2"):
            return "Click 2 of 2"
        if status_text.startswith("Waiting between clicks"):
            return "Waiting click gap"
        if status_text.startswith("Waiting before next cycle"):
            return "Waiting cycle delay"
        if status_text.startswith("Stopping"):
            return "Stopping"
        if status_text.startswith("Stopped"):
            return "Stopped"
        if status_text.startswith("Counters reset"):
            return "Counters reset"
        if status_text.startswith("Completed"):
            if snapshot.cycles_completed:
                return f"Done: {_pluralize(snapshot.cycles_completed, 'cycle')}"
            return f"Done: {_pluralize(snapshot.clicks_completed, 'click')}"
        return status_text.split(".")[0]

    def _counts_text(self, snapshot: ControllerSnapshot) -> str:
        if self.mini_mode_var.get():
            return f"Clicks: {snapshot.clicks_completed}"
        return (
            f"Clicks: {snapshot.clicks_completed} | "
            f"Cycles: {snapshot.cycles_completed}"
        )

    def _toggle_from_hotkey(self) -> None:
        if self.controller.snapshot().is_running:
            self._stop_clicked()
            return
        self._start_clicked()

    def _start_clicked(self) -> None:
        settings = self._build_settings_from_inputs()
        if settings is None:
            return

        started, message = self.controller.start(settings)
        if not started:
            self.status_var.set(message)
            self._last_status_text = message

    def _stop_clicked(self) -> None:
        if not self.controller.stop():
            message = "Not running"
            self.status_var.set(message)
            self._last_status_text = message

    def _reset_clicked(self) -> None:
        self.controller.reset_counters()
        self._update_display_strings(self.controller.snapshot())

    def _build_settings_from_inputs(self) -> ClickerSettings | None:
        try:
            double_click_gap = _parse_click_interval_ms(self.click_interval_var.get())
            cycle_delay = _parse_cycle_delay_seconds(self.cycle_delay_var.get())
            repeat_mode = self.repeat_mode_var.get()
            repeat_basis = self.repeat_basis_var.get()
            repeat_count = 0
            if repeat_mode == "fixed":
                repeat_count = _parse_positive_int(
                    self.repeat_count_var.get(),
                    "Repeat count",
                )
        except ValueError as exc:
            messagebox.showerror("Invalid Settings", str(exc))
            return None

        return ClickerSettings(
            double_click_gap_seconds=double_click_gap,
            cycle_delay_seconds=cycle_delay,
            repeat_mode=repeat_mode,
            repeat_basis=repeat_basis,
            repeat_count=repeat_count,
            hotkey=self.hotkey_var.get(),
            backend=self.controller.backend,
        )

    def _set_widget_state(
        self,
        widget: ctk.CTkBaseClass | None,
        state: str,
    ) -> None:
        if widget is None:
            return

        try:
            current_state = widget.cget("state")
        except (tk.TclError, ValueError, AttributeError):
            current_state = None

        if current_state != state:
            widget.configure(state=state)

    def _refresh_input_state(self, is_running: bool | None = None) -> None:
        snapshot_running = (
            self.controller.snapshot().is_running
            if is_running is None
            else is_running
        )
        fixed_enabled = self.repeat_mode_var.get() == "fixed" and not snapshot_running
        input_state = "disabled" if snapshot_running else "normal"

        for widget in (
            self.click_interval_entry,
            self.cycle_delay_entry,
            self.hotkey_menu,
            self.repeat_mode_control,
        ):
            self._set_widget_state(widget, input_state)

        self._set_widget_state(
            self.repeat_count_entry,
            "normal" if fixed_enabled else "disabled",
        )
        self._set_widget_state(
            self.repeat_basis_menu,
            "normal" if fixed_enabled else "disabled",
        )

    def _on_close(self) -> None:
        self.hotkey_manager.stop()
        self.controller.shutdown()
        self.root.destroy()
