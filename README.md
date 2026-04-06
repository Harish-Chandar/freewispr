# freewispr

<p align="center">
  <strong>Free, local speech-to-text for Windows. No cloud. No subscription.</strong><br>
  Dictate anywhere. Transcribe meetings. 100% on-device via Whisper AI.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
  <img src="https://img.shields.io/badge/python-3.10%2B-yellow" />
  <img src="https://img.shields.io/badge/model-Whisper%20(local)-purple" />
</p>

---

## What is freewispr?

freewispr is a lightweight Windows app that puts speech-to-text at your fingertips — no account, no internet, no cost. Hold a hotkey to dictate into any app, or open Meeting Transcription to capture everything said in a call (mic + system audio) with timestamps.

All audio is processed locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Nothing leaves your PC.

---

## Features

### Dictation
Hold `Ctrl+Space` → speak → release. The transcribed text is instantly pasted at your cursor — works in any app (browser, Word, Notepad, Slack, etc.).

### Meeting Transcription
Start a meeting recording from the system tray. freewispr captures your **microphone and system audio simultaneously** (via WASAPI loopback), transcribes in real time, and writes a timestamped transcript file.

```
[00:00] Welcome everyone, let's get started.
[00:08] Can you share your screen?
[00:14] Sure, give me a second.
```

### Fully Local
Powered by Whisper AI running entirely on your CPU with INT8 quantization. The model (~150 MB for `base`) downloads automatically on first launch to `~/.freewispr/models/`. After that, works offline.

### System Tray
Lives quietly in your system tray. Right-click for Meeting Transcription, Settings, and Start with Windows toggle.

### Configurable
- Change the dictation hotkey (e.g. `right ctrl`, `F9`, `alt+shift`)
- Switch Whisper model: `tiny` (fastest) → `base` (balanced) → `small` (most accurate)
- Set language (ISO code: `en`, `es`, `fr`, `de`, `hi`, etc.)
- Optional OpenAI API key for future summary features

---

## Install

### Download (recommended)

Download the latest `freewispr.exe` from [Releases](https://github.com/prakharsingh-74/freewispr/releases).

- No installation required. Just double-click and run.
- Windows 10/11 only.
- On first launch, the Whisper `base` model (~150 MB) downloads automatically.

### First-time setup

1. Run `freewispr.exe` — a purple mic icon appears in the system tray.
2. Hold `Ctrl+Space` and speak. Release to paste.
3. Right-click the tray icon → **Meeting Transcription** to start a meeting session.
4. Optionally: right-click → **Start with Windows** to auto-launch on login.

---

## Build from Source

**Requirements:** Python 3.10+, Windows 10/11

```bash
# Clone
git clone https://github.com/prakharsingh-74/freewispr.git
cd freewispr

# Install dependencies
pip install -r requirements.txt

# Run directly
python main.py

# Or build a standalone .exe
build.bat
```

The built `.exe` lands in `dist/freewispr.exe`.

### Dependencies

| Package | Purpose |
|---|---|
| `faster-whisper` | Whisper AI inference (CPU, INT8) |
| `sounddevice` | Mic recording + WASAPI loopback |
| `numpy` | Audio processing |
| `keyboard` | Global hotkey detection |
| `pyperclip` + `pyautogui` | Clipboard paste |
| `pystray` | Windows system tray |
| `Pillow` | Tray icon generation |

---

## Models

freewispr uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with INT8 quantization for CPU efficiency.

| Model | Size | Speed | Accuracy | Languages |
|---|---|---|---|---|
| `tiny` | ~40 MB | Fastest | Good | 99 |
| `base` | ~150 MB | Fast | Better | 99 |
| `small` | ~500 MB | Slower | Best (CPU) | 99 |

**Default:** `base` — best balance of speed and accuracy for everyday use.

Models download from HuggingFace on first use. Change via Settings in the tray menu.

---

## How It Works

```
Mic (16 kHz) ──┐
               ├──► Mix & Normalize ──► faster-whisper (CPU/INT8) ──► Text ──► Paste / Transcript
System Audio ──┘    (numpy)              VAD + beam search
(WASAPI loopback,
 resampled to 16 kHz)
```

**Dictation flow:**
1. `keyboard` detects hotkey press/release globally
2. `sounddevice` streams mic audio at 16 kHz
3. On release, audio is sent to `faster-whisper` with VAD filtering
4. Result is copied to clipboard and `Ctrl+V` is simulated via `pyautogui`

**Meeting flow:**
1. Two `sounddevice` streams open: mic (16 kHz) + WASAPI loopback (native SR)
2. System audio is resampled to 16 kHz via linear interpolation
3. Streams are mixed (mic × 0.6 + system × 0.8) and normalized
4. Every 20 seconds, the chunk is sent to Whisper with `time_offset` for accurate timestamps
5. Transcript lines are appended live to `~/.freewispr/transcripts/meeting_YYYYMMDD_HHMMSS.txt`
6. Falls back to mic-only if WASAPI loopback is unavailable

---

## Architecture

```
freewispr/
├── main.py          # Entry point: tray icon, threading, app lifecycle
├── dictation.py     # DictationMode: hotkey → record → transcribe → paste
├── meeting.py       # MeetingMode: continuous record → chunk → transcribe → log
├── audio.py         # MicRecorder, MeetingRecorder (WASAPI loopback + mixing)
├── transcriber.py   # Whisper wrapper (faster-whisper, VAD, segments)
├── paste.py         # Clipboard paste via pyperclip + pyautogui
├── ui.py            # Tkinter windows: MeetingWindow, SettingsWindow
├── config.py        # JSON config (~/.freewispr/config.json)
├── make_icon.py     # Generates assets/icon.ico programmatically
├── build.bat        # PyInstaller build script
└── docs/            # Website (deployed on Vercel)
```

---

## Data & Privacy

- **No telemetry.** No analytics. No network requests (except model download on first launch).
- Audio is never saved during dictation — it's processed in memory and discarded.
- Meeting transcripts are saved locally to `~/.freewispr/transcripts/`.
- Config is stored at `~/.freewispr/config.json`.

---

## Roadmap

- [ ] AI meeting summaries (local LLM or optional API)
- [ ] Floating recording indicator widget
- [ ] Speaker diarization
- [ ] Word replacement / custom vocabulary
- [ ] Dark/light theme toggle in UI
- [ ] Installer (NSIS or WiX)

---

## Contributing

Pull requests welcome. Open an issue first for larger changes.

```bash
git clone https://github.com/prakharsingh-74/freewispr.git
cd freewispr
pip install -r requirements.txt
python main.py   # run from source
```

---

## License

[MIT](LICENSE) — free and open source.

---

<p align="center">
  Built by <a href="https://www.linkedin.com/in/prakharsingh96/">Prakhar Singh</a> •
  <a href="https://www.instagram.com/prakhar.vc/">Instagram</a>
</p>
