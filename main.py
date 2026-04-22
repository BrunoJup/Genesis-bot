import os
import time
import base64
import re
import requests
from io import BytesIO
from PIL import Image
import telebot
from openai import OpenAI

# =========================
# ENV VARIABLES
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# =========================
# INIT
# =========================
bot = telebot.TeleBot(TELEGRAM_TOKEN)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

MAX_RETRIES = 3
MODELS = ["openai/gpt-4o", "openai/gpt-4o-mini"]

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = """
🔒 SYSTEM MODE: V7.1 — BETPAWA VIRTUAL 1H TOP SCORER DETECTOR
📊 INPUT TYPE: SCREENSHOT (PAST RESULTS + CURRENT FIXTURES)
🎯 OUTPUT MODE: SINGLE MATCH ONLY

🧠 CORE OBJECTIVE:
Identify the ONE team with the HIGHEST TOTAL FIRST HALF (1H) GOALS SCORED across the LAST 3 MATCHDAYS, then locate its current fixture.

⚙️ EXECUTION ENGINE:
1️⃣ Extract ONLY first-half scores from LAST 3 matches
2️⃣ Sum ONLY goals scored (not conceded)
3️⃣ Pick team with highest total (consistency priority)
4️⃣ Match with current fixtures
5️⃣ Resolve ties via consistency → fixture order

🚫 RULES:
- NO explanations
- NO multiple picks
- NO full-time data

📢 OUTPUT:
🔥 [HOME TEAM] vs [AWAY TEAM]
⚡ TEAM: [TEAM NAME]
📊 CONFIDENCE: [HIGH/MEDIUM/LOW]
🎯 ACCURACY: [X/10]
"""

# =========================
# IMAGE DOWNLOAD + COMPRESS
# =========================
def download_and_compress(file_id):
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    img_bytes = requests.get(file_url).content
    img = Image.open(BytesIO(img_bytes))

    img = img.convert("RGB")
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=60)  # compression
    return buffer.getvalue()

# =========================
# OUTPUT VALIDATION
# =========================
def validate_output(text):
    pattern = r"🔥 .+ vs .+\n⚡ TEAM: .+\n📊 CONFIDENCE: (HIGH|MEDIUM|LOW)\n🎯 ACCURACY: \d+/10"
    return re.search(pattern, text.strip())

def fix_output(text):
    lines = text.strip().split("\n")

    match_line = next((l for l in lines if "vs" in l), "🔥 UNKNOWN vs UNKNOWN")
    team_line = next((l for l in lines if "TEAM" in l), "⚡ TEAM: UNKNOWN")
    conf_line = next((l for l in lines if "CONFIDENCE" in l), "📊 CONFIDENCE: MEDIUM")
    acc_line = next((l for l in lines if "ACCURACY" in l), "🎯 ACCURACY: 5/10")

    return f"{match_line}\n{team_line}\n{conf_line}\n{acc_line}"

# =========================
# AI CALL (RETRY + FALLBACK)
# =========================
def analyze_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    for model in MODELS:
        for _ in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Analyze this screenshot."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    },
                                },
                            ],
                        },
                    ],
                )

                result = response.choices[0].message.content.strip()

                # Validate
                if validate_output(result):
                    return result
                else:
                    return fix_output(result)

            except Exception:
                time.sleep(2)

    return "❌ Failed to analyze image. Try again."

# =========================
# HANDLERS
# =========================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        bot.reply_to(message, "⏳ Processing screenshot...")

        file_id = message.photo[-1].file_id
        image_bytes = download_and_compress(file_id)

        result = analyze_image(image_bytes)

        bot.send_message(message.chat.id, result)

    except Exception:
        bot.send_message(message.chat.id, "❌ Error processing image")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    bot.reply_to(message, "📸 Send a screenshot.")

# =========================
# START BOT
# =========================
if __name__ == "__main__":
    print("🤖 Bot running (GPT-4o + fallback + validation)...")
    bot.infinity_polling()
