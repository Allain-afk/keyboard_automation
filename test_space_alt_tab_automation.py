from pathlib import Path
import subprocess
import sys
import threading
import unittest

from space_alt_tab_automation import SpaceAltTabAutomator


class RecordingAutomator(SpaceAltTabAutomator):
    def __init__(self) -> None:
        self.actions = []
        self.running = True
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def _press_space(self) -> None:
        self.actions.append("space")

    def _switch_window(self) -> None:
        self.actions.append("alt_tab")

    def _wait_interruptible(self, duration: float) -> bool:
        self.actions.append(("wait", duration))
        return True


class SpaceAltTabAutomatorTests(unittest.TestCase):
    def test_script_uses_project_environment_when_launcher_lacks_dependencies(self) -> None:
        script_path = Path(__file__).with_name("space_alt_tab_automation.py")
        base_python = Path(sys.base_prefix) / "python.exe"
        command = (
            "import runpy; "
            f"runpy.run_path({str(script_path)!r}, run_name='startup_check'); "
            "print('startup ok')"
        )

        result = subprocess.run(
            [str(base_python), "-S", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("startup ok", result.stdout)

    def test_cycle_pauses_between_each_keyboard_action(self) -> None:
        automator = RecordingAutomator()

        completed = automator._run_cycle()

        self.assertTrue(completed)
        self.assertEqual(
            automator.actions,
            [
                "space",
                ("wait", 1.0),
                "alt_tab",
                ("wait", 1.0),
                "space",
                ("wait", 1.0),
                "alt_tab",
            ],
        )


if __name__ == "__main__":
    unittest.main()
