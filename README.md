<div align="center">

# AI Projects Collection

**Three hands-on AI projects in one repository: Translation • FAQ Chatbot • Music Generation**

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![NLP](https://img.shields.io/badge/NLP-NLTK%20%7C%20SpaCy-green)
![TensorFlow](https://img.shields.io/badge/TensorFlow-Keras-FF6F00?logo=tensorflow&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

## Table of Contents

- [Projects at a Glance](#-projects-at-a-glance)
- [Repository Structure](#-repository-structure)
- [Common Setup](#-common-setup)
- [Project 1: Language Translation Tool](#-project-1-language-translation-tool)
- [Project 2: FAQ Chatbot with NLP Matching](#-project-2-faq-chatbot-with-nlp-matching)
- [Project 3: AI Music Generation (RNN & GAN)](#-project-3-ai-music-generation-rnn--gan)
- [Error Handling Summary](#-error-handling-summary)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## Projects at a Glance

| # | Project | What it does | Core tech |
|---|---|---|---|
| 1 |  **Language Translation Tool** | Translates text between 100+ languages with copy and text-to-speech | Flask, Google / Microsoft Translator API |
| 2 |  **FAQ Chatbot** | Finds the best FAQ answer for a user's question | NLTK / SpaCy, TF-IDF, cosine similarity |
| 3 |  **AI Music Generation** | Learns from MIDI files and composes new music | music21, LSTM / GAN, TensorFlow |

All three use a **Flask web UI** with separate CSS and JS files, animations, responsive design, and full **error handling**.

##  Repository Structure

```
ai-projects/
├── README.md
├── translation-tool/
│   ├── app.py
│   ├── translator.py
│   ├── .env.example
│   ├── requirements.txt
│   ├── templates/index.html
│   └── static/{css/style.css, js/app.js}
├── faq-chatbot/
│   ├── app.py
│   ├── chatbot.py
│   ├── preprocess.py
│   ├── data/faqs.csv
│   ├── requirements.txt
│   ├── templates/index.html
│   └── static/{css/style.css, js/chat.js}
└── music-generation-ai/
    ├── app.py
    ├── preprocess.py
    ├── model_lstm.py
    ├── model_gan.py
    ├── train.py
    ├── generate.py
    ├── data/midi/
    ├── models/
    ├── outputs/
    ├── requirements.txt
    ├── templates/index.html
    └── static/{css/style.css, js/app.js}
```

##  Common Setup

```bash
# 1. Clone
git clone https://github.com/<your-username>/ai-projects.git
cd ai-projects

# 2. Pick a project and enter its folder
cd translation-tool          # or faq-chatbot / music-generation-ai

# 3. Create a virtual environment
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run
python app.py                # open http://127.0.0.1:5000
```

>  Use a **separate virtual environment per project**. TensorFlow and SpaCy can conflict with each other.

---

#  Project 1: Language Translation Tool

Type text, choose a **source** and **target** language, and get the translation from **Google Translate** or **Microsoft Translator**.

###  Features

-  Translate 100+ languages
-  Auto-detect source language
-  Swap languages in one click
-  Copy button
-  Text-to-speech (Web Speech API)
-  Live character counter with max length

###  How it works

```
User text ──► JS validation ──► Flask /api/translate ──► Translation API
     ▲                                                        │
     └────────── Translated text ◄── JSON response ◄──────────┘
```

###  Configuration (`.env`)

```env
TRANSLATION_PROVIDER=google        # google | microsoft
GOOGLE_API_KEY=your_key
MICROSOFT_API_KEY=your_key
MICROSOFT_REGION=your_region
MAX_CHARS=5000
REQUEST_TIMEOUT=10
```

>  Never commit `.env`. Add it to `.gitignore`.

###  API

`POST /api/translate`

```json
// Request
{ "text": "Hello", "source": "en", "target": "bn" }

// Success
{ "success": true, "translated_text": "হ্যালো", "detected_source": "en" }

// Error
{ "success": false, "error": "Text is empty.", "code": "EMPTY_TEXT" }
```

###  Errors handled

| Code | Message shown |
|---|---|
| `EMPTY_TEXT` | Please enter some text. |
| `TEXT_TOO_LONG` | Text is too long (max 5000 characters). |
| `SAME_LANGUAGE` | Choose two different languages. |
| `INVALID_LANGUAGE` | Selected language is not supported. |
| `API_KEY_MISSING` | Server is not configured correctly. |
| `API_AUTH_FAILED` | Translation service rejected the request. |
| `RATE_LIMITED` | Too many requests. Please wait. |
| `TIMEOUT` | The service took too long. |
| `NETWORK_ERROR` | You appear to be offline. |

---

#  Project 2: FAQ Chatbot with NLP Matching

A chatbot that answers questions about a topic or product by matching the user's message to the closest FAQ.

###  Features

-  NLP cleaning: lowercase, tokenize, stop-word removal, lemmatization
-  TF-IDF + **cosine similarity** matching
-  Supports **2000+ FAQ questions**
-  Animated chat UI with typing indicator
-  Message length limit with counter
-  Fallback reply when confidence is low

###  How it works

```
Question ──► Preprocess ──► TF-IDF vector ──► Cosine similarity vs. all FAQs
                                                   │
                                   score ≥ threshold ?
                                    ├─ Yes ─► Best answer
                                    └─ No  ─► Fallback message
```

###  One-time NLP downloads

```bash
python -m nltk.downloader punkt stopwords wordnet
python -m spacy download en_core_web_sm
```

###  Dataset format (`data/faqs.csv`)

```csv
question,answer
How do I reset my password?,Click "Forgot password" on the login page.
What payment methods do you accept?,We accept cards, UPI and net banking.
```

Add several phrasings per question for better accuracy.

###  Adding another page (besides home)

```python
@app.route("/about")
def about():
    return render_template("about.html")
```

###  API

`POST /api/chat`

```json
// Request
{ "message": "how can i change my password" }

// Success
{ "success": true, "answer": "...", "matched_question": "How do I reset my password?", "confidence": 0.82 }

// Error
{ "success": false, "error": "Message is empty.", "code": "EMPTY_MESSAGE" }
```

###  Errors handled

| Code | Message shown |
|---|---|
| `EMPTY_MESSAGE` | Please type a question. |
| `MESSAGE_TOO_LONG` | Message is too long (max 500 characters). |
| `INVALID_JSON` | Invalid request. |
| `NO_MATCH` | I couldn't find an answer. Try rephrasing. |
| `DATASET_MISSING` | Knowledge base is unavailable. |
| `MODEL_ERROR` | Something went wrong. Please try again. |
| `NETWORK_ERROR` | You appear to be offline. |

###  Tuning

- Threshold: start at `0.30`.
- Use `TfidfVectorizer(ngram_range=(1, 2))`.
- Vectorize the dataset **once at startup**, not on every request.

---

#  Project 3: AI Music Generation (RNN & GAN)

Train a neural network on **classical or jazz MIDI** files, then generate new music and download it as **MIDI** or **audio**.

###  Features

-  MIDI preprocessing with **music21**
-  **LSTM / RNN** next-note prediction
-  Optional **GAN** (Generator vs. Discriminator)
-  Controls: length and creativity (temperature)
-  MIDI download and 🔊 in-browser playback
-  Animated UI using Tailwind CSS + Bootstrap

###  How it works

```
MIDI files ─► music21 ─► Notes & chords ─► Integer encoding ─► Sliding windows
                                                                  │
                                              ┌───────────────────┴──────────────┐
                                              ▼                                  ▼
                                        LSTM / RNN                           GAN (G + D)
                                              └───────────────────┬──────────────┘
                                                                  ▼
                                      New note sequence ─► MIDI ─► Audio
```

###  Dataset

Put `.mid` files in `data/midi/` (100+ files of **one genre** works best), then:

```bash
python preprocess.py
```

> Make sure you have the right to use the MIDI files you train on.

###  Train

```bash
python train.py --model lstm --epochs 100 --batch-size 64 --seq-length 100
python train.py --model gan  --epochs 300      # optional
```

###  Generate

```bash
python generate.py --length 300 --temperature 1.0 --output outputs/song.mid
```

| Temperature | Result |
|---|---|
| 0.5 | Safe, repetitive |
| 0.8–1.1 | Balanced (good start) |
| 1.2+ | Surprising, riskier |

###  API

`POST /api/generate`

```json
// Request
{ "length": 200, "temperature": 1.0, "model": "lstm" }

// Success
{ "success": true, "midi_url": "/outputs/song_123.mid", "audio_url": "/outputs/song_123.wav" }

// Error
{ "success": false, "error": "Model not trained yet.", "code": "MODEL_NOT_FOUND" }
```

###  Errors handled

| Code | Message shown |
|---|---|
| `NO_MIDI_FILES` | No training data found. Add MIDI files. |
| `CORRUPT_MIDI` | File skipped and logged; training continues. |
| `NOT_ENOUGH_DATA` | Dataset is too small to train. |
| `MODEL_NOT_FOUND` | Model not trained yet. |
| `INVALID_PARAMS` | Length must be between 50 and 1000. |
| `OUT_OF_MEMORY` | Reduce batch size or sequence length. |
| `GENERATION_FAILED` | Could not generate music. Try again. |
| `AUDIO_UNAVAILABLE` | Audio disabled; MIDI still available. |
| `NETWORK_ERROR` | You appear to be offline. |

---

##  Error Handling Summary

All three projects follow the same approach.

**Backend**
- Input validation on every route
- `try/except` around API calls, NLP, and model code
- Request timeouts and JSON validation
- Server-side logging (technical details are never shown to users)
- Custom `404` and `500` pages

**Frontend / device**
- Offline detection with `navigator.onLine`
- Disabled buttons and loading animation during requests (prevents double submit)
- Retry option on failure
- Graceful fallback when the clipboard, speech, or audio playback is unsupported
- Safe text rendering to prevent XSS

##  Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Activate the venv, then `pip install -r requirements.txt` |
| API returns `401 / 403` | Check your key, billing, and that the API is enabled |
| `LookupError: punkt` | Run the NLTK download command |
| `Can't find model 'en_core_web_sm'` | Run the SpaCy download command |
| Port 5000 already used | `flask run --port 5001` |
| Chatbot gives wrong answers | Add more phrasings; tune the threshold |
| Music is one repeating note | Train longer, add data, raise temperature |
| `fluidsynth not found` | Install FluidSynth or use MIDI only |
| Training is very slow | Use a GPU or reduce sequence length |

##  Roadmap

- [ ] Translation: history, file translation, voice input
- [ ] Chatbot: intent classification, admin page, feedback buttons
- [ ] Music: Transformer model, multi-instrument, mood control
- [ ] Dark mode for all UIs
- [ ] Docker support

##  Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m "Add my feature"`
4. Push and open a Pull Request

##  License

Released under the **MIT License**.

<div align="center">

 If this repository helped you, please give it a star!

</div>
