"""
Atham Rent - Akkauntlar holatini boshqaruvchi Telegram bot.

Bot 1 dan TOTAL_ACCOUNTS gacha bo'lgan akkauntlarning holatini
(BOSH / BAND) kuzatib boradi va kanaldagi belgilangan xabarni
avtomatik yangilab turadi.

Ishga tushirish:
    1. @BotFather orqali bot yarating va TOKEN oling.
    2. Muhit o'zgaruvchilarini sozlang:
       - BOT_TOKEN         : bot tokeni
       - ADMIN_ID          : sizning Telegram user ID'ingiz (faqat shu odam buyruq bera oladi)
       - CHANNEL_ID         : kanal ID'si (masalan -1001234567890) yoki @username
    3. Botni kanalga ADMIN qilib qo'shing ("Post messages" va "Edit messages" huquqi bilan).
    4. python arenda_bot.py

Buyruqlar (faqat admin bilan shaxsiy chatda):
    /start                      - botni ishga tushirish, jadvalni kanalga joylash
    /band <N> <DD.MM> <HH:MM>   - N-akkauntni shu sanagacha band qiladi
    /bosh <N>                   - N-akkauntni bo'sh qiladi
    /holat                      - joriy holatni shaxsiy chatga yuboradi
    /help                       - yordam
"""

import os
import json
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ----------------------------- SOZLAMALAR -----------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "BOT_TOKEN_BU_YERGA")
ADMIN_ID = os.environ.get("ADMIN_ID", "0")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "CHANNEL_ID_BU_YERGA")

TOTAL_ACCOUNTS = 100
DATA_FILE = "data.json"

# ----------------------------- MA'LUMOT SAQLASH -----------------------------


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"accounts": {}, "message_id": None}


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()


def is_admin(update: Update) -> bool:
    return str(update.effective_user.id) == str(ADMIN_ID)


# ----------------------------- JADVAL YASASH -----------------------------


def build_table_text() -> str:
    now = datetime.now()
    bosh_count = 0
    band_count = 0

    rows = []
    for i in range(1, TOTAL_ACCOUNTS + 1):
        key = str(i)
        until_str = data["accounts"].get(key)

        if until_str:
            until = datetime.fromisoformat(until_str)
            if until > now:
                band_count += 1
                remaining = until - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                rows.append(
                    f"🔴 №{i:<3} BAND  {until.strftime('%d.%m %H:%M')}  "
                    f"(qoldi {hours}s {minutes}d)"
                )
                continue

        bosh_count += 1
        rows.append(f"🟢 №{i:<3} BO'SH")

    header = (
        "✨ <b>ATHAM RENT — Akkauntlar holati</b> ✨\n"
        f"🟢 Bo'sh: <b>{bosh_count}</b>   🔴 Band: <b>{band_count}</b>\n"
        f"🕒 Yangilandi: {now.strftime('%d.%m.%Y %H:%M')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    body = "<pre>" + "\n".join(rows) + "</pre>"
    footer = "\n📌 Ijaraga olish uchun admin bilan bog'laning."

    return header + body + footer


async def refresh_channel_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    text = build_table_text()

    if data.get("message_id") is None:
        msg = await context.bot.send_message(
            chat_id=CHANNEL_ID, text=text, parse_mode="HTML"
        )
        data["message_id"] = msg.message_id
        save_data(data)
    else:
        try:
            await context.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=data["message_id"],
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            # Agar xabar topilmasa (o'chirilgan bo'lsa) - yangisini yuboramiz
            logger.warning(f"Xabarni tahrirlab bo'lmadi, yangisini yuboraman: {e}")
            msg = await context.bot.send_message(
                chat_id=CHANNEL_ID, text=text, parse_mode="HTML"
            )
            data["message_id"] = msg.message_id
            save_data(data)


# ----------------------------- BUYRUQLAR -----------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "👋 Salom! Atham Rent boshqaruv botiga xush kelibsiz.\n\n"
        "Buyruqlar:\n"
        "/band <N> <DD.MM> <HH:MM> — akkauntni band qilish\n"
        "/bosh <N> — akkauntni bo'sh qilish\n"
        "/holat — joriy holatni ko'rish\n"
        "/help — yordam"
    )
    await refresh_channel_message(context)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "📖 Buyruqlar ro'yxati:\n\n"
        "/band 43 03.08 20:00 — 43-akkauntni 3-avgust soat 20:00 gacha band qiladi\n"
        "/bosh 43 — 43-akkauntni bo'sh qiladi\n"
        "/holat — hozirgi holatni shaxsiy chatga yuboradi"
    )


async def band_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        n = int(context.args[0])
        date_part = context.args[1]
        time_part = context.args[2]

        if not (1 <= n <= TOTAL_ACCOUNTS):
            raise ValueError

        day, month = date_part.split(".")
        hour, minute = time_part.split(":")

        now = datetime.now()
        until = datetime(
            year=now.year,
            month=int(month),
            day=int(day),
            hour=int(hour),
            minute=int(minute),
        )
        if until < now:
            until = until.replace(year=now.year + 1)

    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ Format noto'g'ri.\n"
            "To'g'ri format: /band 43 03.08 20:00"
        )
        return

    data["accounts"][str(n)] = until.isoformat()
    save_data(data)

    await update.message.reply_text(
        f"🔴 №{n} akkaunt {until.strftime('%d.%m %H:%M')} gacha band qilindi."
    )
    await refresh_channel_message(context)


async def bosh_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        n = int(context.args[0])
        if not (1 <= n <= TOTAL_ACCOUNTS):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Format noto'g'ri. To'g'ri format: /bosh 43")
        return

    data["accounts"][str(n)] = None
    save_data(data)

    await update.message.reply_text(f"🟢 №{n} akkaunt bo'sh qilindi.")
    await refresh_channel_message(context)


async def holat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(build_table_text(), parse_mode="HTML")


# ----------------------------- FON VAZIFASI -----------------------------


async def check_expired(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    changed = False

    for key, until_str in list(data["accounts"].items()):
        if until_str:
            until = datetime.fromisoformat(until_str)
            if until <= now:
                data["accounts"][key] = None
                changed = True

    if changed:
        save_data(data)
        await refresh_channel_message(context)


# ----------------------------- MAIN -----------------------------


def main():
    if BOT_TOKEN == "BOT_TOKEN_BU_YERGA":
        print(
            "DIQQAT: BOT_TOKEN o'rnatilmagan. "
            "BOT_TOKEN muhit o'zgaruvchisini to'ldiring."
        )

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("band", band_account))
    app.add_handler(CommandHandler("bosh", bosh_account))
    app.add_handler(CommandHandler("holat", holat))

    # Har 60 soniyada muddati o'tgan akkauntlarni tekshiradi
    app.job_queue.run_repeating(check_expired, interval=60, first=10)

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
