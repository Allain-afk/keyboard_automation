"""WASD keyboard automation.

Behavior:
- Holds each key in the sequence for 1 second.
- Waits 10 seconds before starting the next full sequence rotation.

Hotkeys:
- F8: Start/Pause key pressing
- F9: Stop and exit the program
"""

from __future__ import annotations

import argparse
import importlib.util
import threading
import time
from typing import Sequence

from pynput.keyboard import Controller as KeyboardController, Key, Listener

KEY_HOLD_SECONDS = 0.2
CYCLE_TIMEOUT_SECONDS = 10.0


class WASDAutomator:
    """Presses a configured key sequence repeatedly while running."""

    def __init__(
        self,
        sequence: Sequence[str],
        key_delay: float,
        backend: str,
        cycle_delay: float = CYCLE_TIMEOUT_SECONDS,
    ) -> None:
        self.sequence = [key.lower() for key in sequence]
        self.key_delay = key_delay
        self.cycle_delay = cycle_delay
        self.backend = backend
        self.keyboard = KeyboardController()

        self._pydirectinput = None
        if self.backend == "pydirectinput":
            import pydirectinput  # type: ignore

            pydirectinput.FAILSAFE = False
            pydirectinput.PAUSE = 0
            self._pydirectinput = pydirectinput

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
        end = time.monotonic() + duration
        while time.monotonic() < end:
            if self._stop_event.is_set() or not self.running:
                return False
            remaining = end - time.monotonic()
            time.sleep(min(0.05, max(0.0, remaining)))
        return True

    def _press_key(self, key: str) -> None:
        if self.backend == "pydirectinput" and self._pydirectinput is not None:
            self._pydirectinput.keyDown(key)
            self._wait_interruptible(KEY_HOLD_SECONDS)
            self._pydirectinput.keyUp(key)
            return

        self.keyboard.press(key)
        self._wait_interruptible(KEY_HOLD_SECONDS)
        self.keyboard.release(key)

    def run(self) -> None:
        while not self._stop_event.is_set():
            if not self.running:
                time.sleep(0.05)
                continue

            for key in self.sequence:
                if self._stop_event.is_set() or not self.running:
                    break

                self._press_key(key)
                print(f"Pressed: {key} (held 1s)")

                if self.key_delay > 0 and not self._wait_interruptible(self.key_delay):
                    break

            if self.running and not self._stop_event.is_set():
                print(f"Waiting {self.cycle_delay:g} seconds before next WASD rotation...")
                self._wait_interruptible(self.cycle_delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "WASD keyboard automation: 1 second per key, then 10 seconds between rotations."
        ),
    )
    parser.add_argument(
        "--sequence",
        nargs="+",
        default=["w", "a", "s", "d"],
        help="Keys to press in order (default: w a s d).",
    )
    parser.add_argument(
        "--key-delay",
        type=float,
        default=0.0,
        help="Delay in seconds between keys inside one rotation (default: 0.0).",
    )
    parser.add_argument(
        "--cycle-delay",
        type=float,
        default=CYCLE_TIMEOUT_SECONDS,
        help=f"Delay in seconds between rotations (default: {CYCLE_TIMEOUT_SECONDS:g}).",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "pynput", "pydirectinput"],
        default="auto",
        help=(
            "Input backend to use. 'auto' picks pydirectinput when installed, "
            "otherwise pynput (default: auto)."
        ),
    )
    parser.add_argument(
        "--startup-delay",
        type=int,
        default=3,
        help="Seconds to wait before accepting hotkeys (default: 3).",
    )
    return parser.parse_args()


def choose_backend(backend_arg: str) -> str:
    if backend_arg != "auto":
        return backend_arg
    if importlib.util.find_spec("pydirectinput") is not None:
        return "pydirectinput"
    return "pynput"


def main() -> None:
    args = parse_args()
    selected_backend = choose_backend(args.backend)

    automator = WASDAutomator(
        sequence=args.sequence,
        key_delay=args.key_delay,
        backend=selected_backend,
        cycle_delay=args.cycle_delay,
    )

    worker = threading.Thread(target=automator.run, daemon=True)
    worker.start()

    print("WASD automation is ready.")
    print("Key hold per key: 1 second.")
    print(f"Rotation timeout: {args.cycle_delay:g} seconds.")
    print("Use F8 to Start/Pause.")
    print("Use F9 to Quit.")
    print(f"Input backend: {selected_backend}")
    if selected_backend == "pynput":
        print("Tip: If Roblox ignores input, install pydirectinput and rerun.")
    print(
        f"Switch to your target window now. Listening starts in {args.startup_delay} second(s)..."
    )

    for i in range(args.startup_delay, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

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
        worker.join(timeout=1)


if __name__ == "__main__":
    main()