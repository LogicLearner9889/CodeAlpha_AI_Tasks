"""
Task 3: Music Generation with AI (LSTM + music21)

Pipeline:
  1. Collect MIDI files into ./midi_data/  (classical, jazz, etc.)
  2. Preprocess: extract notes/chords with music21 -> integer sequences
  3. Build + train a stacked LSTM (next-note prediction)
  4. Generate a new sequence and save it as MIDI
  5. (Optional) render MIDI to WAV with FluidSynth

Install:
  pip install music21 tensorflow numpy
  # optional audio rendering:
  pip install midi2audio   (and install FluidSynth + a .sf2 soundfont)

Usage:
  python music_generation.py train      # preprocess + train
  python music_generation.py generate   # generate output.mid (+ output.wav if possible)
  python music_generation.py all        # both
"""

import glob
import os
import pickle
import sys

import numpy as np
from music21 import chord, converter, instrument, note, stream

# ----------------------------- Config ---------------------------------
MIDI_DIR = "midi_data"            # put .mid / .midi files here
NOTES_FILE = "data/notes.pkl"
VOCAB_FILE = "data/vocab.pkl"
WEIGHTS_FILE = "data/model.keras"
OUTPUT_MIDI = "output.mid"
OUTPUT_WAV = "output.wav"
SOUNDFONT = "soundfont.sf2"       # optional, needed only for WAV rendering

SEQ_LEN = 50          # notes of context fed to the model
EPOCHS = 50
BATCH_SIZE = 64
N_GENERATE = 300      # number of notes/chords to generate
TEMPERATURE = 1.0     # <1 = safer/repetitive, >1 = more random

os.makedirs("data", exist_ok=True)


# ------------------------- 1. Preprocessing ---------------------------
def extract_notes(midi_dir=MIDI_DIR):
    """Parse every MIDI file into a flat list of note/chord tokens."""
    files = glob.glob(os.path.join(midi_dir, "**", "*.mid*"), recursive=True)
    if not files:
        raise FileNotFoundError(
            f"No MIDI files found in '{midi_dir}/'. Add some .mid files first."
        )

    notes = []
    for i, path in enumerate(files, 1):
        try:
            midi = converter.parse(path)
        except Exception as e:  # corrupt / unsupported files
            print(f"  skipped {path}: {e}")
            continue

        print(f"[{i}/{len(files)}] parsing {os.path.basename(path)}")
        parts = instrument.partitionByInstrument(midi)
        elements = parts.parts[0].recurse() if parts else midi.flat.notes

        for el in elements:
            if isinstance(el, note.Note):
                notes.append(str(el.pitch))
            elif isinstance(el, chord.Chord):
                # encode chord as dot-separated pitch classes, e.g. "4.7.11"
                notes.append(".".join(str(n) for n in el.normalOrder))

    with open(NOTES_FILE, "wb") as f:
        pickle.dump(notes, f)
    print(f"Extracted {len(notes)} tokens from {len(files)} files")
    return notes


def prepare_sequences(notes):
    """Turn tokens into (X, y) arrays for supervised next-token training."""
    vocab = sorted(set(notes))
    note_to_int = {n: i for i, n in enumerate(vocab)}
    n_vocab = len(vocab)

    inputs, outputs = [], []
    for i in range(len(notes) - SEQ_LEN):
        inputs.append([note_to_int[n] for n in notes[i:i + SEQ_LEN]])
        outputs.append(note_to_int[notes[i + SEQ_LEN]])

    X = np.array(inputs, dtype=np.float32).reshape(-1, SEQ_LEN, 1) / float(n_vocab)
    y = np.array(outputs)

    with open(VOCAB_FILE, "wb") as f:
        pickle.dump(vocab, f)
    return X, y, n_vocab


# ---------------------------- 2. Model --------------------------------
def build_model(n_vocab):
    from tensorflow.keras import layers, models

    model = models.Sequential([
        layers.Input(shape=(SEQ_LEN, 1)),
        layers.LSTM(256, return_sequences=True),
        layers.Dropout(0.3),
        layers.LSTM(256, return_sequences=True),
        layers.Dropout(0.3),
        layers.LSTM(256),
        layers.Dense(256, activation="relu"),
        layers.Dropout(0.3),
        layers.Dense(n_vocab, activation="softmax"),
    ])
    model.compile(loss="sparse_categorical_crossentropy", optimizer="adam")
    return model


def train():
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

    notes = extract_notes()
    X, y, n_vocab = prepare_sequences(notes)
    print(f"Training samples: {len(X)} | vocab size: {n_vocab}")

    model = build_model(n_vocab)
    model.summary()

    callbacks = [
        ModelCheckpoint(WEIGHTS_FILE, monitor="loss", save_best_only=True),
        EarlyStopping(monitor="loss", patience=8, restore_best_weights=True),
    ]
    model.fit(X, y, epochs=EPOCHS, batch_size=BATCH_SIZE, callbacks=callbacks)
    model.save(WEIGHTS_FILE)
    print(f"Model saved to {WEIGHTS_FILE}")


# -------------------------- 3. Generation -----------------------------
def sample(probs, temperature=TEMPERATURE):
    """Temperature sampling for more varied (less looping) music."""
    probs = np.asarray(probs, dtype=np.float64)
    probs = np.log(probs + 1e-9) / temperature
    probs = np.exp(probs)
    probs /= probs.sum()
    return np.random.choice(len(probs), p=probs)


_cache = {}


def _load_assets():
    """Load model + vocab once and reuse (important for the web app)."""
    if not _cache:
        from tensorflow.keras.models import load_model

        with open(NOTES_FILE, "rb") as f:
            _cache["notes"] = pickle.load(f)
        with open(VOCAB_FILE, "rb") as f:
            _cache["vocab"] = pickle.load(f)
        _cache["model"] = load_model(WEIGHTS_FILE)
    return _cache["notes"], _cache["vocab"], _cache["model"]


def clear_cache():
    _cache.clear()


def generate_notes(n_notes=N_GENERATE, temperature=TEMPERATURE):
    notes, vocab, model = _load_assets()

    n_vocab = len(vocab)
    note_to_int = {n: i for i, n in enumerate(vocab)}
    int_to_note = {i: n for n, i in note_to_int.items()}

    # random seed taken from the training data
    start = np.random.randint(0, len(notes) - SEQ_LEN - 1)
    pattern = [note_to_int[n] for n in notes[start:start + SEQ_LEN]]

    generated = []
    for _ in range(n_notes):
        x = np.reshape(pattern, (1, SEQ_LEN, 1)) / float(n_vocab)
        idx = sample(model.predict(x, verbose=0)[0], temperature)
        generated.append(int_to_note[idx])
        pattern = pattern[1:] + [idx]
    return generated


# ------------------------ 4. Notes -> MIDI ----------------------------
def to_midi(tokens, out_file=OUTPUT_MIDI, step=0.5):
    offset = 0.0
    out = []
    for tok in tokens:
        if "." in tok or tok.isdigit():          # chord
            notes_in_chord = []
            for n in tok.split("."):
                nn = note.Note(int(n))
                nn.storedInstrument = instrument.Piano()
                notes_in_chord.append(nn)
            el = chord.Chord(notes_in_chord)
        else:                                      # single note
            el = note.Note(tok)
            el.storedInstrument = instrument.Piano()
        el.offset = offset
        out.append(el)
        offset += step

    stream.Stream(out).write("midi", fp=out_file)
    print(f"Saved MIDI -> {out_file}")


# ----------------------- 5. MIDI -> audio (opt) -----------------------
def to_audio(midi_file=OUTPUT_MIDI, wav_file=OUTPUT_WAV):
    try:
        from midi2audio import FluidSynth
        FluidSynth(SOUNDFONT).midi_to_audio(midi_file, wav_file)
        print(f"Saved audio -> {wav_file}")
    except Exception as e:
        print(f"Audio rendering skipped ({e}). "
              f"Open {midi_file} in any MIDI player (VLC, MuseScore, GarageBand).")


def generate():
    tokens = generate_notes()
    to_midi(tokens)
    to_audio()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("train", "all"):
        train()
    if cmd in ("generate", "all"):
        generate()
