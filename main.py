import os
import telebot
import base64
from flask import Flask
from threading import Thread
from openai import OpenAI

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# Initialize clients
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

app = Flask('')

ULTRA_PRO_PROMPT = """
ROLE:
You are the Elite Football Blackbox. Your mission is to identify ONE single highest-probability high-scoring match from the given fixtures. If no match meets ALL criteria, output NO PICK.

🔍 PHASE 1: ELITE FILTER (STRUCTURAL BALANCE)
Table Position Difference ≤ 2
Points Gap ≤ 4
Both teams must be ranked within Top 12
If ANY condition fails → REJECT match

🔥 PHASE 2: SCORING FORM AUDIT (LEGEND FILTER)
Both teams average > 1.5 Goals Scored per match
Both teams average > 1.2 Goals Conceded per match
Last 5 Matches:
Must score in at least 3/5 games
No prolonged low-scoring trend
If ANY condition fails → REJECT match

⚡ PHASE 3: VOLATILITY CHECK
Target ONLY high-volatility games:
High Goals Scored + High Goals Conceded (both teams)
Reject:
Strong defensive teams (Low GA)
Low-tempo / low-scoring profiles

🚫 FINAL DECISION RULE
Select ONLY ONE match that BEST fits ALL filters
If none qualify → output NO PICK

OUTPUT FORMAT (STRICT – COPY ONLY)
MATCH: [Team A vs Team B]
BTTS: YES
OVER 3.5: YES/NO
CONFIDENCE: 🔥 HIGH (95%+)
OR
❌ NO PICK (Reason: [Reason])
"""

@bot.message_handler(content_types=['photo'])
def handle_stats_screenshot(message):
    try:
        bot.reply_to(message, "🔍 Scanning fixtures via OpenRouter...")

        # 1. Download image from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 2. Encode to Base64
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        # 3. Request analysis from OpenRouter
        # Using gemini-2.0-flash-001 for high speed and great OCR
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://render.com", # Required by OpenRouter
                "X-Title": "Football Analyst Bot",
            },
            model="google/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ULTRA_PRO_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )

        result = response.choices[0].message.content
        bot.reply_to(message, result)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "⚽ ULTRA PRO MAX LEGEND ANALYST ACTIVE.\nSend a screenshot of the match statistics.")

# --- RENDER WEB SERVER ---
@app.route('/')
def index():
    return "Analyst Bot is Running"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_server).start()
    print("Bot is live...")
    bot.infinity_polling()
