import os
import asyncio
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

# SECURITY: Never put your Telegram bot token in this file or in GitHub.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Owner/admin is configured here as requested. Numeric Telegram ID is authoritative.
OWNER_ID = 8899247188
ADMIN_IDS = {OWNER_ID}
ADMIN_USERNAME = "@Ezjxz"  # Display/reference only; username is not used for authorization.

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "49"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", tempfile.gettempdir())) / "media_bot"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
log = logging.getLogger("media-bot")

USER_MODE = {}
USER_LOCKS = {}
TOTAL_REQUESTS = 0
TOTAL_SUCCESS = 0
TOTAL_FAILURES = 0
BOT_ENABLED = True
DEFAULT_QUALITY = 1080

HELP = (
    "Send a direct media link from a source you own or are allowed to download.\\n\\n"
    "Choose Video or Audio, then send the link. Video quality goes up to 4K "
    "when the source provides it. Actual quality depends on the source.\\n\\n"
    "This bot does not bypass DRM, paywalls, private access controls, or platform restrictions."
)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def lock_for(uid):
    if uid not in USER_LOCKS:
        USER_LOCKS[uid] = asyncio.Lock()
    return USER_LOCKS[uid]

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistics", callback_data="admin:stats"),
         InlineKeyboardButton("⚙️ Settings", callback_data="admin:settings")],
        [InlineKeyboardButton("▶️ Enable bot" if not BOT_ENABLED else "⏸ Disable bot",
                              callback_data="admin:toggle")],
        [InlineKeyboardButton("❔ Help", callback_data="admin:help")],
    ])

def settings_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("144p", callback_data="admin:q:144"),
         InlineKeyboardButton("360p", callback_data="admin:q:360"),
         InlineKeyboardButton("720p", callback_data="admin:q:720")],
        [InlineKeyboardButton("1080p", callback_data="admin:q:1080"),
         InlineKeyboardButton("1440p", callback_data="admin:q:1440"),
         InlineKeyboardButton("4K", callback_data="admin:q:2160")],
        [InlineKeyboardButton("⬅️ Admin panel", callback_data="admin:home")],
    ])

def user_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Video", callback_data="mode:video"),
         InlineKeyboardButton("🎵 Audio / MP3", callback_data="mode:audio")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ])

def quality_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("144p", callback_data="q:144"),
         InlineKeyboardButton("240p", callback_data="q:240"),
         InlineKeyboardButton("360p", callback_data="q:360")],
        [InlineKeyboardButton("480p", callback_data="q:480"),
         InlineKeyboardButton("720p HD", callback_data="q:720"),
         InlineKeyboardButton("1080p", callback_data="q:1080")],
        [InlineKeyboardButton("1440p", callback_data="q:1440"),
         InlineKeyboardButton("2160p / 4K", callback_data="q:2160")],
        [InlineKeyboardButton("🎵 Audio MP3", callback_data="mode:audio")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Media Downloader!\\n\\nSelect a mode, then send a permitted media URL.",
        reply_markup=user_keyboard(),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    await update.message.reply_text(
        f"👑 ADMIN CONTROL PANEL\\nOwner: {ADMIN_USERNAME}\\nID: {OWNER_ID}",
        reply_markup=admin_keyboard(),
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    await update.message.reply_text(
        f"📊 BOT STATISTICS\\n"
        f"Requests: {TOTAL_REQUESTS}\\n"
        f"Successful: {TOTAL_SUCCESS}\\n"
        f"Failed: {TOTAL_FAILURES}\\n"
        f"Active user locks: {len(USER_LOCKS)}\\n"
        f"Default quality: {DEFAULT_QUALITY}p\\n"
        f"Upload cap: {MAX_UPLOAD_MB} MB\\n"
        f"Bot status: {'Enabled' if BOT_ENABLED else 'Disabled'}"
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED, DEFAULT_QUALITY
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data or ""

    if data.startswith("admin:"):
        if not is_admin(uid):
            await query.answer("Admin only.", show_alert=True)
            return
        action = data.split(":")
        if data == "admin:home":
            await query.edit_message_text("👑 ADMIN CONTROL PANEL", reply_markup=admin_keyboard())
        elif data == "admin:stats":
            await query.edit_message_text(
                f"📊 BOT STATISTICS\\nRequests: {TOTAL_REQUESTS}\\n"
                f"Successful: {TOTAL_SUCCESS}\\nFailed: {TOTAL_FAILURES}\\n"
                f"Active user locks: {len(USER_LOCKS)}\\n"
                f"Default quality: {DEFAULT_QUALITY}p\\n"
                f"Upload cap: {MAX_UPLOAD_MB} MB\\n"
                f"Bot status: {'Enabled' if BOT_ENABLED else 'Disabled'}",
                reply_markup=admin_keyboard(),
            )
        elif data == "admin:settings":
            await query.edit_message_text(
                f"⚙️ SETTINGS\\nDefault video quality: {DEFAULT_QUALITY}p\\n"
                f"Upload cap: {MAX_UPLOAD_MB} MB",
                reply_markup=settings_keyboard(),
            )
        elif data == "admin:toggle":
            BOT_ENABLED = not BOT_ENABLED
            await query.edit_message_text(
                f"Bot is now {'ENABLED' if BOT_ENABLED else 'DISABLED'} for user downloads.",
                reply_markup=admin_keyboard(),
            )
        elif data == "admin:help":
            await query.edit_message_text(
                "Admin commands:\\n/admin - open panel\\n/stats - view statistics\\n"
                "/setmax 49 - set upload cap in MB (up to 49 in this build).",
                reply_markup=admin_keyboard(),
            )
        elif len(action) == 3 and action[1] == "q":
            DEFAULT_QUALITY = int(action[2])
            await query.edit_message_text(
                f"✅ Default video quality changed to {DEFAULT_QUALITY}p.",
                reply_markup=settings_keyboard(),
            )
        return

    if data == "help":
        await query.message.reply_text(HELP)
    elif data.startswith("mode:"):
        mode = data.split(":", 1)[1]
        USER_MODE[uid] = {"mode": mode, "height": DEFAULT_QUALITY}
        if mode == "video":
            await query.message.reply_text("Choose maximum video quality:", reply_markup=quality_keyboard())
        else:
            await query.message.reply_text("Audio mode selected. Send your permitted media URL.")
    elif data.startswith("q:"):
        height = int(data.split(":", 1)[1])
        USER_MODE[uid] = {"mode": "video", "height": height}
        await query.message.reply_text(f"Video mode set to up to {height}p. Now send the link.")

async def setmax_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAX_UPLOAD_MB, MAX_UPLOAD_BYTES
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setmax 49")
        return
    value = int(context.args[0])
    if not 1 <= value <= 49:
        await update.message.reply_text("This build supports 1–49 MB. Telegram Bot API upload limits apply.")
        return
    MAX_UPLOAD_MB = value
    MAX_UPLOAD_BYTES = value * 1024 * 1024
    await update.message.reply_text(f"✅ Upload cap set to {value} MB for this running session.")

def safe_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def progress_hook_factory(loop, message):
    last = {"pct": -1}
    def hook(data):
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            if total:
                pct = int(downloaded * 100 / total)
                if pct >= last["pct"] + 10:
                    last["pct"] = pct
                    asyncio.run_coroutine_threadsafe(
                        message.edit_text(f"Downloading… {pct}%"), loop
                    )
    return hook

def download_media(url, mode, height, outdir, loop, status_message, max_bytes):
    outtmpl = str(outdir / "%(title).80s-%(id)s.%(ext)s")
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": max_bytes,
        "socket_timeout": 25,
        "retries": 2,
        "fragment_retries": 2,
        "progress_hooks": [progress_hook_factory(loop, status_message)],
    }
    if mode == "audio":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        opts["format"] = (
            f"best[height<={height}][ext=mp4]/"
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]"
        )
        opts["merge_output_format"] = "mp4"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = Path(ydl.prepare_filename(info))
        if mode == "audio":
            filepath = filepath.with_suffix(".mp3")
        elif filepath.suffix.lower() not in (".mp4", ".mkv", ".webm"):
            candidates = sorted(outdir.glob(f"*{info.get('id','')}*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                filepath = candidates[0]
        return filepath, info.get("title", "Media")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TOTAL_REQUESTS, TOTAL_SUCCESS, TOTAL_FAILURES
    uid = update.effective_user.id
    if not BOT_ENABLED and not is_admin(uid):
        await update.message.reply_text("⏸ Downloads are temporarily disabled by the admin.")
        return
    url = (update.message.text or "").strip()
    if not safe_url(url):
        await update.message.reply_text("Please send a valid http:// or https:// link.")
        return
    selection = USER_MODE.get(uid)
    if not selection:
        await update.message.reply_text("First choose Video or Audio using /start.")
        return

    async with lock_for(uid):
        TOTAL_REQUESTS += 1
        status = await update.message.reply_text("Preparing your download…")
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_DOCUMENT)
        temp_dir = Path(tempfile.mkdtemp(prefix=f"tgdl_{uid}_", dir=DOWNLOAD_DIR))
        try:
            loop = asyncio.get_running_loop()
            filepath, title = await asyncio.to_thread(
                download_media, url, selection["mode"], selection["height"],
                temp_dir, loop, status, MAX_UPLOAD_BYTES
            )
            if not filepath.exists():
                raise RuntimeError("The source did not produce a downloadable file.")
            size = filepath.stat().st_size
            if size > MAX_UPLOAD_BYTES:
                raise RuntimeError(
                    f"File is {size / 1024 / 1024:.1f} MB, above this bot's "
                    f"{MAX_UPLOAD_MB} MB upload cap. Try a lower quality."
                )
            await status.edit_text("Uploading to Telegram…")
            with filepath.open("rb") as media:
                await update.message.reply_document(
                    document=media, filename=filepath.name, caption=title[:900],
                    read_timeout=180, write_timeout=180, connect_timeout=30,
                )
            TOTAL_SUCCESS += 1
            await status.delete()
        except Exception as exc:
            TOTAL_FAILURES += 1
            log.exception("Download failed")
            msg = str(exc)
            if len(msg) > 700:
                msg = msg[:700] + "…"
            await status.edit_text(f"Could not complete this download:\\n{msg}")
        finally:
            for p in temp_dir.glob("*"):
                try:
                    p.unlink()
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass

async def error_handler(update, context):
    log.error("Unhandled error: %s", context.error)

def main():
    if not BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN environment variable first.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("setmax", setmax_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_error_handler(error_handler)
    log.info("Bot starting…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
