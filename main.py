import os
import telebot
import google.generativeai as genai
from flask import Flask
from threading import Thread
from PIL import Image
import io

# --- CONFIGURATION ---
# Set these in Render.com Dashboard -> Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Initialize Telegram Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# Initialize Flask (Required for Render to stay alive)
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
def handle_photo(message):
    try:
        bot.reply_to(message, "🧠 Elite Blackbox is scanning the field...")

        # 1. Download photo from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 2. Convert to PIL Image for Gemini
        img = Image.open(io.BytesIO(downloaded_file))

        # 3. Call Gemini API
        response = model.generate_content([ULTRA_PRO_PROMPT, img])
        
        # 4. Reply with analysis
        bot.reply_to(message, response.text)

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "⚽ ULTRA PRO MAX LEGEND ANALYST ACTIVE.\nSend me a screenshot of the matches.")

# --- RENDER DEPLOYMENT HELPERS ---
@app.route('/')
def health_check():
    return "Bot is online!", 200

def run_flask():
    # Render provides the PORT env var automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Start the Flask web server in a background thread
    Thread(target=run_flask).start()
    # Start the Telegram Bot polling
    print("Bot is polling...")
    bot.infinity_polling()
