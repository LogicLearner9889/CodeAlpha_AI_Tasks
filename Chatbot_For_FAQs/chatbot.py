"""FAQ chatbot engine: NLTK preprocessing + TF-IDF + cosine similarity."""
import json
import logging
import re
from pathlib import Path

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 2000  # raised from 500

# Politeness / filler words that carry no meaning for matching
FILLER_WORDS = {
    "hi", "hello", "hey", "please", "tell", "quick", "question", "wondering",
    "let", "know", "like", "would", "could", "just", "thanks", "thank",
}


class ChatbotError(Exception):
    """Base error for chatbot problems."""


class FAQLoadError(ChatbotError):
    """Raised when the FAQ file is missing, malformed or empty."""


class InvalidQueryError(ChatbotError):
    """Raised when the user's question is empty or too long."""


def ensure_nltk_data():
    """Download required NLTK resources if missing (needs internet once)."""
    resources = {
        "punkt": "tokenizers/punkt",
        "punkt_tab": "tokenizers/punkt_tab",
        "stopwords": "corpora/stopwords",
        "wordnet": "corpora/wordnet",
    }
    for pkg, path in resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            try:
                nltk.download(pkg, quiet=True)
            except Exception as exc:  # network failure etc.
                logger.warning("Could not download NLTK package %s: %s", pkg, exc)


class FAQChatbot:
    def __init__(self, faq_path, threshold=0.25):
        ensure_nltk_data()
        self.threshold = threshold
        try:
            self.stop_words = set(stopwords.words("english")) | FILLER_WORDS
            self.lemmatizer = WordNetLemmatizer()
            self.lemmatizer.lemmatize("test")  # verify wordnet is usable
        except LookupError as exc:
            raise ChatbotError(
                "NLTK data missing. Run once with internet: "
                "python -m nltk.downloader punkt punkt_tab stopwords wordnet"
            ) from exc

        self.faqs = self._load_faqs(faq_path)
        self._build_index()

    # ---------- loading ----------
    @staticmethod
    def _load_faqs(path):
        p = Path(path)
        if not p.exists():
            raise FAQLoadError(f"FAQ file not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FAQLoadError(f"FAQ file is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise FAQLoadError(f"Cannot read FAQ file: {exc}") from exc

        if not isinstance(data, list) or not data:
            raise FAQLoadError("FAQ file must contain a non-empty list.")

        clean = []
        for i, item in enumerate(data):
            if (
                isinstance(item, dict)
                and str(item.get("question", "")).strip()
                and str(item.get("answer", "")).strip()
            ):
                question = item["question"].strip()
                clean.append(
                    {
                        "question": question,
                        "answer": item["answer"].strip(),
                        # clean version of the question shown to the user
                        "canonical": str(item.get("canonical") or question).strip(),
                    }
                )
            else:
                logger.warning("Skipping invalid FAQ entry at index %d", i)
        if not clean:
            raise FAQLoadError("No valid FAQ entries (need 'question' and 'answer').")
        return clean

    # ---------- NLP ----------
    def preprocess(self, text):
        """Lowercase, strip punctuation, tokenize, remove stopwords, lemmatize."""
        text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        try:
            tokens = word_tokenize(text)
        except LookupError:
            tokens = text.split()  # fallback if punkt is unavailable
        tokens = [
            self.lemmatizer.lemmatize(t)
            for t in tokens
            if t not in self.stop_words and len(t) > 1
        ]
        return " ".join(tokens)

    def _build_index(self):
        # The question counts twice so it outweighs words that only appear in the answer.
        corpus = []
        for f in self.faqs:
            q = self.preprocess(f["question"])
            corpus.append(f"{q} {q} {self.preprocess(f['answer'])}")
        if not any(c.strip() for c in corpus):
            raise FAQLoadError("FAQs contain no usable text after preprocessing.")
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(corpus)

    # ---------- matching ----------
    def validate(self, query):
        if not isinstance(query, str) or not query.strip():
            raise InvalidQueryError("Please type a question.")
        if len(query) > MAX_QUERY_LENGTH:
            raise InvalidQueryError(
                f"Question is too long (max {MAX_QUERY_LENGTH} characters)."
            )
        return query.strip()

    def _suggestions(self, scores, limit=3):
        """Closest distinct FAQ questions, used when nothing matches well enough."""
        out, seen = [], set()
        for idx in scores.argsort()[::-1]:
            if scores[idx] <= 0:
                break
            canonical = self.faqs[int(idx)]["canonical"]
            if canonical not in seen:
                seen.add(canonical)
                out.append(canonical)
            if len(out) == limit:
                break
        return out

    def get_response(self, query):
        query = self.validate(query)
        processed = self.preprocess(query)
        if not processed:
            return {
                "answer": "I couldn't find any meaningful words in that. Could you rephrase?",
                "matched_question": None,
                "score": 0.0,
                "matched": False,
                "suggestions": [],
            }

        vec = self.vectorizer.transform([processed])
        scores = cosine_similarity(vec, self.matrix).ravel()
        best = int(scores.argmax())
        score = float(scores[best])

        if score < self.threshold:
            return {
                "answer": "Sorry, I don't have an answer for that. Try rephrasing, "
                "or contact our support team.",
                "matched_question": None,
                "score": round(score, 3),
                "matched": False,
                "suggestions": self._suggestions(scores),
            }
        return {
            "answer": self.faqs[best]["answer"],
            "matched_question": self.faqs[best]["canonical"],
            "score": round(score, 3),
            "matched": True,
            "suggestions": [],
        }


if __name__ == "__main__":  # simple CLI mode
    bot = FAQChatbot(Path(__file__).with_name("faqs.json"))
    print(f"FAQ Bot with {len(bot.faqs)} questions (type 'quit' to exit)")
    while True:
        try:
            q = input("You: ")
        except (EOFError, KeyboardInterrupt):
            break
        if q.strip().lower() in {"quit", "exit"}:
            break
        try:
            print("Bot:", bot.get_response(q)["answer"])
        except InvalidQueryError as e:
            print("Bot:", e)
