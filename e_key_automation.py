"""Lightweight automation that holds the E key once every three seconds.

Hotkeys:
- F8: Start/pause automation
- F9: Stop and exit
"""

from __future__ import annotations

import threading
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key, Listener

KEY = "e"
KEY_HOLD_SECONDS = 1.5
CYCLE_DELAY_SECONDS = 3.0


class EKeyAutomator:
    """Press and hold E repeatedly without a busy-wait loop."""

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

    def _wait_interruptible(self, duration: float) -> bool:
        end_time = time.monotonic() + duration
        while not self._stop_event.is_set() and time.monotonic() < end_time:
            with self._lock:
                if not self.running:
                    return False
            remaining = end_time - time.monotonic()
            self._stop_event.wait(timeout=min(0.1, max(0.0, remaining)))
        return not self._stop_event.is_set()

    def _press_and_hold(self) -> bool:
        self.keyboard.press(KEY)
        try:
            return self._wait_interruptible(KEY_HOLD_SECONDS)
        finally:
            self.keyboard.release(KEY)

    def run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                running = self.running

            if not running:
                self._stop_event.wait(timeout=0.1)
                continue

            if not self._press_and_hold():
                continue

            print(f"Pressed and held '{KEY}' for {KEY_HOLD_SECONDS:g} seconds.")
            self._wait_interruptible(CYCLE_DELAY_SECONDS)


def main() -> None:
    automator = EKeyAutomator()
    worker = threading.Thread(target=automator.run, daemon=True)
    worker.start()

    print("E-key automation is ready.")
    print(f"Hold duration: {KEY_HOLD_SECONDS:g} seconds.")
    print(f"Delay between presses: {CYCLE_DELAY_SECONDS:g} seconds.")
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
