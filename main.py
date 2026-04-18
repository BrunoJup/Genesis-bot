import os
import logging
import base64
from io import BytesIO

import telebot
from PIL import Image
from openai import OpenAI

# ENV VARIABLES
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# INIT BOT
bot = telebot.TeleBot(TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO)

# AI CLIENT (OpenRouter)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# ULTRA PROMPT
SYSTEM_PROMPT = """
You are an elite, expert-level high-precision football goals analysis engine.

STRICT RULES:
Work silently.
No explanations.
No commentary.
Only output final structured result.

STEP 1 — Extract:
a_for, a_against, b_for, b_against (arrays)

STEP 2 — Compute:
a_for_avg
a_against_avg
b_for_avg
b_against_avg
total_avg = sum of all
ht_avg = (a_for_avg + b_for_avg) / 2

STEP 3 — Score:
TOTAL:
≥9 → +4
≥8 → +3
≥7 → +2
≥6 → +1

HT:
≥4 → +3
≥3 → +2
≥2.5 → +1

DEFENSE:
both ≥3 → +2
both ≥2 → +1

STEP 4 — MARKET DECISION:

If total_avg ≥ 8.5 AND score ≥ 8:
→ OVER 7.5

If 7.2 ≤ total_avg < 8.5 AND score ≥ 6:
→ OVER 6.5

If 6.0 ≤ total_avg < 7.2 AND score ≥ 5:
→ OVER 5.5

Else:
→ NO BET

STEP 5 — CONFIDENCE:
9+ → 99%
8 → 94%
7 → 88%
6 → 82%
5 → 76%
4 → 68%
<4 → 45%

STEP 6 — VERDICT:
≥8 → 👑 ULTRA PRO MAX LEGEND PICK
≥6 → 🔥 VERY STRONG
≥4 → ✅ STRONG
<4 → ❌ NO BET

FINAL OUTPUT ONLY:

Match: TEAM A vs TEAM B
Avg Total Goals: X.XX
Avg HT Goals: X.XX
Best Market: OVER X.5 / NO BET
Confidence: XX%
Verdict: [Emoji] [Text]
"""

MODELS = [
    "openai/gpt-4o",
    "google/gemini-2.0-pro-exp-02-05"
]


def send_to_ai(image_base64):
    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this screenshot."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception:
            continue
    return "❌ NO BET"


def validate_market(text):
    if "OVER 7.5" in text or "OVER 6.5" in text or "OVER 5.5" in text or "NO BET" in text:
        return text
    return "❌ NO BET"


def format_result(raw_text):
    try:
        lines = raw_text.split("\n")
        data = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()

        return f"""
╔══════════════════╗
   ⚽ ULTRA ANALYSIS
╚══════════════════╝

🏟 Match:
{data.get("Match", "-")}

📊 Avg Goals:
➤ Total: {data.get("Avg Total Goals", "-")}
➤ HT: {data.get("Avg HT Goals", "-")}

🎯 Market:
{data.get("Best Market", "-")}

📈 Confidence:
{data.get("Confidence", "-")}

🏆 Verdict:
{data.get("Verdict", "-")}
"""
    except:
        return raw_text


@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Send screenshot.")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.reply_to(message, "Processing...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        image = Image.open(BytesIO(downloaded_file))
        buffer = BytesIO()
        image.save(buffer, format="JPEG")

        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        result = send_to_ai(image_base64)
        validated = validate_market(result)
        formatted = format_result(validated)

        bot.reply_to(message, formatted)

    except Exception as e:
        logging.error(e)
        bot.reply_to(message, "❌ Error processing image")


if __name__ == "__main__":
    print("Bot running (polling mode)...")
    bot.infinity_polling()
