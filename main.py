import os
import base64
import json
import requests
import asyncio
from dataclasses import dataclass
from typing import List, Dict
from statistics import mean

from fastapi import FastAPI, UploadFile, File
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# =========================
# CONFIG
# =========================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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

        stake = 0
        if market != "NO BET":
            stake = round(confidence / 100 * 5, 2)

        return {
            "match": f.match,
            "market": market,
            "confidence": confidence,
            "stake_units": stake,
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

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        return Fixture(**parsed)

    except Exception as e:
        raise ValueError(f"Parsing failed: {e} | Raw: {data}")

# =========================
# FASTAPI
# =========================
app = FastAPI()

@app.get("/")
def home():
    return {"status": "RUNNING"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    img = await file.read()
    fixture = extract_fixture(img)
    result = engine.analyze(fixture)

    return {
        "fixture": fixture.__dict__,
        "analysis": result
    }

# =========================
# TELEGRAM BOT
# =========================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()

        path = "tmp.jpg"
        await file.download_to_drive(path)

        with open(path, "rb") as f:
            img = f.read()

        fixture = extract_fixture(img)
        result = engine.analyze(fixture)

        if result["market"] == "NO BET":
            msg = f"""
❌ NO BET

Match: {result['match']}
Projection: {result['goal_projection']}
"""
        else:
            msg = f"""
🔥 BET SIGNAL

Match: {result['match']}
Market: {result['market']}

Confidence: {result['confidence']}%
Stake: {result['stake_units']} units

Goals: {result['goal_projection']}
HT: {result['ht_projection']}
"""

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send screenshot 📸")


async def run_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.COMMAND, start))

    print("🤖 BOT STARTED")

    await app_bot.initialize()
    await app_bot.start()
    await app_bot.updater.start_polling()

# =========================
# STARTUP EVENT (FIX)
# =========================
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

# =========================
# ENTRYPOINT (FIX)
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
