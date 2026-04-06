"""
freewispr — Windows speech-to-text
Entry point: system tray icon + dictation/meeting modes.
"""
import sys
import time
import threading
import tkinter as tk

from PIL import Image, ImageDraw
import pystray

import config as cfg_module
from transcriber import Transcriber
from dictation import DictationMode
from meeting import MeetingMode
from ui import MeetingWindow, SettingsWindow, FloatingIndicator, _style, BG

# --------------------------------------------------------------------------- #
#  Globals                                                                     #
# --------------------------------------------------------------------------- #

_config: dict = {}
_transcriber: Transcriber | None = None
_dictation: DictationMode | None = None
_meeting: MeetingMode | None = None
_tray_icon: pystray.Icon | None = None
_tk_root: tk.Tk | None = None
_meeting_win: MeetingWindow | None = None
_status_var: tk.StringVar | None = None
_indicator: FloatingIndicator | None = None


# --------------------------------------------------------------------------- #
#  Tray icon image (drawn with Pillow — no external asset needed)             #
# --------------------------------------------------------------------------- #

def _make_icon() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Purple circle
    draw.ellipse([4, 4, size - 4, size - 4], fill="#7c5cfc")
    # White mic body
    cx = size // 2
    draw.rounded_rectangle([cx - 9, 12, cx + 9, 36], radius=9, fill="white")
    # Mic stand
    draw.arc([cx - 16, 26, cx + 16, 50], start=0, end=180, fill="white", width=3)
    draw.line([cx, 50, cx, 58], fill="white", width=3)
    draw.line([cx - 8, 58, cx + 8, 58], fill="white", width=3)
    return img


# --------------------------------------------------------------------------- #
#  App init                                                                    #
# --------------------------------------------------------------------------- #

def _load_app():
    global _config, _transcriber, _dictation, _meeting, _status_var

    _config = cfg_module.load()

    model_size = _config.get("model_size", "base")
    print(f"Loading Whisper '{model_size}' model...", flush=True)
    _set_tray_status("Loading model…")
    _transcriber = Transcriber(
        model_size=model_size,
        language=_config.get("language", "en"),
        filter_fillers=_config.get("filter_fillers", False),
    )
    print("Model loaded! App is ready.", flush=True)

    _meeting = MeetingMode(_transcriber)
    _dictation = DictationMode(
        _transcriber,
        hotkey=_config.get("hotkey", "ctrl+space"),
        on_status=_set_tray_status,
        indicator=_indicator,
    )
    _dictation.start()
    _set_tray_status(f"Ready — hold {_config.get('hotkey','ctrl+space').upper()} to speak")

    # Start meeting app watcher
    if _config.get("auto_detect_meetings", True):
        threading.Thread(target=_meeting_watcher, daemon=True).start()


# --------------------------------------------------------------------------- #
#  Status helpers                                                              #
# --------------------------------------------------------------------------- #

def _set_tray_status(msg: str):
    if _tray_icon:
        _tray_icon.title = f"freewispr — {msg}"
    if _status_var and _tk_root:
        _tk_root.after(0, lambda: _status_var.set(msg))


# --------------------------------------------------------------------------- #
#  Meeting app auto-detection                                                  #
# --------------------------------------------------------------------------- #

_MEETING_PROCS = {
    "zoom": "Zoom",
    "teams": "Microsoft Teams",
    "webex": "Webex",
    "slack": "Slack",
    "skype": "Skype",
    "googlemeet": "Google Meet",
    "meet": "Google Meet",
}


def _detect_meeting_app() -> str | None:
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            name = proc.info["name"].lower()
            for key, display in _MEETING_PROCS.items():
                if key in name:
                    return display
    except Exception:
        pass
    return None


def _meeting_watcher():
    """Periodically check for meeting apps and notify via tray balloon."""
    notified_for: str | None = None
    while True:
        time.sleep(30)
        # Don't notify if already recording
        if _meeting and _meeting._active:
            notified_for = None
            continue
        app = _detect_meeting_app()
        if app and app != notified_for:
            notified_for = app
            if _tray_icon:
                try:
                    _tray_icon.notify(
                        f"{app} detected — open Meeting Transcription to record.",
                        "freewispr",
                    )
                except Exception:
                    pass  # notify() may not be available on all setups
        elif not app:
            notified_for = None


# --------------------------------------------------------------------------- #
#  Tray menu callbacks                                                         #
# --------------------------------------------------------------------------- #

def _open_meeting(_=None):
    global _meeting_win
    if _tk_root:
        _tk_root.after(0, _show_meeting)


def _show_meeting():
    global _meeting_win
    if _meeting_win is not None:
        try:
            _meeting_win.root.lift()
            return
        except tk.TclError:
            _meeting_win = None
    _meeting_win = MeetingWindow(_meeting, config=_config, on_close=lambda: None)


def _open_settings(_=None):
    if _tk_root:
        _tk_root.after(0, _show_settings)


def _show_settings():
    SettingsWindow(_config, on_save=_apply_settings)


def _apply_settings(new_cfg: dict):
    global _config, _dictation, _transcriber
    _config.update(new_cfg)
    cfg_module.save(_config)

    # Rebuild transcriber if filler setting changed
    if _transcriber:
        _transcriber.filter_fillers = _config.get("filter_fillers", False)

    # Restart dictation with new hotkey
    if _dictation:
        _dictation.stop()
    _dictation = DictationMode(
        _transcriber,
        hotkey=_config.get("hotkey", "ctrl+space"),
        on_status=_set_tray_status,
        indicator=_indicator,
    )
    _dictation.start()
    _set_tray_status(f"Settings saved — hold {_config.get('hotkey','ctrl+space').upper()} to speak")


def _is_startup_enabled() -> bool:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run")
        winreg.QueryValueEx(key, "freewispr")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _toggle_startup(_=None):
    import winreg
    vbs = r"C:\Users\prakh\AI Experiments\freewispr\launch.vbs"
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                         0, winreg.KEY_SET_VALUE)
    if _is_startup_enabled():
        winreg.DeleteValue(key, "freewispr")
        _set_tray_status("Removed from startup")
    else:
        winreg.SetValueEx(key, "freewispr", 0, winreg.REG_SZ, f'wscript.exe "{vbs}"')
        _set_tray_status("Will start with Windows ✓")
    winreg.CloseKey(key)
    _rebuild_menu()


def _rebuild_menu():
    if _tray_icon:
        _tray_icon.menu = _build_menu()


def _build_menu():
    startup_label = "✓ Start with Windows" if _is_startup_enabled() else "Start with Windows"
    return pystray.Menu(
        pystray.MenuItem("Meeting Transcription", _open_meeting),
        pystray.MenuItem("Settings", _open_settings),
        pystray.MenuItem(startup_label, _toggle_startup),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit freewispr", _quit),
    )


def _quit(_=None):
    if _dictation:
        _dictation.stop()
    if _tray_icon:
        _tray_icon.stop()
    if _tk_root:
        _tk_root.quit()
        _tk_root.destroy()
    sys.exit(0)


# --------------------------------------------------------------------------- #
#  Main                                                                        #
# --------------------------------------------------------------------------- #

def main():
    global _tray_icon, _tk_root, _status_var, _indicator

    # Hidden tk root — keeps tkinter event loop running for Toplevel windows
    _tk_root = tk.Tk()
    _tk_root.withdraw()
    _style(_tk_root)

    _status_var = tk.StringVar(value="Starting…")
    _indicator = FloatingIndicator(_tk_root)

    # Build tray icon
    menu = _build_menu()
    _tray_icon = pystray.Icon(
        "freewispr",
        _make_icon(),
        "freewispr — Starting…",
        menu,
    )

    # Load model in background so the tray appears immediately
    threading.Thread(target=_load_app, daemon=True).start()

    # Run tray in a background thread; tkinter runs on main thread
    tray_thread = threading.Thread(target=_tray_icon.run, daemon=True)
    tray_thread.start()

    # tkinter main loop (needed for Toplevel windows + FloatingIndicator)
    _tk_root.mainloop()


if __name__ == "__main__":
    main()
