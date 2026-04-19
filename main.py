from __future__ import annotations

"""freewispr — Windows speech-to-text entry point."""
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any

from PIL import Image, ImageDraw
import pystray

import config as cfg_module
from transcriber import Transcriber
from dictation import DictationMode
from ui import SettingsWindow, SnippetsWindow, DictionaryWindow, FloatingIndicator, _style
from error_log import log_error

_config: dict = {}
_transcriber: Transcriber | None = None
_dictation: DictationMode | None = None
_tray_icon: Any | None = None
_tk_root: tk.Tk | None = None
_status_var: tk.StringVar | None = None
_indicator: FloatingIndicator | None = None
_settings_window: SettingsWindow | None = None


def _make_icon() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Simple mic icon for the tray.
    draw.ellipse([4, 4, size - 4, size - 4], fill="#7c5cfc")
    cx = size // 2
    draw.rounded_rectangle([cx - 9, 12, cx + 9, 36], radius=9, fill="white")
    draw.arc([cx - 16, 26, cx + 16, 50], start=0, end=180, fill="white", width=3)
    draw.line([cx, 50, cx, 58], fill="white", width=3)
    draw.line([cx - 8, 58, cx + 8, 58], fill="white", width=3)
    return img


def _load_app():
    global _config, _transcriber, _dictation
    try:
        _config = cfg_module.load()

        model_size = _config.get("model_size", "base")
        print(f"Loading Whisper '{model_size}' model...", flush=True)
        _set_tray_status("Loading model…")
        _transcriber = Transcriber(
            model_size=model_size,
            language=_config.get("language", "en"),
            filter_fillers=_config.get("filter_fillers", False),
            auto_punctuate=_config.get("auto_punctuate", True),
        )
        print("Model loaded! App is ready.", flush=True)

        _dictation = DictationMode(
            _transcriber,
            hotkey=_config.get("hotkey", "ctrl+space"),
            on_status=_set_tray_status,
            indicator=_indicator,
            on_mic_error=_handle_mic_error,
            on_transcribe_error=_handle_transcribe_error,
        )
        _dictation.start()
        _set_tray_status(f"Ready — hold {_config.get('hotkey','ctrl+space').upper()} to speak")

        import sys
        if getattr(sys, 'frozen', False) and not _is_startup_enabled():
            try:
                _enable_startup()
                _rebuild_menu()
            except Exception as e:
                log_error("startup.auto_enable", e)
    except Exception as e:
        log_error("app.load", e)
        _set_tray_status("Startup failed — check error log")

        if _tk_root:
            _tk_root.after(
                0,
                lambda: messagebox.showerror(
                    "freewispr — Startup Error",
                    "freewispr failed to initialize. Check ~/.freewispr/logs/error.log for details.",
                ),
            )


def _set_tray_status(msg: str):
    if _tray_icon:
        _tray_icon.title = f"freewispr — {msg}"
    if _status_var and _tk_root:
        _tk_root.after(0, lambda: _status_var.set(msg))


def _configure_global_error_logging():
    def _log_unhandled(exc_type, exc_value, exc_tb):
        if exc_value is None:
            return
        log_error("unhandled.main_thread", exc_value)

    def _log_thread_exception(args):
        if args.exc_value is None:
            return
        log_error(
            "unhandled.thread",
            args.exc_value,
            details=f"thread={args.thread.name if args.thread else 'unknown'}",
        )

    sys.excepthook = _log_unhandled
    threading.excepthook = _log_thread_exception


def _open_snippets(_=None):
    if _tk_root:
        _tk_root.after(0, lambda: SnippetsWindow())


def _open_dictionary(_=None):
    if _tk_root:
        _tk_root.after(0, lambda: DictionaryWindow())


def _open_settings(_=None):
    if _tk_root:
        _tk_root.after(0, _show_settings)


def _show_settings():
    global _settings_window

    if _settings_window and _settings_window.root.winfo_exists():
        _settings_window.root.lift()
        _settings_window.root.focus_force()
        return _settings_window

    _settings_window = SettingsWindow(_config, on_save=_apply_settings)

    def _on_destroy(event):
        global _settings_window
        if _settings_window and event.widget == _settings_window.root:
            _settings_window = None

    _settings_window.root.bind("<Destroy>", _on_destroy, add="+")
    return _settings_window


def _handle_mic_error(message: str):
    if not _tk_root:
        return

    log_error("mic.error", details=message)

    def _show():
        settings = _show_settings()
        messagebox.showerror(
            "freewispr — Microphone Error",
            f"freewispr could not access your microphone.\n\n{message}",
            parent=settings.root if settings else None,
        )

    _tk_root.after(0, _show)


def _handle_transcribe_error(message: str):
    if not _tk_root:
        return

    log_error("transcribe.error", details=message)

    def _show():
        messagebox.showerror(
            "freewispr — Transcription Error",
            f"freewispr could not transcribe the captured audio.\n\n{message}",
        )

    _tk_root.after(0, _show)


def _apply_settings(new_cfg: dict):
    global _config, _dictation, _transcriber
    _config.update(new_cfg)
    cfg_module.save(_config)

    if _transcriber:
        _transcriber.filter_fillers = _config.get("filter_fillers", False)
        _transcriber.auto_punctuate = _config.get("auto_punctuate", True)

    if _dictation:
        _dictation.stop()
    _dictation = DictationMode(
        _transcriber,
        hotkey=_config.get("hotkey", "ctrl+space"),
        on_status=_set_tray_status,
        indicator=_indicator,
        on_mic_error=_handle_mic_error,
        on_transcribe_error=_handle_transcribe_error,
    )
    _dictation.start()
    _set_tray_status(f"Settings saved — hold {_config.get('hotkey','ctrl+space').upper()} to speak")


def _startup_exe_path() -> str:
    """Return the command to register for startup."""
    import sys
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    else:
        vbs = r"C:\Users\haris\Side-Projects\freewispr\launch.vbs"
        return f'wscript.exe "{vbs}"'


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


def _enable_startup():
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                         0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, "freewispr", 0, winreg.REG_SZ, _startup_exe_path())
    winreg.CloseKey(key)


def _toggle_startup(_=None):
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                         0, winreg.KEY_SET_VALUE)
    if _is_startup_enabled():
        winreg.DeleteValue(key, "freewispr")
        _set_tray_status("Removed from startup")
    else:
        winreg.SetValueEx(key, "freewispr", 0, winreg.REG_SZ, _startup_exe_path())
        _set_tray_status("Will start with Windows ✓")
    winreg.CloseKey(key)
    _rebuild_menu()


def _rebuild_menu():
    if _tray_icon:
        _tray_icon.menu = _build_menu()


def _build_menu():
    startup_label = "✓ Start with Windows" if _is_startup_enabled() else "Start with Windows"
    return pystray.Menu(
        pystray.MenuItem("Snippets", _open_snippets),
        pystray.MenuItem("Personal Dictionary", _open_dictionary),
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


def main():
    global _tray_icon, _tk_root, _status_var, _indicator

    _configure_global_error_logging()

    _tk_root = tk.Tk()
    _tk_root.withdraw()
    _style(_tk_root)

    _status_var = tk.StringVar(value="Starting…")
    _indicator = FloatingIndicator(_tk_root)

    menu = _build_menu()
    _tray_icon = pystray.Icon(
        "freewispr",
        _make_icon(),
        "freewispr — Starting…",
        menu,
    )

    threading.Thread(target=_load_app, daemon=True).start()

    tray_thread = threading.Thread(target=_tray_icon.run, daemon=True)
    tray_thread.start()

    _tk_root.mainloop()


if __name__ == "__main__":
    main()
