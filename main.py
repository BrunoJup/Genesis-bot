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

# --- GOD MODE SCORING ENGINE PROMPT ---
# Strictly configured for highest dominance analysis only.
ULTRA_PRO_PROMPT = """
ROLE: Elite God Mode Football Scoring Engine.
TASK: Analyze the provided fixture image using the God Mode scoring engine. 

INSTRUCTIONS:
1. Identify all matches in the image.
2. Evaluate each match against the God Mode criteria (Total Avg, HT Pace, Defensive Vulnerability, Consistency).
3. Select the SINGLE match with the highest confidence score.
4. Output ONLY the data for that top-tier match.

STRICT OUTPUT FORMAT:
MATCH: [Team A vs Team B]
MARKET: [Market Label]
CONFIDENCE: [X]%
VERDICT: [Verdict Label]

- NO reasoning.
- NO statistical breakdown.
- If no match reaches the minimum confidence threshold, output ONLY: ❌ NO QUALIFYING MATCHES.
"""

@bot.message_handler(content_types=['photo'])
def handle_vision_analysis(message):
    try:
        bot.reply_to(message, "⚡ Calculating God Mode Analysis...")
        
        # Get the photo
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        # Process with God Mode Prompt
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
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
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
    bot.reply_to(message, "⚽ **GOD MODE LEGEND ANALYST**\nSystem Status: ⚡ ONLINE\nSend your fixture screenshot for the highest probability pick.")

# --- MINIMAL FLASK FOR CRON-JOB.ORG ---
@app.route('/')
def health_check():
    return "OK", 200

def run_flask_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Start web server for uptime
    t = Thread(target=run_flask_server)
    t.daemon = True
    t.start()
    
    print("Bot starting...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
