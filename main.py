import os
import base64
import json
import requests
from dataclasses import dataclass
from typing import List, Dict
from statistics import mean

from fastapi import FastAPI, UploadFile, File, Request
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# =========================
# CONFIG
# =========================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com/webhook

MODEL = "openai/gpt-4o-mini"

# =========================
# DATA STRUCTURE
# =========================
@dataclass
class Fixture:
    match: str
    a_for: List[float]
    a_against: List[float]
    b_for: List[float]
    b_against: List[float]

# =========================
# ENGINE
# =========================
class Engine:
    def avg(self, v): return round(mean(v), 2)

    def analyze(self, f: Fixture) -> Dict:
        a_att = self.avg(f.a_for)
        b_att = self.avg(f.b_for)
        a_def = self.avg(f.a_against)
        b_def = self.avg(f.b_against)

        total = round(a_att + b_att + a_def + b_def, 2)
        ht = round((a_att + b_att) / 2, 2)

        score = 0
        if total >= 7: score += 3
        elif total >= 5: score += 2
        elif total >= 4: score += 1

        if ht >= 2.5: score += 2
        elif ht >= 2.0: score += 1

        if a_def >= 2.5 and b_def >= 2.5:
            score += 1

        if score >= 5:
            market = "Over 2.5"
        elif score >= 3:
            market = "Over 1.5"
        else:
            market = "NO BET"

        confidence = min(95, 50 + score * 10)

        return {
            "match": f.match,
            "market": market,
            "confidence": confidence,
            "goal_projection": total,
            "ht_projection": ht
        }

engine = Engine()

# =========================
# OPENROUTER VISION
# =========================
def extract_fixture(image_bytes: bytes) -> Fixture:
    img_b64 = base64.b64encode(image_bytes).decode()

    prompt = """
Extract football stats from image.

Return STRICT JSON:
{
 "match": "...",
 "a_for": [x,x,x,x,x],
 "a_against": [x,x,x,x,x],
 "b_for": [x,x,x,x,x],
 "b_against": [x,x,x,x,x]
}
"""

    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    }
                ]
            }]
        },
        timeout=60
    )

    data = res.json()
    content = data["choices"][0]["message"]["content"]

    # clean markdown if exists
    content = content.replace("```json", "").replace("```", "").strip()

    parsed = json.loads(content)
    return Fixture(**parsed)

# =========================
# TELEGRAM SETUP
# =========================
app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)

telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()

        img_bytes = await file.download_as_bytearray()

        fixture = extract_fixture(img_bytes)
        result = engine.analyze(fixture)

        if result["market"] == "NO BET":
            msg = f"❌ NO BET\n\nMatch: {result['match']}"
        else:
            msg = f"""🔥 BET SIGNAL

Match: {result['match']}
Market: {result['market']}
Confidence: {result['confidence']}%

Goals: {result['goal_projection']}
HT: {result['ht_projection']}
"""

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# =========================
# WEBHOOK ENDPOINT
# =========================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)

    await telegram_app.initialize()
    await telegram_app.process_update(update)

    return {"ok": True}

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def home():
    return {"status": "Webhook bot running"}

# =========================
# STARTUP: SET WEBHOOK
# =========================
@app.on_event("startup")
async def startup():
    await bot.set_webhook(WEBHOOK_URL)
    print("✅ Webhook set")
