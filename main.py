import os
import logging
import requests
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.onrender.com

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VISION_MODEL = "openai/gpt-4o-mini"

logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────
conn = sqlite3.connect("predictions.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_name TEXT,
    market TEXT,
    odd REAL,
    result TEXT,
    created_at TEXT
)
""")
conn.commit()

# ─────────────────────────────────────────────
# STRATEGY ENGINE
# ─────────────────────────────────────────────
def agent_chloe_analysis(data):
    try:
        m1 = data["match1"]
        m2 = data["match2"]

        combos = {
            "O/O": m1["over"] * m2["over"],
            "O/U": m1["over"] * m2["under"],
            "U/O": m1["under"] * m2["over"],
            "U/U": m1["under"] * m2["under"]
        }

        in_3_range = {k: v for k, v in combos.items() if 3.0 <= v < 4.0}

        if len(in_3_range) != 3:
            return None

        sorted_vals = sorted(in_3_range.items(), key=lambda x: x[1])
        median_combo, _ = sorted_vals[1]

        mapping = {
            "O/O": [(m1["name"], "Over", m1["over"]),
                    (m2["name"], "Over", m2["over"])],
            "O/U": [(m1["name"], "Over", m1["over"]),
                    (m2["name"], "Under", m2["under"])],
            "U/O": [(m1["name"], "Under", m1["under"]),
                    (m2["name"], "Over", m2["over"])],
            "U/U": [(m1["name"], "Under", m1["under"]),
                    (m2["name"], "Under", m2["under"])],
        }

        selected = mapping[median_combo]
        best_pick = min(selected, key=lambda x: x[2])

        match_name, market, odd = best_pick

        return {
            "match_name": match_name,
            "market": f"{market} Goals",
            "odd": odd,
            "combo": median_combo
        }

    except:
        return None


# ─────────────────────────────────────────────
# SAVE PREDICTION
# ─────────────────────────────────────────────
def save_prediction(pred):
    cursor.execute("""
    INSERT INTO predictions (match_name, market, odd, result, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (
        pred["match_name"],
        pred["market"],
        pred["odd"],
        "PENDING",
        datetime.utcnow().isoformat()
    ))
    conn.commit()


# ─────────────────────────────────────────────
# VISION EXTRACTION
# ─────────────────────────────────────────────
def extract_data_from_image(image_url):
    prompt = """
Extract 2 matches with Over/Under odds.

Return ONLY JSON:
{
  "match1": {"name": "...", "over": 1.85, "under": 1.95},
  "match2": {"name": "...", "over": 1.90, "under": 1.88}
}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
    }

    r = requests.post(OPENROUTER_URL, headers=headers, json=payload)

    try:
        import json
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        return None


# ─────────────────────────────────────────────
# TELEGRAM HANDLER
# ─────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_url = file.file_path

    await update.message.reply_text("🔍 Processing...")

    data = extract_data_from_image(image_url)

    if not data:
        await update.message.reply_text("❌ Failed to read image.")
        return

    pred = agent_chloe_analysis(data)

    if not pred:
        await update.message.reply_text('❌ "Strategy conditions not met"')
        return

    save_prediction(pred)

    response = f"""🔥 **FINAL VERDICT:**

**{pred['match_name']} — {pred['market']} @ {pred['odd']}**

📌 *Reason:* Based on stable median clustering and filtered odds structure. The {pred['combo']} combination yielded the perfect median marker, and extracting the smallest individual risk component points directly to the {pred['match_name'].split()[0]} market."""

    await update.message.reply_text(response, parse_mode="Markdown")


# ─────────────────────────────────────────────
# WEBHOOK SERVER (RENDER READY)
# ─────────────────────────────────────────────
from flask import Flask, request

app = Flask(__name__)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"


@app.route("/")
def home():
    return "Agent Chloe is live 🤖"


# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────
if __name__ == "__main__":
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )
