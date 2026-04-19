import threading
import time
import keyboard
import pyperclip
import pyautogui


_MODIFIER_KEYS = (
    "ctrl", "left ctrl", "right ctrl",
    "alt", "left alt", "right alt", "alt gr",
    "shift", "left shift", "right shift",
    "windows", "left windows", "right windows",
)


def _any_modifier_pressed() -> bool:
    for key in _MODIFIER_KEYS:
        try:
            if keyboard.is_pressed(key):
                return True
        except Exception:
            continue
    return False


def _wait_for_modifiers_release(max_wait: float = 0.2, poll_interval: float = 0.01):
    deadline = time.perf_counter() + max_wait
    while time.perf_counter() < deadline:
        if not _any_modifier_pressed():
            return
        time.sleep(poll_interval)


def _restore_clipboard_later(old_value: str, delay: float = 0.12):
    time.sleep(delay)
    try:
        pyperclip.copy(old_value)
    except Exception:
        pass


def paste_text(text: str):
    """Copy text to the clipboard and paste it at the current cursor."""
    text = text.strip()
    if not text:
        return

    try:
        old = pyperclip.paste()
    except Exception:
        old = ""

    pyperclip.copy(text + " ")
    _wait_for_modifiers_release()
    pyautogui.hotkey("ctrl", "v")

    threading.Thread(target=_restore_clipboard_later, args=(old,), daemon=True).start()
