import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from chatbot import ChatbotError, FAQChatbot, InvalidQueryError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # reject huge payloads

bot = None
startup_error = None
try:
    bot = FAQChatbot(Path(__file__).with_name("faqs.json"))
except ChatbotError as exc:
    startup_error = str(exc)
    logger.error("Chatbot failed to start: %s", exc)


@app.route("/")
def index():
    return render_template("index.html", startup_error=startup_error)


@app.route("/chat", methods=["POST"])
def chat():
    if bot is None:
        return jsonify(error=f"Chatbot unavailable: {startup_error}"), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "message" not in data:
        return jsonify(error="Invalid request. Send JSON like {\"message\": \"...\"}."), 400

    try:
        return jsonify(bot.get_response(data["message"]))
    except InvalidQueryError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        logger.exception("Unexpected error while answering")
        return jsonify(error="Something went wrong on our side. Please try again."), 500


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="Not found."), 404


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Request too large."), 413


if __name__ == "__main__":
    app.run(debug=True)
