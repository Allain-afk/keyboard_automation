"""Send Space to every open Roblox client window in a stable rotation."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import site
import threading
import time
from typing import Protocol


def _add_project_dependencies() -> None:
    site_packages = Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"
    if site_packages.is_dir():
        site.addsitedir(str(site_packages))


_add_project_dependencies()

import pydirectinput
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key, Listener


WINDOW_SETTLE_SECONDS = 1.0
ACTION_DELAY_SECONDS = 1.0
SPACE_DELAY_SECONDS = 10.0
SPACE_HOLD_SECONDS = 0.1
POLL_INTERVAL_SECONDS = 0.05
FOCUS_RETRY_SECONDS = 0.1
FOCUS_ATTEMPTS = 3

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9

pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0


def is_roblox_client_identity(executable_name: str, class_name: str) -> bool:
    """Return whether Win32 process/class metadata identifies a Roblox client."""
    return executable_name.casefold() in {
        "robloxplayerbeta.exe",
        "windows10universal.exe",
    } or class_name.casefold() == "windowsclient"


class WindowManager(Protocol):
    def find_roblox_windows(self) -> list[int]: ...

    def activate(self, window_handle: int) -> bool: ...

    def is_active(self, window_handle: int) -> bool: ...


class WindowsRobloxWindowManager:
    """Discover and focus Roblox top-level windows through the Win32 API."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("This automation requires Windows.")
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.keyboard = KeyboardController()
        self._enum_callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        self._configure_api_signatures()

    def _configure_api_signatures(self) -> None:
        self.user32.EnumWindows.argtypes = [
            self._enum_callback_type,
            wintypes.LPARAM,
        ]
        self.user32.EnumWindows.restype = wintypes.BOOL
        self.user32.GetClassNameW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user32.GetClassNameW.restype = ctypes.c_int
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.IsIconic.argtypes = [wintypes.HWND]
        self.user32.IsIconic.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL
        self.user32.BringWindowToTop.argtypes = [wintypes.HWND]
        self.user32.BringWindowToTop.restype = wintypes.BOOL
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def _window_class_name(self, window_handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(window_handle, buffer, len(buffer))
        return buffer.value

    def _window_executable_name(self, window_handle: int) -> str:
        process_id = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(
            window_handle, ctypes.byref(process_id)
        )
        process_handle = self.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value
        )
        if not process_handle:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if not self.kernel32.QueryFullProcessImageNameW(
                process_handle, 0, buffer, ctypes.byref(size)
            ):
                return ""
            return Path(buffer.value).name
        finally:
            self.kernel32.CloseHandle(process_handle)

    def find_roblox_windows(self) -> list[int]:
        window_handles: list[int] = []

        def collect(window_handle: int, _extra: int) -> bool:
            if not self.user32.IsWindowVisible(window_handle):
                return True
            executable_name = self._window_executable_name(window_handle)
            class_name = self._window_class_name(window_handle)
            if is_roblox_client_identity(executable_name, class_name):
                window_handles.append(int(window_handle))
            return True

        callback = self._enum_callback_type(collect)
        self.user32.EnumWindows(callback, 0)
        return window_handles

    def is_active(self, window_handle: int) -> bool:
        return bool(self.user32.IsWindow(window_handle)) and (
            self.user32.GetForegroundWindow() == window_handle
        )

    def activate(self, window_handle: int) -> bool:
        if not self.user32.IsWindow(window_handle):
            return False
        if self.user32.IsIconic(window_handle):
            self.user32.ShowWindow(window_handle, SW_RESTORE)

        for _attempt in range(FOCUS_ATTEMPTS):
            # A synthetic Alt release helps Windows permit a foreground change.
            self.keyboard.press(Key.alt)
            self.keyboard.release(Key.alt)
            self.user32.BringWindowToTop(window_handle)
            self.user32.SetForegroundWindow(window_handle)
            if self.user32.GetForegroundWindow() == window_handle:
                return True
            time.sleep(FOCUS_RETRY_SECONDS)
        return False


class RobloxMultiWindowAutomator:
    """Press Space once in every discovered Roblox window per cycle."""

    def __init__(self, window_manager: WindowManager) -> None:
        self.window_manager = window_manager
        self.running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._window_order: list[int] = []

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
        pydirectinput.keyDown("space")
        try:
            time.sleep(SPACE_HOLD_SECONDS)
        finally:
            pydirectinput.keyUp("space")

    def _refresh_window_order(self) -> list[int]:
        discovered = self.window_manager.find_roblox_windows()
        discovered_set = set(discovered)
        retained = [handle for handle in self._window_order if handle in discovered_set]
        retained_set = set(retained)
        self._window_order = retained + [
            handle for handle in discovered if handle not in retained_set
        ]
        return self._window_order.copy()

    def _run_cycle(self) -> bool:
        window_handles = self._refresh_window_order()
        for index, window_handle in enumerate(window_handles):
            if not self.window_manager.activate(window_handle):
                print(f"Skipped Roblox window {window_handle}: could not focus it.")
                continue
            if not self._wait_interruptible(WINDOW_SETTLE_SECONDS):
                return False
            if not self.window_manager.is_active(window_handle):
                if not self.window_manager.activate(window_handle):
                    print(
                        f"Skipped Roblox window {window_handle}: "
                        "it lost focus before Space was sent."
                    )
                    continue
                if not self._wait_interruptible(WINDOW_SETTLE_SECONDS):
                    return False
                if not self.window_manager.is_active(window_handle):
                    print(
                        f"Skipped Roblox window {window_handle}: "
                        "it lost focus again before Space was sent."
                    )
                    continue
            self._press_space()
            print(f"Pressed Space in Roblox window {window_handle}.")
            if index < len(window_handles) - 1:
                if not self._wait_interruptible(ACTION_DELAY_SECONDS):
                    return False
        return not self._stop_event.is_set() and self._is_running()

    def run(self) -> None:
        while not self._stop_event.is_set():
            if not self._is_running():
                self._stop_event.wait(timeout=POLL_INTERVAL_SECONDS)
                continue

            if not self._run_cycle():
                continue
            if not self._window_order:
                print("No Roblox windows found. Retrying after the cycle delay.")
            else:
                print(
                    f"Completed {len(self._window_order)} Roblox window(s). "
                    f"Waiting {SPACE_DELAY_SECONDS:g} seconds..."
                )
            self._wait_interruptible(SPACE_DELAY_SECONDS)


def main() -> None:
    automator = RobloxMultiWindowAutomator(WindowsRobloxWindowManager())
    worker = threading.Thread(target=automator.run, daemon=True)
    worker.start()

    print("Multi-window Roblox Space automation is ready.")
    print("Each cycle refreshes all open Roblox client windows.")
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
