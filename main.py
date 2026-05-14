"""
GOD MODE Telegram Bot v3 PRO — Production Hardened
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Features:
  - Keep-alive HTTP server (prevents Railway sleep)
  - Vision model fallback chain (3 models)
  - Exponential backoff retry on all API calls
  - Crash recovery polling loop (bot never stays down)
  - Global exception handlers on every handler
  - Rate limit + credits error detection
  - /status command for health check

Env vars required:
  TELEGRAM_TOKEN   — BotFather token
  OPENROUTER_KEY   — OpenRouter API key
  PORT             — auto-set by Railway (default 8080)
"""

import os
import json
import math
import base64
import logging
import time
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import Message

# ══════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("godmode")

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "YOUR_OPENROUTER_API_KEY")
PORT           = int(os.getenv("PORT", 8080))
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Vision model fallback chain — tried in order until one succeeds
VISION_MODELS = [
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku",
    "google/gemini-pro-vision",
]

MAX_RETRIES   = 3
RETRY_BACKOFF = 2  # seconds, doubles each attempt

# ══════════════════════════════════════════════════════════════
#  KEEP-ALIVE SERVER (prevents Railway free tier from sleeping)
# ══════════════════════════════════════════════════════════════
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"GOD MODE Bot is alive.")

    def log_message(self, format, *args):
        pass  # Suppress noisy HTTP logs


def run_keep_alive():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    log.info(f"Keep-alive server listening on port {PORT}")
    server.serve_forever()

# ══════════════════════════════════════════════════════════════
#  GOD MODE ENGINE v3 PRO
# ══════════════════════════════════════════════════════════════
CONFIDENCE_MAP = {
    1: 52, 2: 58, 3: 64, 4: 71,
    5: 78, 6: 84, 7: 89
}
DEFAULT_CONFIDENCE = 45


def avg(values):
    return sum(values) / len(values)


def poisson_pmf(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)


def poisson_over_25(lmbda):
    return 1 - sum(poisson_pmf(lmbda, k) for k in range(3))


def btts_probability(lmbda_a, lmbda_b):
    p_a = 1 - poisson_pmf(lmbda_a, 0)
    p_b = 1 - poisson_pmf(lmbda_b, 0)
    return p_a * p_b


def evaluate_fixture(a_for, a_against, b_for, b_against, odds_over_2_5=1.80):
    a_attack = avg(a_for)
    a_def    = avg(a_against)
    b_attack = avg(b_for)
    b_def    = avg(b_against)

    lambda_a     = (a_attack + b_def) / 2
    lambda_b     = (b_attack + a_def) / 2
    total_lambda = lambda_a + lambda_b

    over25_prob   = poisson_over_25(total_lambda)
    btts_prob     = btts_probability(lambda_a, lambda_b)
    draw_pressure = max(0, 1 - abs(lambda_a - lambda_b) / (total_lambda + 0.01))

    if over25_prob >= 0.65:
        market = "Over 2.5 Goals"
        prob   = over25_prob
    elif btts_prob >= 0.62:
        market = "BTTS Yes"
        prob   = btts_prob
    else:
        market = "Lean Over 1.5"
        prob   = max(over25_prob, 0.55)

    confidence_base = int(
        (over25_prob * 0.5 + btts_prob * 0.3 + draw_pressure * 0.2) * 100
    )
    score_level = min(7, max(1, confidence_base // 10))
    confidence  = CONFIDENCE_MAP.get(score_level, DEFAULT_CONFIDENCE)

    edge  = (prob * odds_over_2_5) - 1
    kelly = max(0, edge / odds_over_2_5)

    if confidence >= 85 and kelly > 0.25:
        stake = 3.0
    elif confidence >= 75 and kelly > 0.15:
        stake = 2.0
    elif confidence >= 65:
        stake = 1.5
    else:
        stake = 1.0

    verdict = (
        "🔥 ELITE"  if confidence >= 85 and prob >= 0.65 else
        "✅ STRONG" if confidence >= 75 else
        "🟡 LEAN"   if confidence >= 65 else
        "❌ NO BET"
    )

    return {
        "lambda_home":   round(lambda_a, 2),
        "lambda_away":   round(lambda_b, 2),
        "total_lambda":  round(total_lambda, 2),
        "over25_prob":   round(over25_prob, 3),
        "btts_prob":     round(btts_prob, 3),
        "draw_pressure": round(draw_pressure, 3),
        "market":        market,
        "confidence":    confidence,
        "kelly_edge":    round(edge, 3),
        "stake_units":   stake,
        "verdict":       verdict,
    }


def format_result(res, match_name=None):
    name = match_name or res.get("match", "Unknown Fixture")
    return "\n".join([
        "━━━━━━━━━━━━━━━━━━━━",
        f"⚽ *{name}*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 *Market:* {res['market']}",
        f"🎯 *Verdict:* {res['verdict']}",
        f"📈 *Confidence:* {res['confidence']}%",
        "",
        f"🔢 *λ Home:* {res['lambda_home']}  |  *λ Away:* {res['lambda_away']}",
        f"🌐 *Total λ:* {res['total_lambda']}",
        "",
        f"📉 *Over 2.5 Prob:* {res['over25_prob']*100:.1f}%",
        f"🔁 *BTTS Prob:*     {res['btts_prob']*100:.1f}%",
        f"⚖️ *Draw Pressure:* {res['draw_pressure']*100:.1f}%",
        "",
        f"💰 *Kelly Edge:* {res['kelly_edge']*100:.1f}%",
        f"🏦 *Stake Units:* {res['stake_units']}u",
        "━━━━━━━━━━━━━━━━━━━━",
    ])


def analyse_fixtures(fixtures: list) -> str:
    if not fixtures:
        return "⚠️ No fixtures found to analyse."

    results = []
    for f in fixtures:
        try:
            res = evaluate_fixture(
                f["a_for"], f["a_against"],
                f["b_for"], f["b_against"],
                f.get("odds_over_2_5", 1.80)
            )
            res["match"] = f.get("match", "Unknown")
            results.append(res)
        except Exception as e:
            log.warning(f"Engine error on {f.get('match','?')}: {e}")
            results.append({"match": f.get("match", "?"), "error": str(e)})

    lines = ["🤖 *GOD MODE v3 PRO — ANALYSIS*\n"]
    valid = []

    for r in results:
        if "error" in r:
            lines.append(f"⚠️ {r['match']}: {r['error']}\n")
        else:
            lines.append(format_result(r))
            lines.append("")
            if r["verdict"] != "❌ NO BET":
                valid.append(r)

    if valid:
        elite = max(valid, key=lambda x: (x["confidence"], x["kelly_edge"], x["over25_prob"]))
        lines += [
            "🏆 *TOP PICK THIS BATCH*",
            f"➡️ *{elite['match']}* — {elite['market']}",
            f"   Confidence: {elite['confidence']}% | Stake: {elite['stake_units']}u",
        ]
    else:
        lines.append("📭 No value picks found in this batch.")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  VISION — fallback chain + exponential backoff retry
# ══════════════════════════════════════════════════════════════
VISION_PROMPT = """You are a football statistics extractor.
Given a screenshot of a fixture or league table, extract ALL visible fixtures.

Return ONLY valid JSON (no markdown, no explanation) in this exact structure:
{
  "fixtures": [
    {
      "match": "Home Team vs Away Team",
      "a_for":     [last 3-5 goals scored per game by Home],
      "a_against": [last 3-5 goals conceded per game by Home],
      "b_for":     [last 3-5 goals scored per game by Away],
      "b_against": [last 3-5 goals conceded per game by Away],
      "odds_over_2_5": 1.80
    }
  ]
}

Rules:
- If exact per-game stats aren't visible, estimate from season totals (goals / games played).
- If odds are not visible, default odds_over_2_5 to 1.80.
- If no data is extractable, return: {"fixtures": [], "error": "reason"}
- Return ONLY the JSON object. Nothing else."""


def _call_model(model: str, b64: str) -> dict:
    """Single attempt against one model. Raises on any failure."""
    payload = {
        "model": model,
        "max_tokens": 2000,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": VISION_PROMPT}
            ]
        }]
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://godmode-bot",
        "X-Title":       "GOD MODE Bot",
    }
    resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)

    if resp.status_code == 429:
        raise RuntimeError("RATE_LIMITED")
    if resp.status_code == 402:
        raise RuntimeError("INSUFFICIENT_CREDITS")
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def call_vision_with_fallback(image_bytes: bytes) -> tuple:
    """
    Try each model in VISION_MODELS with exponential backoff per attempt.
    Returns (result_dict, model_name_used).
    Raises RuntimeError if all models and retries are exhausted.
    """
    b64        = base64.b64encode(image_bytes).decode("utf-8")
    last_error = "Unknown error"

    for model in VISION_MODELS:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"Vision: {model} attempt {attempt}/{MAX_RETRIES}")
                result = _call_model(model, b64)
                log.info(f"Vision success: {model}")
                return result, model

            except RuntimeError as e:
                last_error = str(e)
                if last_error == "RATE_LIMITED":
                    wait = RETRY_BACKOFF ** attempt
                    log.warning(f"Rate limited on {model}, retrying in {wait}s")
                    time.sleep(wait)
                elif last_error == "INSUFFICIENT_CREDITS":
                    log.error(f"No credits: {model}, skipping to next model")
                    break  # Skip remaining retries, try next model
                else:
                    time.sleep(RETRY_BACKOFF ** attempt)

            except (json.JSONDecodeError, KeyError) as e:
                last_error = f"Parse error: {e}"
                log.warning(f"Parse fail on {model} attempt {attempt}: {e}")
                time.sleep(RETRY_BACKOFF ** attempt)

            except requests.RequestException as e:
                last_error = str(e)
                log.warning(f"Request error on {model} attempt {attempt}: {e}")
                time.sleep(RETRY_BACKOFF ** attempt)

        log.warning(f"All retries exhausted for {model}")

    raise RuntimeError(f"All vision models failed. Last error: {last_error}")


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def parse_pipe_input(text: str) -> dict:
    """
    Format: Match|aFor1,aFor2,aFor3|aAgainst1,aAgainst2|bFor1,bFor2|bAgainst1,bAgainst2[|odds]
    Example: Arsenal vs Chelsea|2.1,1.8,2.4|0.9,1.1,0.8|1.6,1.9,1.5|1.3,1.0,1.2|1.85
    """
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 5:
        raise ValueError("Need at least 5 pipe-separated fields.")

    def to_floats(s):
        return [float(x.strip()) for x in s.split(",")]

    return {
        "match":         parts[0],
        "a_for":         to_floats(parts[1]),
        "a_against":     to_floats(parts[2]),
        "b_for":         to_floats(parts[3]),
        "b_against":     to_floats(parts[4]),
        "odds_over_2_5": float(parts[5]) if len(parts) > 5 else 1.80,
    }


def send_chunks(bot_instance, chat_id, text, parse_mode="Markdown"):
    """Send long messages in 4000-char chunks; falls back to plain text on parse errors."""
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            bot_instance.send_message(chat_id, chunk, parse_mode=parse_mode)
        except Exception:
            try:
                bot_instance.send_message(chat_id, chunk)
            except Exception as e:
                log.error(f"send_chunks total failure: {e}")


# ══════════════════════════════════════════════════════════════
#  BOT HANDLERS
# ══════════════════════════════════════════════════════════════
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)


@bot.message_handler(commands=["start"])
def cmd_start(msg: Message):
    try:
        bot.send_message(msg.chat.id,
            "⚽ *GOD MODE Bot v3 PRO* is live\!\n\n"
            "Send me:\n"
            "📸 A *screenshot* → AI vision extracts → engine analyses\n"
            "📝 *Pipe\-separated* data → direct engine run\n\n"
            "Type /help for the manual format or /status to check bot health\.",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        log.error(f"cmd_start: {e}")


@bot.message_handler(commands=["help"])
def cmd_help(msg: Message):
    try:
        bot.send_message(msg.chat.id,
            "*Manual Input Format*\n"
            "`Match|aFor|aAgainst|bFor|bAgainst[|odds]`\n\n"
            "Each field = comma\-separated per\-game goal values\.\n\n"
            "*Single fixture:*\n"
            "`Arsenal vs Chelsea|2\.1,1\.8,2\.4|0\.9,1\.1,0\.8|1\.6,1\.9,1\.5|1\.3,1\.0,1\.2|1\.85`\n\n"
            "*Batch \(multi\-line\):*\n"
            "Send multiple lines — one fixture per line\.\n\n"
            "📸 Or just send a screenshot — AI does the rest\.",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        log.error(f"cmd_help: {e}")


@bot.message_handler(commands=["status"])
def cmd_status(msg: Message):
    try:
        models_list = "\n".join([f"  {i+1}. `{m}`" for i, m in enumerate(VISION_MODELS)])
        bot.send_message(msg.chat.id,
            f"✅ *Bot Status: ONLINE*\n\n"
            f"🔁 *Vision fallback chain:*\n{models_list}\n\n"
            f"⚡ *Engine:* GOD MODE v3 PRO\n"
            f"🔄 *Max retries:* {MAX_RETRIES} per model",
            parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"cmd_status: {e}")


@bot.message_handler(content_types=["photo"])
def handle_photo(msg: Message):
    chat_id = msg.chat.id
    try:
        bot.send_chat_action(chat_id, "typing")
        bot.send_message(chat_id, "📸 Screenshot received. Running vision extraction…")

        file_info   = bot.get_file(msg.photo[-1].file_id)
        image_bytes = bot.download_file(file_info.file_path)

        bot.send_chat_action(chat_id, "typing")

        try:
            vision_data, model_used = call_vision_with_fallback(image_bytes)
            model_short = model_used.split("/")[-1]
        except RuntimeError as e:
            err = str(e)
            if "RATE_LIMITED" in err:
                bot.send_message(chat_id,
                    "⏳ Vision API is rate-limited. Please wait 30 seconds and try again.")
            elif "INSUFFICIENT_CREDITS" in err:
                bot.send_message(chat_id,
                    "❌ Vision API credits exhausted. Please contact the admin.")
            else:
                bot.send_message(chat_id,
                    "❌ All vision models failed. Try again later or use manual input (/help).")
            log.error(f"Vision fallback exhausted for chat {chat_id}: {e}")
            return

        if "error" in vision_data and not vision_data.get("fixtures"):
            bot.send_message(chat_id,
                f"⚠️ Could not extract data: {vision_data['error']}\nTry a clearer screenshot.")
            return

        fixtures = vision_data.get("fixtures", [])
        if not fixtures:
            bot.send_message(chat_id, "⚠️ No fixture data found. Try a clearer screenshot.")
            return

        bot.send_message(chat_id,
            f"✅ Extracted *{len(fixtures)}* fixture(s) via `{model_short}`. Analysing…",
            parse_mode="Markdown"
        )
        bot.send_chat_action(chat_id, "typing")
        send_chunks(bot, chat_id, analyse_fixtures(fixtures))

    except Exception as e:
        log.error(f"handle_photo unhandled: {e}", exc_info=True)
        try:
            bot.send_message(chat_id, "❌ Unexpected error. Please try again.")
        except Exception:
            pass


@bot.message_handler(func=lambda m: "|" in (m.text or ""))
def handle_pipe(msg: Message):
    chat_id = msg.chat.id
    try:
        bot.send_chat_action(chat_id, "typing")
        lines    = [l.strip() for l in msg.text.strip().splitlines() if l.strip()]
        fixtures = []

        for line in lines:
            try:
                fixtures.append(parse_pipe_input(line))
            except Exception as e:
                bot.send_message(chat_id,
                    f"⚠️ Skipped: `{line[:50]}` — {e}", parse_mode="Markdown")

        if not fixtures:
            bot.send_message(chat_id,
                "❌ No valid fixtures parsed. Type /help for the correct format.")
            return

        send_chunks(bot, chat_id, analyse_fixtures(fixtures))

    except Exception as e:
        log.error(f"handle_pipe unhandled: {e}", exc_info=True)
        try:
            bot.send_message(chat_id, "❌ Unexpected error. Please try again.")
        except Exception:
            pass


@bot.message_handler(func=lambda m: True)
def handle_other(msg: Message):
    try:
        bot.send_message(msg.chat.id,
            "Send a 📸 screenshot or pipe-separated data.\n"
            "Type /help for format | /status to check bot health."
        )
    except Exception as e:
        log.error(f"handle_other: {e}")


# ══════════════════════════════════════════════════════════════
#  CRASH-RECOVERY POLLING LOOP
# ══════════════════════════════════════════════════════════════
def start_polling():
    consecutive_failures = 0
    while True:
        try:
            log.info("Bot polling started.")
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=20,
                allowed_updates=["message"],
            )
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            wait = min(60, RETRY_BACKOFF ** consecutive_failures)
            log.error(
                f"Polling crashed (failure #{consecutive_failures}): {e}. "
                f"Restarting in {wait}s…"
            )
            time.sleep(wait)


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("🤖 GOD MODE Bot v3 PRO starting…")

    # Start keep-alive HTTP server in background (Railway needs an open port)
    threading.Thread(target=run_keep_alive, daemon=True).start()

    # Start bot with crash recovery
    start_polling()
