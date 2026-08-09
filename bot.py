import logging
import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === НАСТРОЙКИ ===
BOT_TOKEN = "8856132966:AAF_rF0buTVJO2WWc44IyC3eEvxAOPq9qGE"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

chat_history = {}

# === ВЕБ-СЕРВЕР ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    app.run(host='0.0.0.0', port=PORT)


# === ИИ-ФУНКЦИЯ ===

def ask_ai(user_id, message):
    """Отправляет запрос к Groq API (бесплатно)."""
    if not GROQ_API_KEY:
        return None
    
    try:
        if user_id not in chat_history:
            chat_history[user_id] = [
                {"role": "system", "content": "Ты — полезный ассистент. Отвечай на русском языке."}
            ]
        
        chat_history[user_id].append({"role": "user", "content": message})
        
        if len(chat_history[user_id]) > 21:
            chat_history[user_id] = [chat_history[user_id][0]] + chat_history[user_id][-20:]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": chat_history[user_id],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=20)
        
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            chat_history[user_id].append({"role": "assistant", "content": reply})
            return reply
        else:
            logger.error(f"Groq ошибка: {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"Groq ошибка: {e}")
        return None


# === КОМАНДЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 Привет! Я **НейроДруг** — твой личный ИИ-помощник!\n\n"
        "💬 Просто напиши мне что-нибудь — я отвечу!\n\n"
        "Команды:\n"
        "/new — новый диалог\n"
        "/help — помощь",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 **НейроДруг — помощь**\n\n"
        "Просто напиши сообщение — я отвечу!\n"
        "Я помню контекст диалога.\n\n"
        "/start — главное меню\n"
        "/new — очистить историю\n"
        "/help — справка",
        parse_mode="Markdown"
    )


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in chat_history:
        del chat_history[user_id]
    await update.message.reply_text("🆕 Новый диалог! Всё забыто.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    
    reply = ask_ai(user_id, user_message)
    
    if not reply:
        reply = "😔 Извини, сейчас не могу ответить. Попробуй позже."
    
    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i:i+4096])
    else:
        await update.message.reply_text(reply)


def main():
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🧠 НейроДруг запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
