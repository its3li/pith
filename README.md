<p align="center">
  <img src="pith.png" alt="Pith icon" width="120" height="120">
</p>

<h1 align="center">Pith</h1>

<p align="center">
  <strong>Lightweight Windows dictation that records your voice, transcribes it, and pastes the text into the active app.</strong>
</p>

<p align="center">
  <em>Say it however it comes out. What lands in the text field is the pith.</em>
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Speech to text" src="https://img.shields.io/badge/STT-Groq_Whisper-F55036?style=for-the-badge">
  <img alt="Build" src="https://img.shields.io/badge/build-PyInstaller-2E3440?style=for-the-badge">
  <img alt="Config" src="https://img.shields.io/badge/config-.env_required-EAB308?style=for-the-badge">
</p>

<p align="center">
  <a href="https://github.com/its3li/pith/releases/latest"><strong>Download latest release</strong></a>
  ·
  <a href="#quick-start-for-the-exe"><strong>Quick start</strong></a>
  ·
  <a href="#troubleshooting"><strong>Troubleshooting</strong></a>
</p>

---

## What it does

Pith runs quietly in the Windows tray. Press the dictation hotkey, speak, stop recording, and the transcription is pasted into the app you were using.

```text
Press hotkey → Speak → Stop recording → Cleanup pass → Text gets pasted
```

The cleanup pass is what makes the output read like writing rather than a recording. It strips fillers and applies spoken self-corrections, so this:

> so um I bought the phone for ten dollars, no actually I bought it for twenty

is pasted as:

> I bought the phone for twenty.

It never rewrites, translates, or summarises — it only removes what you retracted. Turn it off with `PITH_FIX=0` to paste the raw verbatim transcript instead.

That is where the name comes from: pith is the substance left when the waffle is gone.

---

## The overlay

<p align="center">
  <img src="overlay-states.png" alt="The Pith overlay in each of its states" width="820">
</p>

A frameless card you can drag anywhere. The dot's colour is the state, the meter
follows your voice while recording and holds its shape when paused, and a sweep
runs across it while a request is in flight. `Ctrl + Shift + P` shows and hides it;
it costs no CPU when nothing is moving.

---

## Visual overview

| Area | What you get |
| --- | --- |
| 🎙️ Dictation | Global voice recording with `Ctrl + Shift + Space` |
| 📝 Transcription | Groq `whisper-large-v3`, falling back to `whisper-large-v3-turbo` |
| ✨ Cleanup | Fillers and false starts removed, spoken self-corrections applied |
| 📋 Paste behavior | Pastes into the active window or copies to clipboard if focus changed |
| 🕘 History | Last few transcripts stay in the tray menu, click to re-copy |
| 🪟 Overlay | Small floating control panel for status, pause, and cancel |
| 🧭 Tray app | Runs in the system tray with show/hide and quit controls |
| 🎨 Icon | Uses `pith.ico` for the tray and the exe, `pith.png` for this page |

---

## Controls

| Action | Shortcut / control |
| --- | --- |
| Start recording | `Ctrl + Shift + Space` |
| Stop and transcribe | `Ctrl + Shift + Space` or `Enter` |
| Cancel recording | `Esc`, or the overlay stop button |
| Show / hide overlay | `Ctrl + Shift + P` |
| Pause / resume | Overlay pause button |
| Move the overlay | Drag it anywhere |
| Re-copy a recent transcript | Tray menu → Recent transcripts |
| Quit | System tray menu |

`Esc` and `Enter` are captured only while a recording is running, and suppressed
while they are, so they stop the dictation without also reaching the app
underneath. At any other time both keys behave completely normally. Set
`PITH_STOP_ON_ENTER=0` if you would rather `Enter` never stopped a
recording at all.

---

## Requirements

| Requirement | Needed for |
| --- | --- |
| Windows 10/11 | The app uses Windows tray, hotkeys, and paste behavior |
| Working microphone | Audio capture |
| Groq API key | Transcription and transcript cleanup |
| Python 3.10+ | Only needed when running from source |


---

## Quick start for the exe

Download the release exe from:

https://github.com/its3li/pith/releases/latest

Then keep these files together in the same folder:

```text
Pith-V2.0.exe
.env
```

> The download is named `Pith-V2.0.exe`. If you build it yourself with `build_exe.bat`
> instead, you get `dist\Pith.exe` — same app, and either name works as long as `.env`
> sits beside it.

> [!IMPORTANT]
> The `.env` file must be next to the `.exe`. If `.env` is missing or in another folder, transcription will fail with `GROQ_API_KEY is not set`.

Create `.env` from the config template attached to the same release
(`env-example.txt`, listed under the exe):

```powershell
copy env-example.txt .env
```

Then edit `.env` and add your real API key from [console.groq.com/keys](https://console.groq.com/keys):

```env
GROQ_API_KEY=your_api_key_here
```

Run the exe:

```powershell
.\Pith-V2.0.exe
```

---

## Quick install from source

1. Clone or download this folder.
2. Copy `.env.example` to `.env`.
3. Put your API key in `.env`.
4. Run setup.
5. Start the app.

```powershell
copy .env.example .env
.\setup.bat
.\.venv\Scripts\python.exe pith.py
```

---

## Manual source install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\python.exe pith.py
```

---

## Build a standalone exe

Run:

```powershell
.\build_exe.bat
```

The executable is created at:

```text
dist\Pith.exe
```

The build uses this icon:

```text
pith.ico
```

> [!NOTE]
> `build_exe.bat` does **not** copy your `.env` into `dist\`. Place it beside `dist\Pith.exe` yourself, so a real key never ends up in a folder you might zip and publish.

---

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest
```

The suite covers silence trimming, upload encoding, the model fallback chains, and the cleanup pass. It needs neither a microphone nor an API key.

---

## Start automatically with Windows

After building the exe:

```powershell
.\install_startup.bat
```

That creates this shortcut:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Pith.lnk
```

To remove auto-start:

```powershell
.\uninstall_startup.bat
```

---

## Configuration

Create a `.env` file from `.env.example`. Only the API key is required; every other
value below is the default.

| Variable | Default | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | **required** | Your Groq API key |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint |
| `PITH_STT_MODEL` | `whisper-large-v3` | Primary transcription model |
| `PITH_STT_FALLBACK` | `whisper-large-v3-turbo` | Used on rate limits, outages, and timeouts |
| `PITH_LANGUAGE` | blank (auto-detect) | Spoken language; `ar` forces Arabic, `en` forces English |
| `PITH_FIX` | `1` | Enable the transcript cleanup pass |
| `PITH_FIX_MODEL` | `qwen/qwen3.8-27b` | Primary cleanup model |
| `PITH_FIX_FALLBACK` | `qwen/qwen3.6-27b` | Cleanup fallback |
| `PITH_FIX_MIN_WORDS` | `4` | Skip cleanup below this word count |
| `PITH_FIX_TIMEOUT` | `4.0` | Seconds before pasting the raw transcript instead |
| `PITH_STOP_ON_ENTER` | `1` | Also stop recording on `Enter` |
| `PITH_KEEP_CLIPBOARD` | `1` | Restore your previous clipboard after pasting |
| `PITH_CLIPBOARD_RESTORE_MS` | `250` | Delay before that restore |
| `PITH_LEADING_SPACE` | `0` | Prepend a space, for dictating onto half-typed text |
| `PITH_HISTORY_SIZE` | `5` | Transcripts kept in the tray menu |
| `PITH_SILENCE_THRESHOLD` | `500` | Higher trims silence more aggressively |
| `PITH_TRIM_PADDING_MS` | `250` | Speech padding kept around detected audio |
| `PITH_FLAC_THRESHOLD_KB` | `600` | Above this, upload FLAC instead of WAV |
| `PITH_MAX_SECONDS` | `600` | Hard cap on a single recording |
| `PITH_REQUEST_TIMEOUT` | `60` | Seconds to wait for a transcription |

Minimal example:

```env
GROQ_API_KEY=your_api_key_here
```

> [!NOTE]
> **Upgrading from PollenScribe v1.0:** the app is called Pith now, and settings use
> the `PITH_` prefix. Your old `POLLENSCRIBE_` variables are still read as a fallback,
> so an existing `.env` keeps working — only the key itself must change:
> `POLLINATIONS_API_KEY` and `POLLINATIONS_BASE_URL` are gone, replaced by
> `GROQ_API_KEY` and `GROQ_BASE_URL`. If you were overriding the old
> `POLLENSCRIBE_MODEL`, the setting is now `PITH_STT_MODEL`.

---

## Privacy

Your audio is uploaded to Groq for transcription. With the cleanup pass enabled — it
is on by default — the resulting transcript is then sent to Groq a second time, as
text, to be cleaned up.

Set `PITH_FIX=0` to keep that second request from happening, or point
`GROQ_BASE_URL` at any other OpenAI-compatible endpoint, including a local one.

Nothing is written to disk: audio is held in memory and discarded after the
transcription returns. Recent transcripts live in memory only, for the tray menu,
and go away when you quit.

---

## Troubleshooting

### `GROQ_API_KEY is not set`

Check that:

- `.env` exists.
- `.env` is in the same folder as the running exe.
- `.env` contains `GROQ_API_KEY=...`.
- The key line is not commented out.
- You are not still using the old `POLLINATIONS_API_KEY` name.

### Hotkeys do not work

Try:

- Run Pith as Administrator.
- Close any app using the same hotkey.
- Restart Pith after permission changes.

### Microphone capture fails

Check:

- Windows microphone privacy permissions.
- Default input device.
- Microphone mute state.
- Whether another app is exclusively using the microphone.

### Transcription fails

Check:

- API key is valid.
- Internet connection is working.
- `GROQ_BASE_URL` is correct.
- Audio was actually recorded. Silence is detected before upload and reported as
  `No speech detected` rather than sent.

### `Enter` sends my half-typed message

This was fixed. The old build registered `Enter` globally and without suppression, so
the keypress stopped the recording *and* passed through to the app underneath. `Enter`
is now bound only for the duration of a recording and suppressed while it is bound, so
it stops the dictation and goes no further. Set `PITH_STOP_ON_ENTER=0` to
disable the key entirely.

### `Enter` does nothing while I am recording

Check that `PITH_STOP_ON_ENTER` is not set to `0` in your `.env`. It defaults
to on; `Ctrl + Shift + Space` always works as the stop key regardless.

### The pasted text is not what I said

The cleanup pass removes fillers and applies self-corrections by design. Set
`PITH_FIX=0` for the raw verbatim transcript.

### Icon looks wrong after rebuilding

Check:

- `pith.ico` exists in the repo root.
- You rebuilt after adding the icon.
- You are running the newly built exe, not an older one.
- Windows icon cache may still show the old icon temporarily.

---

## Security notes

> [!WARNING]
> Never publish your real `.env` file or API key.

Safe to publish:

```text
.env.example
```

Do not publish:

```text
.env
```

If a real API key was exposed, rotate it before publishing another release.

---

## Project files

| File | Purpose |
| --- | --- |
| `pith.py` | Entry point shim, so the batch files keep working |
| `pith/config.py` | Every tunable, read from `.env` into one frozen dataclass |
| `pith/audio.py` | Capture, silence trimming, WAV/FLAC encoding |
| `pith/groq_client.py` | Transcription, cleanup, and the model fallback chains |
| `pith/paste.py` | Foreground-window checks and clipboard save/restore |
| `pith/ui.py` | Tray icon and the floating overlay |
| `pith/status.py` | Thread-safe status plumbing and transcript history |
| `pith/app.py` | Hotkeys, recording state, and the dictation pipeline |
| `tests/` | Unit tests that need no microphone or API key |
| `pith.ico` | App and tray icon, bundled into the exe |
| `pith.png` | The same icon in a format GitHub renders, for this README |
| `build_exe.bat` | Builds the standalone exe |
| `setup.bat` | Creates/install source environment |
| `install_startup.bat` | Adds Windows startup shortcut |
| `uninstall_startup.bat` | Removes Windows startup shortcut |
| `.env.example` | Safe config template |

---

<p align="center">
  <strong>Remember:</strong> the exe and `.env` must stay together.
</p>
