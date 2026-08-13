import logging
import os
import requests
from flask import Flask, request
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

@app.route('/chat.html')
def chat_page():
    with open('chat.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    user_message = data.get('message', '')
    user_id = data.get('user_id', 0)
    reply = ask_ai(str(user_id), user_message)
    return {"reply": reply or "Не могу ответить"}

def run_web_server():
    app.run(host='0.0.0.0', port=PORT)


# === ИИ-ФУНКЦИЯ (без ключей) ===

def ask_ai(user_id, message):
    """Бесплатный ИИ через открытые API."""
    
    # Способ 1: DuckDuckGo AI Chat (без ключа)
    try:
        status_resp = requests.get(
            "https://duckduckgo.com/duckchat/v1/status",
            headers={"x-vqd-accept": "1"},
            timeout=10
        )
        token = status_resp.headers.get("x-vqd-4", "")
        
        if token:
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
                            import json
                            chunk = json.loads(line[6:])
                            if "message" in chunk:
                                result += chunk.get("message", "")
                        except:
                            pass
                if result.strip():
                    return result.strip()
    except:
        pass
    
    # Способ 2: OpenRouter бесплатные модели (без ключа)
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        data = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [{"role": "user", "content": message}]
        }
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    
    return None


# === КОМАНДЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Открыть чат", web_app={"url": "https://neurodrug.onrender.com/chat.html"})],
        [InlineKeyboardButton("📋 Команды", callback_data="show_commands")]
    ])
    
    await update.message.reply_text(
        "🧠 Привет! Я **НейроДруг** — твой личный ИИ-помощник!\n\n"
        "💬 Напиши мне что-нибудь или открой красивый чат!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def show_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📋 **Команды:**\n\n"
        "/start — главное меню\n"
        "/new — новый диалог\n"
        "/help — помощь\n\n"
        "💬 Или просто напиши мне сообщение!",
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
    application.add_handler(CallbackQueryHandler(show_commands, pattern="show_commands"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🧠 НейроДруг запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
