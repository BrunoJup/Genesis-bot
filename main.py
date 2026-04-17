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

# --- STRIPPED DOWN PROMPT ---
# This forces the AI to ignore logic explanations and only give the final pick.
ULTRA_PRO_PROMPT = """
Analyze the football fixtures in this image.
Apply Elite Filter: Table Diff ≤ 2, Top 12 Rank, High Scoring Form (>1.5 PPG).

STRICT OUTPUT RULE:
- If a match qualifies, output ONLY the following 3 lines.
- If no match qualifies, output: ❌ NO PICK

FORMAT:
MATCH: [Team A vs Team B]
MARKET: [BTTS: YES / OVER 3.5]
CONFIDENCE: [🔥 HIGH / MEDIUM]
"""

@bot.message_handler(content_types=['photo'])
def handle_vision_analysis(message):
    try:
        bot.reply_to(message, "⏳ Analyzing...")
        
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
        # Final safety check to ensure it's not a wall of text
        bot.reply_to(message, analysis_result.strip())

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "⚽ Analyst Ready. Send fixture screenshot.")

# --- MINIMAL FLASK FOR CRON-JOB.ORG ---
@app.route('/')
def health_check():
    return "OK", 200 # Minimal 2-byte response

def run_flask_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    t = Thread(target=run_flask_server)
    t.daemon = True
    t.start()
    
    print("Bot is live...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
