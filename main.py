import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VISION_MODEL = "openai/gpt-4o-mini"  # vision-capable via OpenRouter

logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────
# AGENT CHLOE CORE STRATEGY (HIDDEN LOGIC)
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
            return '❌ "Strategy conditions not met"'

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

        return f"""🔥 **FINAL VERDICT:**

**{match_name} — {market} Goals @ {odd}**

📌 *Reason:* Based on stable median clustering and filtered odds structure. The {median_combo} combination yielded the perfect median marker, and extracting the smallest individual risk component points directly to the {match_name.split()[0]} market."""
    
    except:
        return "❌ Error processing data."


# ─────────────────────────────────────────────
# VISION: EXTRACT DATA FROM IMAGE USING OPENROUTER
# ─────────────────────────────────────────────
def extract_data_from_image(image_url):
    prompt = """
You are an AI that extracts structured betting data.

From this image, extract:
- Two match names
- Over odds
- Under odds

Return ONLY valid JSON in this format:
{
  "match1": {"name": "...", "over": 1.85, "under": 1.95},
  "match2": {"name": "...", "over": 1.90, "under": 1.88}
}

NO explanation. ONLY JSON.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-app.onrender.com",
        "X-Title": "Agent Chloe"
    }

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)

    result = response.json()

    try:
        content = result["choices"][0]["message"]["content"]

        import json
        return json.loads(content)

    except:
        return None


# ─────────────────────────────────────────────
# TELEGRAM HANDLER (IMAGE)
# ─────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    image_url = file.file_path

    await update.message.reply_text("🔍 Analyzing screenshot...")

    data = extract_data_from_image(image_url)

    if not data:
        await update.message.reply_text("❌ Failed to read image. Try clearer screenshot.")
        return

    result = agent_chloe_analysis(data)

    await update.message.reply_text(result, parse_mode="Markdown")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Agent Chloe Vision Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
