# Keyboard Automation

A few small Windows automation scripts for clicking and key presses.

## Included
- `auto_clicker.py` / `bi_clicker_ui.py` — auto clicker for repeated mouse clicks
- `wasd_automation.py` — loops a WASD key sequence
- `e_key_automation.py` — presses and holds the `E` key on a timer
- `space_alt_tab_automation.py` - sends Space while alternating between two windows
- `roblox_multi_window_automation.py` - sends Space to every open Roblox client window

## Run
```bash
pip install -r requirements.txt
python auto_clicker.py
python wasd_automation.py
python e_key_automation.py
python roblox_multi_window_automation.py
```

## Notes
- Use the hotkeys in each script to start, pause, or stop.
- `F8` and `F9` are commonly used for the keyboard automations.
- The multi-window Roblox script refreshes its window list each cycle, uses
  direct window activation instead of Alt+Tab, and supports three or more clients.
- For the clicker, the UI includes the main controls and hotkey setup.
