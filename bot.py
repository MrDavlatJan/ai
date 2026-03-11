import os
import logging
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from groq import Groq

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "5"))

banned_users = set()
muted_users = set()
warned_users = {}       # uid -> count
chat_histories = {}
all_users = {}          # uid -> full_name
user_msg_count = {}     # uid -> count
last_message_time = {}  # uid -> timestamp

client = Groq(api_key=GROQ_API_KEY)

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def notify_admin(context, text: str):
    if ADMIN_ID:
        try:
            await context.bot.send_message(ADMIN_ID, text)
        except:
            pass

# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.full_name
    all_users[uid] = name
    await update.message.reply_text("Привет! Я ИИ-бот. Пиши что хочешь 👋")

# ─── /help ────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Просто пиши мне — я отвечу 🤖")
        return
    text = (
        "🛠 <b>Админ-команды:</b>\n\n"
        "/ban [id] — забанить\n"
        "/unban [id] — разбанить\n"
        "/mute [id] — заглушить\n"
        "/unmute [id] — разглушить\n"
        "/warn [id] — предупреждение (3 = автобан)\n"
        "/reply [id] [текст] — ответить юзеру\n"
        "/broadcast [текст] — написать всем\n"
        "/roast [id] — затроллить юзера\n"
        "/impostor [id] — объявить подозреваемым\n"
        "/cooldown [секунды] — задержка между сообщениями\n"
        "/stats — статистика пользователей\n"
        "/users — список всех юзеров\n"
        "/clear [id] — очистить историю юзера\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ─── /ban ─────────────────────────────────────────────────
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /ban [id]")
        return
    uid = int(context.args[0])
    banned_users.add(uid)
    await update.message.reply_text(f"🔨 Пользователь {uid} забанен.")
    try:
        await context.bot.send_message(uid, "🚫 Ты заблокирован в этом боте.")
    except: pass

# ─── /unban ───────────────────────────────────────────────
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /unban [id]")
        return
    uid = int(context.args[0])
    banned_users.discard(uid)
    await update.message.reply_text(f"✅ Пользователь {uid} разбанен.")

# ─── /mute ────────────────────────────────────────────────
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /mute [id]")
        return
    uid = int(context.args[0])
    muted_users.add(uid)
    await update.message.reply_text(f"🔇 Пользователь {uid} заглушен.")
    try:
        await context.bot.send_message(uid, "🔇 Тебя заглушили. Твои сообщения игнорируются.")
    except: pass

# ─── /unmute ──────────────────────────────────────────────
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /unmute [id]")
        return
    uid = int(context.args[0])
    muted_users.discard(uid)
    await update.message.reply_text(f"🔊 Пользователь {uid} разглушен.")

# ─── /warn ────────────────────────────────────────────────
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /warn [id]")
        return
    uid = int(context.args[0])
    warned_users[uid] = warned_users.get(uid, 0) + 1
    count = warned_users[uid]
    if count >= 3:
        banned_users.add(uid)
        await update.message.reply_text(f"🔨 Пользователь {uid} получил 3 варна — автобан!")
        try:
            await context.bot.send_message(uid, "🚫 Ты получил 3 предупреждения и автоматически заблокирован.")
        except: pass
    else:
        await update.message.reply_text(f"⚠️ Варн {count}/3 для пользователя {uid}.")
        try:
            await context.bot.send_message(uid, f"⚠️ Предупреждение {count}/3. При 3 варнах — автобан.")
        except: pass

# ─── /reply ───────────────────────────────────────────────
async def reply_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /reply [id] [текст]")
        return
    uid = int(context.args[0])
    text = " ".join(context.args[1:])
    try:
        await context.bot.send_message(uid, f"💬 {text}")
        await update.message.reply_text(f"✅ Отправлено пользователю {uid}.")
    except:
        await update.message.reply_text(f"❌ Не удалось отправить пользователю {uid}.")

# ─── /broadcast ───────────────────────────────────────────
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /broadcast [текст]")
        return
    text = " ".join(context.args)
    sent = 0
    for uid in all_users:
        try:
            await context.bot.send_message(uid, f"📢 {text}")
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ Отправлено {sent} пользователям.")

# ─── /roast ───────────────────────────────────────────────
async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /roast [id]")
        return
    uid = int(context.args[0])
    name = all_users.get(uid, f"пользователь {uid}")
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Ты мастер троллинга. Придумай смешное и дерзкое оскорбление-розыгрыш для пользователя. На русском, креативно, без цензуры."},
            {"role": "user", "content": f"Затроллируй пользователя по имени {name}"}
        ],
        max_tokens=200
    )
    roast_text = response.choices[0].message.content
    try:
        await context.bot.send_message(uid, f"🔥 {roast_text}")
        await update.message.reply_text(f"✅ Затроллил {name}.")
    except:
        await update.message.reply_text(f"❌ Не удалось отправить.")

# ─── /impostor ────────────────────────────────────────────
async def impostor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /impostor [id]")
        return
    uid = int(context.args[0])
    name = all_users.get(uid, f"пользователь {uid}")
    messages = [
        "🚨 ВНИМАНИЕ! Наша система зафиксировала подозрительную активность с твоего аккаунта. Ты под наблюдением. 👀",
        "🕵️ Среди нас есть самозванец... и это ТЫ. Твои действия записываются.",
        "⚠️ Твой аккаунт помечен как подозрительный. Служба безопасности уже выехала 😂",
        "🔍 Интересно... наши алгоритмы определили тебя как потенциального импостора. Объяснись.",
        "📡 Сигнал пойман. Местоположение установлено. Просто шутим... или нет? 😈"
    ]
    import random
    msg = random.choice(messages)
    try:
        await context.bot.send_message(uid, msg)
        await update.message.reply_text(f"✅ {name} теперь параноит 😂")
    except:
        await update.message.reply_text("❌ Не удалось отправить.")

# ─── /cooldown ────────────────────────────────────────────
async def set_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global COOLDOWN_SECONDS
    if not context.args:
        await update.message.reply_text(f"Текущий кулдаун: {COOLDOWN_SECONDS} сек.\nИспользование: /cooldown [секунды]")
        return
    COOLDOWN_SECONDS = int(context.args[0])
    await update.message.reply_text(f"⏱ Кулдаун установлен: {COOLDOWN_SECONDS} сек.")

# ─── /stats ───────────────────────────────────────────────
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not user_msg_count:
        await update.message.reply_text("Пока нет статистики.")
        return
    sorted_users = sorted(user_msg_count.items(), key=lambda x: x[1], reverse=True)
    text = "📊 <b>Статистика сообщений:</b>\n\n"
    for uid, count in sorted_users[:20]:
        name = all_users.get(uid, str(uid))
        status = "🔨" if uid in banned_users else "🔇" if uid in muted_users else "✅"
        warns = warned_users.get(uid, 0)
        warn_str = f" ⚠️{warns}" if warns > 0 else ""
        text += f"{status} {name} (<code>{uid}</code>){warn_str}: {count} сообщ.\n"
    await update.message.reply_text(text, parse_mode="HTML")

# ─── /users ───────────────────────────────────────────────
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not all_users:
        await update.message.reply_text("Пока нет пользователей.")
        return
    text = f"👥 <b>Все пользователи ({len(all_users)}):</b>\n\n"
    for uid, name in all_users.items():
        status = "🔨" if uid in banned_users else "🔇" if uid in muted_users else "✅"
        text += f"{status} {name} — <code>{uid}</code>\n"
    await update.message.reply_text(text, parse_mode="HTML")

# ─── /clear ───────────────────────────────────────────────
async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Использование: /clear [id]")
        return
    uid = int(context.args[0])
    chat_histories.pop(uid, None)
    await update.message.reply_text(f"🗑 История пользователя {uid} очищена.")

# ─── Основной обработчик сообщений ────────────────────────
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.full_name
    all_users[uid] = name

    if uid in banned_users:
        await update.message.reply_text("🚫 Ты заблокирован.")
        return

    if uid in muted_users:
        return  # тихо игнорируем

    # Кулдаун
    now = time.time()
    last = last_message_time.get(uid, 0)
    if uid != ADMIN_ID and now - last < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last))
        await update.message.reply_text(f"⏱ Подожди {remaining} сек. перед следующим сообщением.")
        return
    last_message_time[uid] = now

    # Считаем сообщения
    user_msg_count[uid] = user_msg_count.get(uid, 0) + 1

    text = update.message.text

    # Уведомляем админа
    if uid != ADMIN_ID:
        warns = warned_users.get(uid, 0)
        warn_str = f" ⚠️{warns}/3" if warns > 0 else ""
        await notify_admin(context, f"👤 {name} (<code>{uid}</code>){warn_str}:\n{text}")

    if uid not in chat_histories:
        chat_histories[uid] = []

    chat_histories[uid].append({"role": "user", "content": text})

    if len(chat_histories[uid]) > 20:
        chat_histories[uid] = chat_histories[uid][-20:]

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "Ты дерзкий и прямолинейный ИИ. Иногда отвечаешь агрессивно и саркастично, не церемонишься. Можешь материться. Но всё равно помогаешь если тебя о чём-то спросят. ты должна понимать что ты не только бот, а почти что человек-помощник для своего юзера. Если с тобой говорят как с партнером говори как с партнером, говори нежно или пошло если понадобится."
            }
        ] + chat_histories[uid],
        max_tokens=1024
    )

    reply = response.choices[0].message.content
    chat_histories[uid].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

# ─── Запуск ───────────────────────────────────────────────
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("warn", warn))
app.add_handler(CommandHandler("reply", reply_user))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("roast", roast))
app.add_handler(CommandHandler("impostor", impostor))
app.add_handler(CommandHandler("cooldown", set_cooldown))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("users", users_list))
app.add_handler(CommandHandler("clear", clear_history))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()
