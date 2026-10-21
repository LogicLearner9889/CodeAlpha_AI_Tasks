"""Language Translation Tool - Flask backend.

The browser talks only to this server. The server talks to the translation API,
so your API key is never exposed in front-end code.
"""
import logging
import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("translator")

PROVIDER = os.getenv("TRANSLATION_PROVIDER", "mymemory").lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
REQUEST_TIMEOUT = 15  # seconds
MAX_CHARS = 5000 if PROVIDER == "google" else 500

LANGUAGES = {
    "af": "Afrikaans", "ar": "Arabic", "bn": "Bengali", "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)", "cs": "Czech", "da": "Danish", "nl": "Dutch",
    "en": "English", "fi": "Finnish", "fr": "French", "de": "German", "el": "Greek",
    "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian",
    "it": "Italian", "ja": "Japanese", "kn": "Kannada", "ko": "Korean", "ml": "Malayalam",
    "mr": "Marathi", "ne": "Nepali", "no": "Norwegian", "fa": "Persian", "pl": "Polish",
    "pt": "Portuguese", "pa": "Punjabi", "ro": "Romanian", "ru": "Russian", "es": "Spanish",
    "sv": "Swedish", "ta": "Tamil", "te": "Telugu", "th": "Thai", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "vi": "Vietnamese",
}


class TranslationError(Exception):
    """An error with a user-friendly message and an HTTP status code."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.message = message
        self.status = status


def translate_google(text, source, target):
    if not GOOGLE_API_KEY or GOOGLE_API_KEY.startswith("your-"):
        raise TranslationError("Server is missing GOOGLE_API_KEY. Add it to your .env file.", 500)

    payload = {"q": text, "target": target, "format": "text", "key": GOOGLE_API_KEY}
    if source != "auto":
        payload["source"] = source

    resp = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        data=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        log.error("Google API error %s: %s", resp.status_code, detail)
        if resp.status_code in (400, 403):
            raise TranslationError(f"Google rejected the request: {detail or 'check your API key and that the Translation API is enabled.'}", 502)
        if resp.status_code == 429:
            raise TranslationError("Translation quota exceeded. Try again later.", 429)
        raise TranslationError("The translation service returned an error. Try again.", 502)

    item = resp.json()["data"]["translations"][0]
    return item["translatedText"], item.get("detectedSourceLanguage")


def translate_mymemory(text, source, target):
    if source == "auto":
        raise TranslationError("Auto-detect needs the Google provider. Pick a source language.", 400)
    resp = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": f"{source.split('-')[0]}|{target}"},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        raise TranslationError("The translation service returned an error. Try again.", 502)
    data = resp.json()
    status = int(data.get("responseStatus", 200))
    if status == 429:
        raise TranslationError("Daily free quota reached. Try again tomorrow or switch to Google.", 429)
    if status != 200:
        raise TranslationError(data.get("responseDetails") or "Translation failed.", 502)
    return data["responseData"]["translatedText"], None


@app.route("/")
def index():
    return render_template("index.html", max_chars=MAX_CHARS, provider=PROVIDER)


@app.route("/api/languages")
def languages():
    return jsonify({"languages": LANGUAGES, "autoDetect": PROVIDER == "google", "maxChars": MAX_CHARS})


@app.route("/api/translate", methods=["POST"])
def translate():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Request must be JSON."), 400

    text = (body.get("text") or "").strip()
    source = body.get("source") or "auto"
    target = body.get("target") or ""

    if not text:
        return jsonify(error="Enter some text to translate."), 400
    if len(text) > MAX_CHARS:
        return jsonify(error=f"Text is too long. The limit is {MAX_CHARS} characters."), 400
    if target not in LANGUAGES:
        return jsonify(error="Choose a valid target language."), 400
    if source != "auto" and source not in LANGUAGES:
        return jsonify(error="Choose a valid source language."), 400
    if source == target:
        return jsonify(error="Source and target languages are the same."), 400

    try:
        fn = translate_google if PROVIDER == "google" else translate_mymemory
        translated, detected = fn(text, source, target)
        return jsonify(translation=translated, detectedSource=detected)
    except TranslationError as e:
        return jsonify(error=e.message), e.status
    except requests.Timeout:
        return jsonify(error="The translation service timed out. Try again."), 504
    except requests.ConnectionError:
        return jsonify(error="Could not reach the translation service. Check your internet connection."), 503
    except (KeyError, IndexError, ValueError):
        log.exception("Unexpected API response")
        return jsonify(error="Got an unexpected response from the translation service."), 502
    except Exception:
        log.exception("Unhandled error")
        return jsonify(error="Something went wrong on the server."), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
