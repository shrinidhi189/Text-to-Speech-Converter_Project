# AI Text-to-Speech Converter

Flask + edge-tts web app that converts typed text into speech using Microsoft
Edge's free neural voices, with playback, download, and a conversion history.

## Project structure

```
tts-app/
├── app.py                  # Flask backend + edge-tts calls
├── requirements.txt
├── templates/
│   └── index.html          # Page markup
├── static/
│   ├── css/style.css       # Light theme styling
│   ├── js/script.js        # Fetch calls, playback, history table
│   └── audio/              # Generated .mp3 files land here
└── history.json             # Auto-created; stores conversion history
```

## How it works

1. **Frontend** (`index.html` + `script.js`) collects text, a voice choice,
   and a speed value, then POSTs them to `/api/convert`.
2. **Backend** (`app.py`) calls `edge_tts.Communicate(text, voice, rate=...)`,
   which streams audio from Microsoft's Edge Read Aloud service and saves it
   as an `.mp3` under `static/audio/`.
3. The response includes the audio URL, which the browser plays immediately
   with an `<audio>` element and adds to the on-page history table.
4. History is persisted server-side in `history.json` so it survives a page
   refresh or server restart. Deleting a row removes both the JSON entry and
   the `.mp3` file.

## Run it locally

```bash
git clone https://github.com/shrinidhi189/Text-to-Speech-Converter_ML-Project
cd Text-to-Speech-Converter_ML-Project

python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. No API key is needed — `edge-tts` talks
directly to Microsoft's public Edge voice service over the internet, so you
do need an internet connection, but not an Azure account.

## Customizing voices

`VOICES` in `app.py` is a hand-picked shortlist. To see everything edge-tts
offers:

```bash
edge-tts --list-voices | grep en-
```

Add any voice ID + a friendly label to the `VOICES` list and it shows up in
the dropdown automatically.
eployment that's fine, but for anything longer-lived, add a
cleanup job (e.g. delete files older than N days) or move to cheap object
storage (S3/R2) instead of local disk.
