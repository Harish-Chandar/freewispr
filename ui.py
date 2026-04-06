"""
Tkinter-based windows for freewispr.
- FloatingIndicator : small always-on-top pill (recording / transcribing state)
- MeetingWindow     : transcript view + start/stop + AI summary
- SettingsWindow    : hotkey, model, language, API key, filler filter
"""
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path
import subprocess
import sys


BG = "#0f0f0f"
BG2 = "#1a1a1a"
ACC = "#7c5cfc"          # purple accent
ACC2 = "#5a3fd4"
FG = "#e8e8e8"
FG2 = "#888"
FONT = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 10)


def _style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("TButton", background=ACC, foreground=FG, font=FONT, relief="flat", padding=6)
    s.map("TButton", background=[("active", ACC2)])
    s.configure("Stop.TButton", background="#c0392b", foreground=FG, font=FONT, relief="flat", padding=6)
    s.map("Stop.TButton", background=[("active", "#96281b")])
    s.configure("TLabel", background=BG, foreground=FG, font=FONT)
    s.configure("Sub.TLabel", background=BG, foreground=FG2, font=("Segoe UI", 9))
    s.configure("TFrame", background=BG)
    s.configure("TEntry", fieldbackground=BG2, foreground=FG, font=FONT)
    s.configure("TCombobox", fieldbackground=BG2, foreground=FG, font=FONT)
    s.configure("TCheckbutton", background=BG, foreground=FG, font=FONT)
    s.map("TCheckbutton", background=[("active", BG)])


# --------------------------------------------------------------------------- #
#  Floating indicator pill                                                     #
# --------------------------------------------------------------------------- #

class FloatingIndicator:
    """
    Small always-on-top pill that appears during dictation/transcription.
    Shows at the top-centre of the screen with a pulsing dot.
    """

    _COLORS = {
        "listen":      "#7c5cfc",   # purple  — listening
        "transcribe":  "#f39c12",   # amber   — processing
        "done":        "#27ae60",   # green   — pasted
    }

    def __init__(self, root: tk.Tk):
        self._root = root
        self._win: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._dot: tk.Label | None = None
        self._blink_job = None
        self._state: str = "listen"

    # ------------------------------------------------------------------ public

    def show(self, message: str, state: str = "listen"):
        """Show (or update) the indicator. state: 'listen' | 'transcribe' | 'done'"""
        self._state = state
        self._root.after(0, self._show, message, state)

    def hide(self, delay_ms: int = 800):
        """Hide the indicator, optionally after a short delay."""
        self._root.after(delay_ms, self._hide)

    # ----------------------------------------------------------------- private

    def _show(self, message: str, state: str):
        color = self._COLORS.get(state, ACC)

        if self._win is None:
            self._win = tk.Toplevel(self._root)
            self._win.overrideredirect(True)          # no title bar
            self._win.attributes("-topmost", True)
            self._win.attributes("-alpha", 0.93)
            self._win.configure(bg=BG2)

            outer = tk.Frame(self._win, bg=BG2, padx=14, pady=7)
            outer.pack()

            self._dot = tk.Label(outer, text="●", bg=BG2, fg=color,
                                 font=("Segoe UI", 9))
            self._dot.pack(side="left", padx=(0, 7))

            self._label = tk.Label(outer, text=message, bg=BG2, fg=FG,
                                   font=("Segoe UI", 10))
            self._label.pack(side="left")

            # Position top-centre
            self._win.update_idletasks()
            sw = self._win.winfo_screenwidth()
            w = self._win.winfo_reqwidth()
            self._win.geometry(f"+{(sw - w) // 2}+18")
        else:
            if self._label:
                self._label.configure(text=message)
            if self._dot:
                self._dot.configure(fg=color)

        # Restart blink
        if self._blink_job:
            self._root.after_cancel(self._blink_job)
        self._blink(color)

    def _hide(self):
        if self._blink_job:
            self._root.after_cancel(self._blink_job)
            self._blink_job = None
        if self._win:
            self._win.destroy()
            self._win = None
            self._label = None
            self._dot = None

    def _blink(self, color: str):
        if self._win is None or self._dot is None:
            return
        current = self._dot.cget("fg")
        next_color = BG2 if current != BG2 else color
        self._dot.configure(fg=next_color)
        self._blink_job = self._root.after(550, self._blink, color)


# --------------------------------------------------------------------------- #
#  Meeting window                                                              #
# --------------------------------------------------------------------------- #

class MeetingWindow:
    def __init__(self, meeting_mode, config: dict, on_close=None):
        self.meeting = meeting_mode
        self.config = config
        self.on_close = on_close
        self._running = False

        self.root = tk.Toplevel()
        self.root.title("freewispr — Meeting")
        self.root.geometry("700x560")
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        _style(self.root)

        self._build()

    def _build(self):
        # Header
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=16, pady=(16, 4))
        ttk.Label(hdr, text="Meeting Transcription", font=("Segoe UI", 13, "bold")).pack(side="left")
        self._status_var = tk.StringVar(value="Ready to record")
        ttk.Label(hdr, textvariable=self._status_var, style="Sub.TLabel").pack(side="right")

        # Transcript area
        self._text = scrolledtext.ScrolledText(
            self.root, bg=BG2, fg=FG, font=FONT_MONO,
            relief="flat", borderwidth=0, wrap="word",
            insertbackground=FG,
        )
        self._text.pack(fill="both", expand=True, padx=16, pady=8)
        self._text.configure(state="disabled")

        # Controls
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", padx=16, pady=(0, 16))

        self._start_btn = ttk.Button(ctrl, text="Start Recording", command=self._toggle)
        self._start_btn.pack(side="left", padx=(0, 8))

        ttk.Button(ctrl, text="Save Transcript", command=self._save).pack(side="left", padx=(0, 8))
        ttk.Button(ctrl, text="Clear", command=self._clear).pack(side="left", padx=(0, 8))

        self._summary_btn = ttk.Button(ctrl, text="AI Summary", command=self._summarize)
        self._summary_btn.pack(side="left", padx=(0, 8))

        self._open_btn = ttk.Button(ctrl, text="Open Folder", command=self._open_folder)
        self._open_btn.pack(side="right")

    # ------------------------------------------------------------------ actions

    def _toggle(self):
        if not self._running:
            self._running = True
            self._start_btn.configure(text="Stop Recording", style="Stop.TButton")
            self.meeting.on_line = self._add_line
            self.meeting.on_status = self._set_status
            self.meeting.start()
        else:
            self._running = False
            self._start_btn.configure(text="Start Recording", style="TButton")
            path = self.meeting.stop()
            self._set_status(f"Saved → {path}" if path else "Stopped")

    def _add_line(self, line: str):
        self.root.after(0, self._insert_line, line)

    def _insert_line(self, line: str):
        self._text.configure(state="normal")
        self._text.insert("end", line + "\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def _set_status(self, msg: str):
        self.root.after(0, lambda: self._status_var.set(msg))

    def _save(self):
        transcript = self.meeting.get_transcript()
        if not transcript.strip():
            messagebox.showinfo("freewispr", "No transcript yet.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="meeting_transcript.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(transcript)
            messagebox.showinfo("freewispr", f"Saved to {path}")

    def _clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def _open_folder(self):
        folder = Path.home() / ".freewispr" / "transcripts"
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')

    # ------------------------------------------------------------------ AI summary

    def _summarize(self):
        transcript = self.meeting.get_transcript()
        if not transcript.strip():
            messagebox.showinfo("freewispr", "No transcript to summarize yet.")
            return
        api_key = self.config.get("api_key", "").strip()
        if not api_key:
            messagebox.showwarning(
                "freewispr",
                "Add your OpenAI API key in Settings to use AI summaries.",
            )
            return
        self._summary_btn.configure(state="disabled", text="Summarizing…")
        threading.Thread(
            target=self._do_summarize,
            args=(transcript, api_key),
            daemon=True,
        ).start()

    def _do_summarize(self, transcript: str, api_key: str):
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a meeting assistant. Given the transcript below, produce:\n"
                            "1. A 2-3 sentence summary\n"
                            "2. Key decisions made\n"
                            "3. Action items (bullet list with owner if mentioned)\n\n"
                            "Be concise. Use plain text, no markdown."
                        ),
                    },
                    {"role": "user", "content": f"Transcript:\n\n{transcript}"},
                ],
                max_tokens=600,
            )
            summary = resp.choices[0].message.content
            self.root.after(0, self._show_summary, summary)
        except ImportError:
            self.root.after(0, lambda: messagebox.showerror(
                "freewispr", "Install openai package:\n  pip install openai"
            ))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "freewispr", f"Summary failed:\n{e}"
            ))
        finally:
            self.root.after(0, lambda: self._summary_btn.configure(
                state="normal", text="AI Summary"
            ))

    def _show_summary(self, summary: str):
        win = tk.Toplevel(self.root)
        win.title("Meeting Summary")
        win.geometry("520x420")
        win.configure(bg=BG)
        _style(win)

        ttk.Label(win, text="AI Meeting Summary", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        txt = scrolledtext.ScrolledText(
            win, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", borderwidth=0, wrap="word",
        )
        txt.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        txt.insert("1.0", summary)
        txt.configure(state="disabled")

        def _copy():
            win.clipboard_clear()
            win.clipboard_append(summary)

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(btn_row, text="Copy", command=_copy).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="left")

    # ------------------------------------------------------------------ close

    def _on_close(self):
        if self._running:
            self._running = False
            self.meeting.stop()
        self.root.destroy()
        if self.on_close:
            self.on_close()


# --------------------------------------------------------------------------- #
#  Settings window                                                             #
# --------------------------------------------------------------------------- #

class SettingsWindow:
    def __init__(self, config: dict, on_save=None):
        self.cfg = config.copy()
        self.on_save = on_save

        self.root = tk.Toplevel()
        self.root.title("freewispr — Settings")
        self.root.geometry("440x480")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        _style(self.root)

        self._build()

    def _build(self):
        pad = {"padx": 20, "pady": 6}

        ttk.Label(self.root, text="Settings", font=("Segoe UI", 13, "bold")).pack(anchor="w", **pad)

        # Hotkey
        ttk.Label(self.root, text="Dictation hotkey").pack(anchor="w", padx=20, pady=(12, 0))
        self._hotkey_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+space"))
        ttk.Entry(self.root, textvariable=self._hotkey_var, width=30).pack(anchor="w", **pad)
        ttk.Label(self.root, text="e.g. ctrl+space, right ctrl, F9, alt+shift",
                  style="Sub.TLabel").pack(anchor="w", padx=20, pady=(0, 4))

        # Model size
        ttk.Label(self.root, text="Whisper model").pack(anchor="w", padx=20, pady=(8, 0))
        self._model_var = tk.StringVar(value=self.cfg.get("model_size", "base"))
        model_cb = ttk.Combobox(self.root, textvariable=self._model_var,
                                values=["tiny", "base", "small"], state="readonly", width=20)
        model_cb.pack(anchor="w", **pad)
        ttk.Label(self.root, text="tiny=fastest (~40MB)  base=balanced (~150MB)  small=best (~500MB)",
                  style="Sub.TLabel").pack(anchor="w", padx=20, pady=(0, 4))

        # Language
        ttk.Label(self.root, text="Language").pack(anchor="w", padx=20, pady=(8, 0))
        self._lang_var = tk.StringVar(value=self.cfg.get("language", "en"))
        ttk.Entry(self.root, textvariable=self._lang_var, width=10).pack(anchor="w", **pad)
        ttk.Label(self.root, text="ISO 639-1 code: en, es, fr, de, hi…",
                  style="Sub.TLabel").pack(anchor="w", padx=20, pady=(0, 4))

        # API key
        ttk.Label(self.root, text="OpenAI API key (for AI meeting summaries)").pack(
            anchor="w", padx=20, pady=(8, 0)
        )
        self._api_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        ttk.Entry(self.root, textvariable=self._api_var, show="*", width=40).pack(anchor="w", **pad)

        # Filler word filter
        self._filler_var = tk.BooleanVar(value=self.cfg.get("filter_fillers", False))
        ttk.Checkbutton(
            self.root,
            text='Remove filler words ("um", "uh", "you know"…) from dictation',
            variable=self._filler_var,
        ).pack(anchor="w", padx=20, pady=(12, 2))

        # Auto-detect meetings
        self._detect_var = tk.BooleanVar(value=self.cfg.get("auto_detect_meetings", True))
        ttk.Checkbutton(
            self.root,
            text="Notify when Zoom / Teams / Meet is detected",
            variable=self._detect_var,
        ).pack(anchor="w", padx=20, pady=(2, 12))

        # Save
        ttk.Button(self.root, text="Save", command=self._save).pack(anchor="e", padx=20, pady=8)

    def _save(self):
        self.cfg["hotkey"] = self._hotkey_var.get().strip()
        self.cfg["model_size"] = self._model_var.get()
        self.cfg["language"] = self._lang_var.get().strip()
        self.cfg["api_key"] = self._api_var.get().strip()
        self.cfg["filter_fillers"] = self._filler_var.get()
        self.cfg["auto_detect_meetings"] = self._detect_var.get()
        if self.on_save:
            self.on_save(self.cfg)
        self.root.destroy()
