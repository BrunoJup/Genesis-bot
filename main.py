import os
import telebot
import base64
import io
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

# Your Elite Analysis Prompt
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
def handle_vision_analysis(message):
    try:
        bot.reply_to(message, "🧠 Elite Blackbox is processing... Using OpenRouter Auto-Analyst.")

        # 1. Get the photo from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 2. Encode to Base64
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        # 3. Request analysis
        # Using "openrouter/auto" lets OpenRouter decide, 
        # but we add "google/gemini-2.0-flash-001" as a primary choice for vision speed.
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://render.com", 
                "X-Title": "Football Analyst Bot",
            },
            model="openrouter/auto", # This changes the model automatically based on prompt
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

        analysis_result = response.choices[0].message.content
        bot.reply_to(message, analysis_result)

    except Exception as e:
        bot.reply_to(message, f"❌ Analysis Error: {str(e)}\nMake sure your OpenRouter credits are sufficient.")

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "⚽ **ULTRA PRO MAX LEGEND VIRTUAL ANALYST v2**\n\nStatus: ONLINE\nReady for screenshots.")

# --- RENDER SERVER SETUP ---
@app.route('/')
def health_check():
    return "Bot is Alive", 200

def run_flask_server():
    # Render maps port automatically via environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Run Flask in background thread to satisfy Render's web service requirement
    Thread(target=run_flask_server).start()
    print("Bot is starting...")
    bot.infinity_polling()
