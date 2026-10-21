"""
Flask UI for Task 3: Music Generation with AI.

Run:
    pip install flask music21 tensorflow numpy
    python app.py
Then open http://127.0.0.1:5000

Folder layout:
    app.py
    music_generation.py
    templates/index.html
    midi_data/            <- training MIDI files (or upload them in the UI)
"""

import os
import threading
import uuid

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

import music_generation as mg

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB per upload batch

GEN_DIR = os.path.join("static", "generated")
os.makedirs(GEN_DIR, exist_ok=True)
os.makedirs(mg.MIDI_DIR, exist_ok=True)

# Simple in-memory training status (single-user demo)
train_state = {"running": False, "message": "Idle", "error": None}


def model_ready():
    return os.path.exists(mg.WEIGHTS_FILE) and os.path.exists(mg.VOCAB_FILE)


def _train_worker(epochs):
    try:
        train_state.update(running=True, message="Training…", error=None)
        mg.EPOCHS = epochs
        mg.train()
        mg.clear_cache()
        train_state["message"] = "Training finished. Model ready."
    except Exception as e:  # surface any failure to the UI
        train_state.update(error=str(e), message="Training failed")
    finally:
        train_state["running"] = False


@app.route("/")
def index():
    n_files = len([f for f in os.listdir(mg.MIDI_DIR)
                   if f.lower().endswith((".mid", ".midi"))])
    return render_template("index.html", model_ready=model_ready(), n_files=n_files)


@app.route("/upload", methods=["POST"])
def upload():
    saved = 0
    for f in request.files.getlist("files"):
        name = secure_filename(f.filename or "")
        if name.lower().endswith((".mid", ".midi")):
            f.save(os.path.join(mg.MIDI_DIR, name))
            saved += 1
    if not saved:
        return jsonify(error="No valid .mid/.midi files received."), 400
    return jsonify(saved=saved)


@app.route("/train", methods=["POST"])
def train():
    if train_state["running"]:
        return jsonify(error="Training already in progress."), 409
    data = request.get_json(silent=True) or {}
    try:
        epochs = max(1, min(int(data.get("epochs", 30)), 300))
    except (TypeError, ValueError):
        return jsonify(error="Epochs must be a whole number between 1 and 300."), 400
    if not any(f.lower().endswith((".mid", ".midi")) for f in os.listdir(mg.MIDI_DIR)):
        return jsonify(error="No MIDI files found. Upload some first."), 400
    threading.Thread(target=_train_worker, args=(epochs,), daemon=True).start()
    return jsonify(started=True)


@app.route("/status")
def status():
    return jsonify(**train_state, model_ready=model_ready())


@app.route("/generate", methods=["POST"])
def generate():
    if not model_ready():
        return jsonify(error="No trained model yet. Upload MIDI files and train first."), 400
    data = request.get_json(silent=True) or {}
    try:
        n_notes = max(20, min(int(data.get("length", 200)), 1000))
        temperature = max(0.3, min(float(data.get("temperature", 1.0)), 2.0))
        step = max(0.125, min(float(data.get("step", 0.5)), 2.0))
    except (TypeError, ValueError):
        return jsonify(error="Invalid parameters."), 400

    try:
        tokens = mg.generate_notes(n_notes, temperature)
        name = f"{uuid.uuid4().hex[:10]}"
        midi_path = os.path.join(GEN_DIR, f"{name}.mid")
        mg.to_midi(tokens, out_file=midi_path, step=step)

        resp = {"midi": f"/static/generated/{name}.mid"}
        wav_path = os.path.join(GEN_DIR, f"{name}.wav")
        mg.to_audio(midi_path, wav_path)
        if os.path.exists(wav_path):
            resp["wav"] = f"/static/generated/{name}.wav"
        return jsonify(resp)
    except Exception as e:
        return jsonify(error=f"Generation failed: {e}"), 500


HTTP_MSG = {
    404: "That endpoint does not exist.",
    405: "That action is not allowed here.",
    413: "Upload too large (max 64 MB per upload).",
    415: "Unsupported request format.",
}


@app.errorhandler(HTTPException)
def handle_http(e):
    if request.path.startswith("/static"):
        return e
    return jsonify(error=HTTP_MSG.get(e.code, e.description)), e.code


@app.errorhandler(Exception)
def handle_any(e):
    app.logger.exception(e)
    return jsonify(error="Unexpected server error. Check the server console."), 500


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
