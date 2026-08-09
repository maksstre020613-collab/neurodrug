import logging
import os
import json
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


# === ИИ-ФУНКЦИИ ===

def ask_ai(message):
    """Основной ИИ через DuckDuckGo."""
    try:
        status_resp = requests.get(
            "https://duckduckgo.com/duckchat/v1/status",
            headers={"x-vqd-accept": "1"},
            timeout=10
        )
        token = status_resp.headers.get("x-vqd-4", "")
        if not token:
            return None
        
        headers = {
            "Content-Type": "application/json",
            "x-vqd-4": token
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": message}]
        }
        resp = requests.post(
            "https://duckduckgo.com/duckchat/v1/chat",
            headers=headers,
            json=data,
            timeout=20
        )
        if resp.status_code == 200:
            result = ""
            for line in resp.text.split("\n"):
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        if "message" in chunk:
                            result += chunk.get("message", "")
                    except:
                        pass
            return result.strip() if result.strip() else None
        return None
    except:
        return None


def ask_backup(message):
    """Запасной ИИ через Gemini."""
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        params = {"key": "AIzaSyBdK0LQ8xXH3QmJk9Y0vZ2wN5bXq7cU1Rg"}
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": message}]}]
        }
        resp = requests.post(url, params=params, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
        return None
    except:
        return None


def ask_simple(message):
    """Простые ответы."""
    msg = message.lower()
    
    if any(w in msg for w in ["привет", "здравствуй", "hello", "hi", "ку"]):
        return "👋 Привет! Я НейроДруг. Задай мне вопрос или просто поболтаем!"
    
    if "как дела" in msg:
        return "😊 У меня всё отлично! Готов помочь. А у тебя как?"
    
    if "что ты умеешь" in msg or "что ты можешь" in msg:
        return (
            "🤖 Я умею:\n"
            "💬 Общаться на любые темы\n"
            "📝 Писать тексты и код\n"
            "🤔 Отвечать на вопросы\n"
            "📚 Объяснять сложные вещи\n\n"
            "Просто напиши мне!"
        )
    
    if any(w in msg for w in ["спасибо", "благодарю"]):
        return "Всегда пожалуйста! Обращайся ещё! 😊"
    
    if any(w in msg for w in ["пока", "до встречи"]):
        return "До встречи! Буду ждать! 👋"
    
    if "?" in msg:
        return (
            "🤔 Интересный вопрос! Попробуй переформулировать или спроси что-то ещё.\n"
            "Я постоянно учусь новому!"
        )
    
    return (
        "📝 Я понял твоё сообщение.\n"
        "Попробуй спросить позже или задай другой вопрос!"
    )


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
    
    reply = ask_ai(user_message)
    
    if not reply:
        reply = ask_backup(user_message)
    
    if not reply:
        reply = ask_simple(user_message)
    
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
