import os
import logging
import base64
from io import BytesIO

import telebot
from PIL import Image
from openai import OpenAI

# LOAD ENV VARIABLES
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# SAFETY CHECK
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN is missing in environment variables")

if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY is missing in environment variables")

# INIT BOT
bot = telebot.TeleBot(TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO)

# AI CLIENT
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# PROMPT
SYSTEM_PROMPT = """
You are an elite football goals analysis engine.
Return ONLY final structured result.
"""

MODELS = [
    "openai/gpt-4o",
    "google/gemini-2.0-pro-exp-02-05"
]


def send_to_ai(image_base64):
    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze screenshot"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Model {model} failed: {e}")
            continue
    return "❌ NO BET"


@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Send screenshot.")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.reply_to(message, "Processing...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        image = Image.open(BytesIO(downloaded_file))
        buffer = BytesIO()
        image.save(buffer, format="JPEG")

        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        result = send_to_ai(image_base64)

        bot.reply_to(message, result)

    except Exception as e:
        logging.error(e)
        bot.reply_to(message, "❌ Error processing image")


if __name__ == "__main__":
    print("Bot running (polling)...")
    bot.infinity_polling()
