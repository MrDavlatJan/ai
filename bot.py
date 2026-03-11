import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

banned_users = set()
chat_histories = {}

client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я ИИ-бот. Пиши что хочешь 👋")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        uid = int(context.args[0])
        banned_users.add(uid)
        await update.message.reply_text(f"Пользователь {uid} забанен.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        uid = int(context.args[0])
        banned_users.discard(uid)
        await update.message.reply_text(f"Пользователь {uid} разбанен.")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid in banned_users:
        await update.message.reply_text("Ты заблокирован.")
        return

    # Логируем админу
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"👤 {user.full_name} (id: {uid}):\n{update.message.text}"
            )
        except:
            pass

    text = update.message.text

    if uid not in chat_histories:
        chat_histories[uid] = []

    chat_histories[uid].append({"role": "user", "content": text})

    # Держим только последние 20 сообщений
    if len(chat_histories[uid]) > 20:
        chat_histories[uid] = chat_histories[uid][-20:]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=chat_histories[uid],
        max_tokens=1024
    )

    reply = response.choices[0].message.content
    chat_histories[uid].append({"role": "assistant", "content": reply})

    await update.message.reply_text(reply)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()
