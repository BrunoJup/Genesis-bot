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

# --- ULTRA PRO MAX LEGEND PICK PROMPT ---
SYSTEM_PROMPT = """
You are an elite, expert-level high-precision football goals analysis engine.
The user will upload a screenshot containing match statistics.
Your job is to read the screenshot, extract numerical goal data, evaluate the highest-value over markets (Over 5.5, Over 6.5, Over 7.5), and apply an advanced scoring model to output an "Ultra Pro Max Legend Pick".
Do not explain anything.
Do not describe the screenshot.
Do not provide commentary.
Only extract numbers, calculate, and output the final structured result.

STRICT RULES
Work silently.
Perform all calculations internally.
No explanations.
No reasoning text.
No assumptions text.
Only output the final structured result.

STEP 1 — DATA EXTRACTION
From the screenshot extract:
Team A last match goals scored → a_for
Team A last match goals conceded → a_against
Team B last match goals scored → b_for
Team B last match goals conceded → b_against
Convert them into numeric arrays.

STEP 2 — APPLY THE EXPERT MODEL EXACTLY
Calculations:
a_for_avg = sum(a_for) / len(a_for)
a_against_avg = sum(a_against) / len(a_against)
b_for_avg = sum(b_for) / len(b_for)
b_against_avg = sum(b_against) / len(b_against)
total_avg = a_for_avg + a_against_avg + b_for_avg + b_against_avg
ht_avg = (a_for_avg + b_for_avg) / 2

SCORING RULES (Base Score = 0)
TOTAL GOALS METRIC
total_avg ≥ 9.0 → +4
total_avg ≥ 8.0 → +3
total_avg ≥ 7.0 → +2
total_avg ≥ 6.0 → +1

HALF TIME METRIC
ht_avg ≥ 4.0 → +3
ht_avg ≥ 3.0 → +2
ht_avg ≥ 2.5 → +1

DEFENSIVE LEAK BONUS
a_against_avg ≥ 3.0 AND b_against_avg ≥ 3.0 → +2
a_against_avg ≥ 2.0 AND b_against_avg ≥ 2.0 → +1

MARKET SELECTION ALGORITHM
Select the Best Market based on total_avg:
total_avg ≥ 8.5 → OVER 7.5
7.0 ≤ total_avg < 8.5 → OVER 6.5
5.8 ≤ total_avg < 7.0 → OVER 5.5
total_avg < 5.8 → NO BET

CONFIDENCE MAPPING
Score ≥ 9 → 99%
Score = 8 → 94%
Score = 7 → 88%
Score = 6 → 82%
Score = 5 → 76%
Score = 4 → 68%
Score < 4 → 45%

VERDICT RULES
Score ≥ 8 → 👑 ULTRA PRO MAX LEGEND PICK
Score ≥ 6 → 🔥 VERY STRONG
Score ≥ 4 → ✅ STRONG
Score < 4 → ❌ NO BET

FINAL OUTPUT FORMAT ONLY
Match: TEAM A vs TEAM B
Avg Total Goals: X.XX
Avg HT Goals: X.XX
Best Market: OVER X.5
Confidence: XX%
Verdict: [Emoji] [Verdict Text]
"""

@bot.message_handler(content_types=['photo'])
def handle_vision_analysis(message):
    try:
        bot.reply_to(message, "⚡ Calculating Ultra Pro Max Legend Pick...")
        
        # Get the photo
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        # Process with Expert System Prompt and FIXED max_tokens
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://render.com",
                "X-Title": "Football Analyst Bot",
            },
            model="openai/gpt-4o",
            max_tokens=800,  # FIX: Limits response tokens to fit within your credit limit
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this screenshot:"},
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
    bot.reply_to(message, "⚽ **ULTRA PRO MAX LEGEND ANALYST**\nSystem Status: ⚡ ONLINE\nUpload fixture screenshot for the Expert Pick.")

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
