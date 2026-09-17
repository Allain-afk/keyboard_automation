"""Core controller and entrypoint for Bi-Clicker."""

from __future__ import annotations

import argparse
import importlib.util
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pynput.keyboard import GlobalHotKeys
from pynput.mouse import Button, Controller as MouseController

HOTKEY_OPTIONS = [f"F{i}" for i in range(1, 13)]
DEFAULT_HOTKEY = "F6"
IDLE_UI_POLL_INTERVAL_MS = 1000
RUNNING_UI_POLL_INTERVAL_MS = 450
WINDOW_TITLE = "Bi-Clicker"


@dataclass(frozen=True)
class ClickerSettings:
    """Runtime settings for one clicking session."""

    double_click_gap_seconds: float
    cycle_delay_seconds: float
    repeat_mode: str
    repeat_basis: str
    repeat_count: int
    hotkey: str
    backend: str


@dataclass(frozen=True)
class ControllerSnapshot:
    """Thread-safe view of the controller state."""

    is_running: bool
    status_text: str
    clicks_completed: int
    cycles_completed: int
    backend: str


def resource_path(relative_path: str) -> Path:
    """Resolve resources from source or from a PyInstaller bundle."""

    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / relative_path


def choose_backend(backend_arg: str) -> str:
    """Choose the best available click backend."""

    if backend_arg != "auto":
        return backend_arg
    if importlib.util.find_spec("pydirectinput") is not None:
        return "pydirectinput"
    return "pynput"


def format_duration(seconds: float) -> str:
    """Render a compact duration label for the UI."""

    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if whole_seconds:
        parts.append(f"{whole_seconds}s")
    if milliseconds or not parts:
        parts.append(f"{milliseconds}ms")
    return " ".join(parts)


class AutoClickerController:
    """Runs the click loop on a worker thread."""

    def __init__(
        self,
        backend: str,
        click_executor: Callable[[], None] | None = None,
    ) -> None:
        self.backend = backend
        self._click_executor = click_executor
        self._mouse = MouseController() if click_executor is None else None

        self._pydirectinput = None
        if click_executor is None and self.backend == "pydirectinput":
            import pydirectinput  # type: ignore

            pydirectinput.FAILSAFE = False
            pydirectinput.PAUSE = 0
            self._pydirectinput = pydirectinput

        self._state_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._status_text = "Ready. Press Start or the selected hotkey."
        self._clicks_completed = 0
        self._cycles_completed = 0

    def snapshot(self) -> ControllerSnapshot:
        """Return a thread-safe snapshot for the UI."""

        with self._state_lock:
            running = self._worker is not None and self._worker.is_alive()
            return ControllerSnapshot(
                is_running=running,
                status_text=self._status_text,
                clicks_completed=self._clicks_completed,
                cycles_completed=self._cycles_completed,
                backend=self.backend,
            )

    def start(self, settings: ClickerSettings) -> tuple[bool, str]:
        """Start a new clicking session if the worker is idle."""

        with self._state_lock:
            worker_running = self._worker is not None and self._worker.is_alive()
            if worker_running:
                return False, "The auto clicker is already running."

            self._clicks_completed = 0
            self._cycles_completed = 0
            self._status_text = (
                f"Running. Toggle with {settings.hotkey}. "
                f"Double-click gap: {format_duration(settings.double_click_gap_seconds)}."
            )
            stop_event = threading.Event()
            worker = threading.Thread(
                target=self._run_click_loop,
                args=(settings, stop_event),
                daemon=True,
            )
            self._stop_event = stop_event
            self._worker = worker

        worker.start()
        return True, "Started."

    def stop(self) -> bool:
        """Request the current worker to stop."""

        with self._state_lock:
            worker_running = self._worker is not None and self._worker.is_alive()
            stop_event = self._stop_event
            if not worker_running or stop_event is None:
                return False
            self._status_text = "Stopping..."

        stop_event.set()
        return True

    def shutdown(self) -> None:
        """Stop the worker and wait briefly for it to exit."""

        self.stop()
        worker: threading.Thread | None
        with self._state_lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout=1.0)

    def reset_counters(self) -> None:
        """Reset the visible counters while idle."""

        with self._state_lock:
            worker_running = self._worker is not None and self._worker.is_alive()
            if worker_running:
                return
            self._clicks_completed = 0
            self._cycles_completed = 0
            self._status_text = "Counters reset. Press Start or the selected hotkey."

    def _run_click_loop(
        self,
        settings: ClickerSettings,
        stop_event: threading.Event,
    ) -> None:
        final_status = "Stopped."

        try:
            while not stop_event.is_set():
                self._set_status("Running click 1 of 2...")
                self._click_once()
                clicks_completed = self._increment_clicks()
                if self._target_reached(settings, clicks_completed, 0):
                    final_status = self._completed_message(settings, clicks_completed, 0)
                    break

                self._set_status(
                    "Waiting between clicks "
                    f"({format_duration(settings.double_click_gap_seconds)})..."
                )
                if not self._wait_interruptible(
                    settings.double_click_gap_seconds,
                    stop_event,
                ):
                    break

                self._set_status("Running click 2 of 2...")
                self._click_once()
                clicks_completed = self._increment_clicks()
                cycles_completed = self._increment_cycles()

                if self._target_reached(settings, clicks_completed, cycles_completed):
                    final_status = self._completed_message(
                        settings,
                        clicks_completed,
                        cycles_completed,
                    )
                    break

                self._set_status(
                    "Waiting before next cycle "
                    f"({format_duration(settings.cycle_delay_seconds)})..."
                )
                if not self._wait_interruptible(settings.cycle_delay_seconds, stop_event):
                    break
        finally:
            self._finish_run(final_status)

    def _target_reached(
        self,
        settings: ClickerSettings,
        clicks_completed: int,
        cycles_completed: int,
    ) -> bool:
        if settings.repeat_mode != "fixed":
            return False
        if settings.repeat_basis == "clicks":
            return clicks_completed >= settings.repeat_count
        return cycles_completed >= settings.repeat_count

    def _completed_message(
        self,
        settings: ClickerSettings,
        clicks_completed: int,
        cycles_completed: int,
    ) -> str:
        if settings.repeat_basis == "clicks":
            return (
                f"Completed {clicks_completed} click(s) "
                f"across {cycles_completed} full cycle(s)."
            )
        return (
            f"Completed {cycles_completed} cycle(s) "
            f"for {clicks_completed} total click(s)."
        )

    def _finish_run(self, final_status: str) -> None:
        with self._state_lock:
            self._status_text = final_status
            self._stop_event = None
            self._worker = None

    def _set_status(self, status_text: str) -> None:
        with self._state_lock:
            self._status_text = status_text

    def _increment_clicks(self) -> int:
        with self._state_lock:
            self._clicks_completed += 1
            return self._clicks_completed

    def _increment_cycles(self) -> int:
        with self._state_lock:
            self._cycles_completed += 1
            return self._cycles_completed

    def _wait_interruptible(
        self,
        duration: float,
        stop_event: threading.Event,
    ) -> bool:
        if duration <= 0:
            return not stop_event.is_set()
        return not stop_event.wait(timeout=duration)

    def _click_once(self) -> None:
        if self._click_executor is not None:
            self._click_executor()
            return

        if self.backend == "pydirectinput" and self._pydirectinput is not None:
            self._pydirectinput.click(button="left")
            return

        if self._mouse is None:
            raise RuntimeError("Mouse controller is not initialized.")
        self._mouse.click(Button.left, 1)


class GlobalHotkeyManager:
    """Registers and swaps one global toggle hotkey."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._listener_lock = threading.Lock()
        self._listener: GlobalHotKeys | None = None
        self._hotkey = ""

    def set_hotkey(self, hotkey: str) -> None:
        listener = GlobalHotKeys({f"<{hotkey.lower()}>": self._callback})

        with self._listener_lock:
            previous_listener = self._listener
            previous_hotkey = self._hotkey

        if previous_listener is not None:
            previous_listener.stop()
            previous_listener.join(timeout=1.0)

        try:
            listener.start()
        except Exception:
            if previous_listener is not None and previous_hotkey:
                previous_listener = GlobalHotKeys(
                    {f"<{previous_hotkey.lower()}>": self._callback},
                )
                previous_listener.start()
                with self._listener_lock:
                    self._listener = previous_listener
                    self._hotkey = previous_hotkey
            raise

        with self._listener_lock:
            self._listener = listener
            self._hotkey = hotkey

    def stop(self) -> None:
        with self._listener_lock:
            listener = self._listener
            self._listener = None
            self._hotkey = ""

        if listener is not None:
            listener.stop()
            listener.join(timeout=1.0)


def _parse_non_negative_int(raw_value: str, label: str) -> int:
    value_text = raw_value.strip()
    if value_text == "":
        raise ValueError(f"{label} cannot be blank.")
    try:
        value = int(value_text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a whole number.") from exc
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def _parse_positive_int(raw_value: str, label: str) -> int:
    value = _parse_non_negative_int(raw_value, label)
    if value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return value


def _parse_non_negative_float(raw_value: str, label: str) -> float:
    value_text = raw_value.strip()
    if value_text == "":
        raise ValueError(f"{label} cannot be blank.")
    try:
        value = float(value_text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def _parse_click_interval_ms(raw_value: str) -> float:
    return _parse_non_negative_int(raw_value, "Click Interval (ms)") / 1000


def _parse_cycle_delay_seconds(raw_value: str) -> float:
    return _parse_non_negative_float(raw_value, "Cycle Delay (sec)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Custom auto clicker desktop app.")
    parser.add_argument(
        "--backend",
        choices=["auto", "pynput", "pydirectinput"],
        default="auto",
        help=(
            "Input backend to use. 'auto' picks pydirectinput when installed, "
            "otherwise pynput."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_backend = choose_backend(args.backend)

    from bi_clicker_ui import AutoClickerApp, create_root

    root = create_root()
    AutoClickerApp(root, selected_backend)
    root.mainloop()


if __name__ == "__main__":
    main()
