"""Repeat Space and Alt+Tab actions with F8/F9 controls.

Hotkeys:
- F8: Start/pause automation
- F9: Stop and exit
"""

from __future__ import annotations

import threading
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key, Listener

SPACE_DELAY_SECONDS = 10.0
POLL_INTERVAL_SECONDS = 0.05


class SpaceAltTabAutomator:
    """Press Space in each alternating window and repeat while running."""

    def __init__(self) -> None:
        self.keyboard = KeyboardController()
        self.running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def toggle(self) -> None:
        with self._lock:
            self.running = not self.running
            status = "RUNNING" if self.running else "PAUSED"
        print(f"[Status] {status}")

    def stop(self) -> None:
        self._stop_event.set()

    def _is_running(self) -> bool:
        with self._lock:
            return self.running

    def _wait_interruptible(self, duration: float) -> bool:
        end_time = time.monotonic() + duration
        while not self._stop_event.is_set() and time.monotonic() < end_time:
            if not self._is_running():
                return False
            remaining = end_time - time.monotonic()
            self._stop_event.wait(timeout=min(POLL_INTERVAL_SECONDS, remaining))
        return not self._stop_event.is_set() and self._is_running()

    def _press_space(self) -> None:
        self.keyboard.press(Key.space)
        self.keyboard.release(Key.space)

    def _switch_window(self) -> None:
        self.keyboard.press(Key.alt)
        try:
            self.keyboard.press(Key.tab)
            self.keyboard.release(Key.tab)
        finally:
            self.keyboard.release(Key.alt)

    def _run_cycle(self) -> bool:
        self._press_space()
        print("Pressed Space in the current window.")

        self._switch_window()
        if not self._is_running() or self._stop_event.is_set():
            return False

        self._press_space()
        print("Pressed Space after switching windows.")

        self._switch_window()
        return not self._stop_event.is_set() and self._is_running()

    def run(self) -> None:
        while not self._stop_event.is_set():
            if not self._is_running():
                self._stop_event.wait(timeout=POLL_INTERVAL_SECONDS)
                continue

            if self._run_cycle():
                print(f"Waiting {SPACE_DELAY_SECONDS:g} seconds before the next cycle...")
                self._wait_interruptible(SPACE_DELAY_SECONDS)


def main() -> None:
    automator = SpaceAltTabAutomator()
    worker = threading.Thread(target=automator.run, daemon=True)
    worker.start()

    print("Space + Alt+Tab automation is ready.")
    print(f"Delay between cycles: {SPACE_DELAY_SECONDS:g} seconds.")
    print("Use F8 to start/pause and F9 to quit.")

    def on_press(key: Key) -> bool | None:
        if key == Key.f8:
            automator.toggle()
        elif key == Key.f9:
            print("Stopping automation and exiting...")
            automator.stop()
            return False
        return None

    listener = Listener(on_press=on_press)
    listener.start()

    try:
        listener.join()
    except KeyboardInterrupt:
        automator.stop()
    finally:
        automator.stop()
        worker.join(timeout=1.0)


if __name__ == "__main__":
    main()