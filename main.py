import os
import telebot
import base64
from flask import Flask
from threading import Thread
from openai import OpenAI

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

app = Flask('')

# --- THE ELITE BLACKBOX LOGIC (INTERNAL ONLY) ---
ULTRA_PRO_PROMPT = """
ROLE: Elite Virtual Football Blackbox.
TASK: Extract the single highest-probability scoring match.

INTERNAL FILTERS:
1. Structural Balance: Table proximity ≤ 2, Points Gap ≤ 4, Both teams in Top 12.
2. Legend Filter: Both teams GF > 1.5/match, GA > 1.2/match. Fail if failed to score in 2 of last 5.
3. Volatility: Target High GF + High GA. Avoid strong defenses.

STRICT OUTPUT INSTRUCTIONS:
- If a match meets ALL criteria, output ONLY the Match, BTTS/Over 3.5, and Confidence.
- DO NOT provide the statistical breakdown or reasoning.
- If no match qualifies, output: ❌ NO PICK (Reason: [Short Reason])

REQUIRED FORMAT:
MATCH: [Team A vs Team B]
MARKET: BTTS: YES | OVER 3.5: [YES/NO]
CONFIDENCE: 🔥 HIGH (95%+)
"""

@bot.message_handler(content_types=['photo'])
def handle_vision_analysis(message):
    try:
        bot.reply_to(message, "⚡ Running Ultra Pro Max Legend Analysis...")
        
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://render.com", 
                "X-Title": "Football Analyst Bot",
            },
            model="openrouter/auto",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ULTRA_PRO_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": { "url": f"data:image/jpeg;base64,{base64_image}" }
                        }
                    ]
                }
            ]
        )

        analysis_result = response.choices[0].message.content
        bot.reply_to(message, analysis_result.strip())

    except Exception as e:
        bot.reply_to(message, f"❌ System Error: {str(e)}")

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "⚽ **ULTRA PRO MAX LEGEND ANALYST**\nSystem Status: ⚡ ONLINE\nSend your fixture screenshot.")

# --- MINIMAL FLASK FOR CRON-JOB.ORG SUCCESS ---
@app.route('/')
def health_check():
    # Returns only 2 bytes to prevent "Output Too Large" error
    return "OK", 200

def run_flask_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    t = Thread(target=run_flask_server)
    t.daemon = True
    t.start()
    
    print("Bot starting...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
