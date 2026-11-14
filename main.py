
import os
import sqlite3
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL = os.getenv("CHANNEL_ID", "@KANAL_USERNAME")

db = sqlite3.connect("kurayo.db", check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS anime (
 code TEXT PRIMARY KEY,
 name TEXT,
 cover TEXT
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS episodes (
 code TEXT,
 number INTEGER,
 title TEXT,
 video TEXT,
 PRIMARY KEY(code, number)
)
""")
db.commit()


def is_admin(user_id):
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    try:
        member = await context.bot.get_chat_member(CHANNEL, user.id)
        if member.status in ("left", "kicked"):
            await update.message.reply_text(
                f"Botdan foydalanish uchun kanalga obuna bo'ling:\n"
                f"https://t.me/{CHANNEL.lstrip('@')}\n"
                "Obuna bo'lgach /start ni qayta bosing."
            )
            return
    except Exception:
        await update.message.reply_text(
            "Obunani tekshirib bo'lmadi. Kanal sozlamalarini tekshiring."
        )
        return

    await update.message.reply_text(
        "🎌 KURAYO | Anime World\n\n"
        "Anime kodini yuboring va qismlarni oling!"
    )


async def new_anime(update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Namuna: /new 101 Solo Leveling"
        )
        return

    code = context.args[0]
    name = " ".join(context.args[1:])

    db.execute(
        "INSERT OR REPLACE INTO anime(code,name) VALUES(?,?)",
        (code, name)
    )
    db.commit()

    await update.message.reply_text(
        f"✅ Anime qo'shildi!\nKod: {code}\nNomi: {name}"
    )


async def cover(update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 1:
        await update.message.reply_text("Namuna: /cover 101")
        return

    code = context.args[0]
    row = db.execute(
        "SELECT name FROM anime WHERE code=?", (code,)
    ).fetchone()

    if not row:
        await update.message.reply_text("Bunday anime kodi topilmadi.")
        return

    context.user_data["pending"] = ("cover", code)
    await update.message.reply_text("Endi anime muqovasini rasm qilib yuboring.")


async def episode(update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Namuna: /episode 101 1 Birinchi qism"
        )
        return

    code = context.args[0]
    number = int(context.args[1])
    title = " ".join(context.args[2:])

    row = db.execute(
        "SELECT name FROM anime WHERE code=?", (code,)
    ).fetchone()

    if not row:
        await update.message.reply_text("Avval /new bilan anime qo'shing.")
        return

    context.user_data["pending"] = ("episode", code, number, title)
    await update.message.reply_text("Endi video yuboring.")


async def media(update, context):
    pending = context.user_data.get("pending")

    if not pending or not is_admin(update.effective_user.id):
        return

    if pending[0] == "cover":
        if not update.message.photo:
            await update.message.reply_text("Iltimos, rasm yuboring.")
            return

        code = pending[1]
        photo = update.message.photo[-1].file_id
        name = db.execute(
            "SELECT name FROM anime WHERE code=?", (code,)
        ).fetchone()[0]

        db.execute(
            "UPDATE anime SET cover=? WHERE code=?", (photo, code)
        )
        db.commit()

        await context.bot.send_photo(
            chat_id=CHANNEL,
            photo=photo,
            caption=f"🎌 {name}\n🔑 Kod: {code}"
        )

        context.user_data.pop("pending", None)
        await update.message.reply_text("✅ Muqova kanalga joylandi!")

    elif pending[0] == "episode":
        if not update.message.video:
            await update.message.reply_text("Iltimos, video yuboring.")
            return

        _, code, number, title = pending
        video = update.message.video.file_id

        db.execute(
            "INSERT OR REPLACE INTO episodes VALUES(?,?,?,?)",
            (code, number, title, video)
        )
        db.commit()

        await context.bot.send_video(
            chat_id=CHANNEL,
            video=video,
            caption=f"🎬 {title}\n🔑 Kod: {code}\n📺 Qism: {number}"
        )

        context.user_data.pop("pending", None)
        await update.message.reply_text("✅ Video kanalga joylandi!")


async def find_anime(update, context):
    code = update.message.text.strip()

    row = db.execute(
        "SELECT name, cover FROM anime WHERE code=?", (code,)
    ).fetchone()

    if not row:
        await update.message.reply_text("❌ Anime kodi topilmadi.")
        return

    name, cover_id = row
    episodes = db.execute(
        "SELECT number,title,video FROM episodes WHERE code=? ORDER BY number",
        (code,)
    ).fetchall()

    if cover_id:
        await update.message.reply_photo(
            cover_id, caption=f"🎌 {name}\n🔑 Kod: {code}"
        )
    else:
        await update.message.reply_text(f"🎌 {name}\n🔑 Kod: {code}")

    if not episodes:
        await update.message.reply_text("Hozircha qismlar mavjud emas.")
        return

    for number, title, video in episodes:
        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=video,
            caption=f"📺 {number}-qism: {title}"
        )


def main():
    if not TOKEN or not ADMIN_ID or CHANNEL == "@KANAL_USERNAME":
        raise RuntimeError("Hosting sozlamalarini to'ldiring!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_anime))
    app.add_handler(CommandHandler("cover", cover))
    app.add_handler(CommandHandler("episode", episode))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, media))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, find_anime
    ))

    print("KURAYO BOT ISHGA TUSHDI!")
    app.run_polling()


if __name__ == "__main__":
    main()
