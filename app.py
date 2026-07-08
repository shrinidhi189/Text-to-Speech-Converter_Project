"""
AI Text-to-Speech Converter - Flask backend
Uses Microsoft Edge's neural voices via the edge-tts library.

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

import asyncio
import json
import os
import uuid
from datetime import datetime

import edge_tts
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
MAX_CHARS = 3000

os.makedirs(AUDIO_DIR, exist_ok=True)

# edge-tts exposes 300+ voices across ~140 locales (edge_tts.list_voices()).
# We fetch the live catalog at startup and keep every locale that's likely
# useful, instead of hand-picking ~10. If the fetch fails (no internet at
# boot, Microsoft endpoint unreachable), we fall back to a small hardcoded
# list so the app still starts.
INCLUDED_LOCALE_PREFIXES = (
    "en-", "hi-", "ta-", "te-", "kn-", "ml-", "bn-", "mr-", "gu-", "pa-", "ur-",
    "fr-", "es-", "de-", "it-", "pt-", "ja-", "zh-", "ar-", "ru-", "ko-",
)

FALLBACK_VOICES = [
    {"id": "en-IN-NeerjaNeural", "label": "English (India) - Neerja"},
    {"id": "en-IN-PrabhatNeural", "label": "English (India) - Prabhat"},
    {"id": "en-US-JennyNeural", "label": "English (US) - Jenny"},
    {"id": "en-US-GuyNeural", "label": "English (US) - Guy"},
    {"id": "en-GB-SoniaNeural", "label": "English (UK) - Sonia"},
    {"id": "hi-IN-SwaraNeural", "label": "Hindi (India) - Swara"},
    {"id": "hi-IN-MadhurNeural", "label": "Hindi (India) - Madhur"},
]


def _locale_display_name(locale, friendly_name):
    # friendly_name looks like "Microsoft Neerja Online (Natural) - English (India)"
    # we just want the "English (India)" part after the last " - "
    if " - " in friendly_name:
        return friendly_name.rsplit(" - ", 1)[-1]
    return locale


def build_voice_catalog():
    try:
        raw_voices = asyncio.run(edge_tts.list_voices())
    except Exception:
        return list(FALLBACK_VOICES)

    catalog = []
    for v in raw_voices:
        locale = v.get("Locale", "")
        if not locale.startswith(INCLUDED_LOCALE_PREFIXES):
            continue
        short_name = v.get("ShortName")
        if not short_name:
            continue
        display_locale = _locale_display_name(locale, v.get("FriendlyName", locale))
        name = short_name.split("-")[-1].replace("Neural", "")
        gender = v.get("Gender", "")
        catalog.append({
            "id": short_name,
            "label": f"{display_locale} - {name} ({gender})",
            "locale": locale,
        })

    if not catalog:
        return list(FALLBACK_VOICES)

    catalog.sort(key=lambda v: (v["locale"], v["label"]))
    return catalog


VOICES = FALLBACK_VOICES
VOICE_LOOKUP = {v["id"]: v["label"] for v in VOICES}


# ---------------------------------------------------------------- history --
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


# ------------------------------------------------------------------ audio --
async def synthesize(text, voice, rate_percent):
    """Generate speech with edge-tts and save it to AUDIO_DIR. Returns filename."""
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    rate_str = f"{rate_percent:+d}%"  # edge-tts wants "+20%" / "-10%"
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(filepath)
    return filename


# ------------------------------------------------------------------ routes --
@app.route("/")
def index():
    from flask import render_template
    return render_template("index.html")


@app.route("/api/voices")
def get_voices():
    return jsonify(VOICES)


@app.route("/api/convert", methods=["POST"])
def convert():
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    voice = data.get("voice") or VOICES[0]["id"]
    rate = data.get("rate", 0)

    if not text:
        return jsonify({"error": "Please enter some text to convert."}), 400
    if len(text) > MAX_CHARS:
        return jsonify({"error": f"Text is too long (max {MAX_CHARS} characters)."}), 400
    if voice not in VOICE_LOOKUP:
        return jsonify({"error": "Unknown voice selected."}), 400
    try:
        rate = int(rate)
    except (TypeError, ValueError):
        rate = 0
    rate = max(-50, min(50, rate))

    try:
        filename = asyncio.run(synthesize(text, voice, rate))
    except Exception as exc:  # network / edge-tts failure
        return jsonify({"error": f"Speech generation failed: {exc}"}), 502

    entry = {
        "id": uuid.uuid4().hex,
        "text": text[:120] + ("..." if len(text) > 120 else ""),
        "voice": VOICE_LOOKUP[voice],
        "filename": filename,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    history = load_history()
    history.insert(0, entry)
    save_history(history)

    return jsonify({
        "status": "ok",
        "audio_url": f"/static/audio/{filename}",
        "entry": entry,
    })


@app.route("/api/history")
def get_history():
    return jsonify(load_history())


@app.route("/api/history/<entry_id>", methods=["DELETE"])
def delete_history(entry_id):
    history = load_history()
    entry = next((e for e in history if e["id"] == entry_id), None)
    if entry is None:
        return jsonify({"error": "Not found"}), 404

    filepath = os.path.join(AUDIO_DIR, entry["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    history = [e for e in history if e["id"] != entry_id]
    save_history(history)
    return jsonify({"status": "deleted"})


@app.route("/static/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
