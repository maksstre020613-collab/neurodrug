import logging
import os
import re
import random
import requests
from datetime import datetime
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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

chat_history = {}
notes_storage = {}
reminders = []

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


# === ОЧИСТКА MARKDOWN ===

def clean_markdown(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        if line.strip().startswith('|') and '---' in line:
            continue
        if line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            cleaned.append(' • '.join(parts))
            continue
        cleaned.append(line)
    text = '\n'.join(cleaned)
    text = re.sub(r'^#{1,3}\s+', '📌 ', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


# === ИИ ===

def ask_ai(user_id, message):
    if not GROQ_API_KEY:
        return None
    try:
        if user_id not in chat_history:
            chat_history[user_id] = [
                {"role": "system", "content": "Ты — НейроДруг. Отвечай на русском. Не используй таблицы. Используй списки и эмодзи."}
            ]
        chat_history[user_id].append({"role": "user", "content": message})
        if len(chat_history[user_id]) > 21:
            chat_history[user_id] = [chat_history[user_id][0]] + chat_history[user_id][-20:]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        data = {
            "model": "openai/gpt-oss-120b",
            "messages": chat_history[user_id],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=20)
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            reply = clean_markdown(reply)
            chat_history[user_id].append({"role": "assistant", "content": reply})
            return reply
        return None
    except:
        return None


# === СЛУЖЕБНЫЕ ФУНКЦИИ ===

def get_weather(city):
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=10)
        return resp.text.strip()
    except:
        return "Не удалось получить погоду"

def get_currency():
    try:
        resp = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        data = resp.json()
        return f"💵 USD: 1\n💶 EUR: {data['rates']['EUR']:.2f}\n🇷🇺 RUB: {data['rates']['RUB']:.2f}"
    except:
        return "Не удалось получить курсы"

def get_wiki(query):
    try:
        resp = requests.get(f"https://ru.wikipedia.org/api/rest_v1/page/summary/{query}", timeout=10)
        data = resp.json()
        return f"📖 *{data.get('title', query)}*\n\n{data.get('extract', 'Не найдено')[:500]}"
    except:
        return "Не удалось найти статью"

def translate_text(text, target="английский"):
    langs = {"английский": "en", "русский": "ru", "немецкий": "de", "французский": "fr"}
    lang_code = langs.get(target.lower(), "en")
    try:
        resp = requests.get(f"https://api.mymemory.translated.net/get?q={text}&langpair=ru|{lang_code}", timeout=10)
        data = resp.json()
        return data["responseData"]["translatedText"]
    except:
        return "Не удалось перевести"

facts = [
    "🎯 Пчёлы могут узнавать человеческие лица!",
    "🌍 Земля — единственная планета, не названная в честь бога.",
    "🧠 Мозг использует 20% всей энергии тела.",
    "🍯 Мёд никогда не портится.",
    "🐙 У осьминогов три сердца.",
    "❄️ Снежинки имеют 6 лучей.",
    "🎵 Музыка улучшает память.",
    "⭐ Солнце — звезда среднего размера.",
    "🦈 Акулы существуют дольше деревьев.",
    "💡 Свет от Солнца до Земли идёт 8 минут.",
]

jokes = [
    "😂 Почему программисты не ходят в лес? Там баги!",
    "😂 Почему компьютер чихает? У него вирус!",
    "😂 Как называется боязнь гигантских чисел? Гуголфобия!",
    "😂 Почему скелет не пошёл на вечеринку? Ему было не в чем идти!",
    "😂 Что сказал ноль восьмёрке? Классный пояс!",
]


# === ОСНОВНЫЕ КОМАНДЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Открыть чат", web_app={"url": "https://neurodrug.onrender.com/chat.html"})],
        [InlineKeyboardButton("📋 Команды", callback_data="show_commands")]
    ])
    await update.message.reply_text(
        "🧠 Привет! Я *НейроДруг* — твой личный ИИ-помощник!\n\n"
        "💬 Напиши мне что-нибудь или открой красивый чат!",
        parse_mode="Markdown", reply_markup=keyboard
    )

async def show_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📋 *Команды:*\n\n"
        "/start — главное меню\n"
        "/new — новый диалог\n"
        "/help — помощь\n"
        "/random 1-100 — случайное число\n"
        "/coin — подбросить монетку\n"
        "/time — текущее время\n"
        "/date — сегодняшняя дата\n"
        "/calc 2+2 — калькулятор\n"
        "/fact — случайный факт\n"
        "/joke — шутка\n"
        "/weather Москва — погода\n"
        "/currency — курсы валют\n"
        "/note текст — сохранить заметку\n"
        "/mynotes — мои заметки\n"
        "/wiki запрос — википедия\n"
        "/translate фраза — перевод\n"
        "/game — угадай число",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_commands(update, context)

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in chat_history:
        del chat_history[user_id]
    await update.message.reply_text("🆕 Новый диалог! Всё забыто.")


# === ФУНКЦИИ КОМАНД ===

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎲 Используйте: /random 1-100")
        return
    parts = context.args[0].split('-')
    try:
        a, b = int(parts[0]), int(parts[1])
        result = random.randint(a, b)
        await update.message.reply_text(f"🎲 Случайное число: *{result}*", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Формат: /random 1-100")

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
    await update.message.reply_text(result)

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%H:%M:%S")
    await update.message.reply_text(f"⏰ Текущее время: *{now}*", parse_mode="Markdown")

async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().strftime("%d.%m.%Y")
    await update.message.reply_text(f"📅 Сегодня: *{today}*", parse_mode="Markdown")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🔢 Используйте: /calc 2+2")
        return
    expr = " ".join(context.args)
    try:
        result = eval(expr)
        await update.message.reply_text(f"🔢 {expr} = *{result}*", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Неверное выражение")

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(facts))

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(jokes))

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else "Moscow"
    result = get_weather(city)
    await update.message.reply_text(f"🌤 Погода в *{city}*: {result}", parse_mode="Markdown")

async def currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = get_currency()
    await update.message.reply_text(result)

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("📝 Используйте: /note ваш текст")
        return
    if user_id not in notes_storage:
        notes_storage[user_id] = []
    notes_storage[user_id].append(text)
    await update.message.reply_text(f"✅ Заметка сохранена!\nНомер: {len(notes_storage[user_id])}")

async def mynotes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in notes_storage or not notes_storage[user_id]:
        await update.message.reply_text("📭 У вас нет заметок")
        return
    text = "📝 *Ваши заметки:*\n\n"
    for i, note in enumerate(notes_storage[user_id], 1):
        text += f"{i}. {note}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def wiki_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📖 Используйте: /wiki запрос")
        return
    query = "_".join(context.args)
    result = get_wiki(query)
    await update.message.reply_text(result, parse_mode="Markdown")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🌍 Используйте: /translate фраза")
        return
    text = " ".join(context.args)
    result = translate_text(text)
    await update.message.reply_text(f"🌍 Перевод:\n{result}")

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = random.randint(1, 10)
    context.user_data["game_number"] = number
    context.user_data["game_attempts"] = 0
    await update.message.reply_text("🎮 Я загадал число от 1 до 10! Попробуй угадать!\nПиши число в чат.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text

    # Игра "Угадай число"
    if "game_number" in context.user_data:
        try:
            guess = int(user_message)
            context.user_data["game_attempts"] += 1
            number = context.user_data["game_number"]
            if guess == number:
                attempts = context.user_data["game_attempts"]
                await update.message.reply_text(f"🎉 Правильно! Ты угадал за {attempts} попыток!")
                del context.user_data["game_number"]
                del context.user_data["game_attempts"]
                return
            elif guess < number:
                await update.message.reply_text("📈 Больше!")
                return
            else:
                await update.message.reply_text("📉 Меньше!")
                return
        except ValueError:
            pass

    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    reply = ask_ai(user_id, user_message)
    if not reply:
        reply = "😔 Извини, сейчас не могу ответить. Попробуй позже."
    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i:i+4096], parse_mode="Markdown")
    else:
        await update.message.reply_text(reply, parse_mode="Markdown")


def main():
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_chat))
    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("date", date_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("fact", fact_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("currency", currency_command))
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("mynotes", mynotes_command))
    application.add_handler(CommandHandler("wiki", wiki_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("game", game_command))
    application.add_handler(CallbackQueryHandler(show_commands, pattern="show_commands"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🧠 НейроДруг запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
