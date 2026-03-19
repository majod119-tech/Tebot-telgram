import os
import io
import json
import time
import base64
import random
import asyncio
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==========================================
# ⚙️ إعدادات أساسية
# ==========================================
TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGODB_URI")
ADMIN_ID = os.getenv("ADMIN_ID", "")
GROUP_ID = os.getenv("GROUP_ID", "")
PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    raise ValueError("❌ TOKEN غير موجود في البيئة!")

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"

# ==========================================
# 📁 أدوات JSON
# ==========================================
def load_json(file):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except:
        pass

# ==========================================
# ⚡ كاش الإكسل (محسن)
# ==========================================
EXCEL_CACHE = None
LAST_MODIFIED = 0

def get_excel():
    global EXCEL_CACHE, LAST_MODIFIED
    path = "data.xlsx"

    if not os.path.exists(path):
        return None

    mod = os.path.getmtime(path)

    if EXCEL_CACHE is None or mod > LAST_MODIFIED:
        try:
            df = pd.read_excel(path, dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\D', '', regex=True)
            EXCEL_CACHE = df
            LAST_MODIFIED = mod
            print("🔄 تم تحديث الكاش")
        except Exception as e:
            print("Excel Error:", e)
            return None

    return EXCEL_CACHE

# ==========================================
# 🌐 Web Dashboard
# ==========================================
class Dashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        df = get_excel()
        total = len(df) if df is not None else 0

        html = f"""
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family:sans-serif;text-align:center">
        <h1>📊 Dashboard</h1>
        <h2>عدد السجلات: {total}</h2>
        </body>
        </html>
        """

        self.send_response(200)
        self.end_headers()
        self.wfile.write(html.encode())

def run_web():
    server = HTTPServer(("0.0.0.0", PORT), Dashboard)
    server.serve_forever()

# ==========================================
# 🔁 مهام خلفية
# ==========================================
def background():
    while True:
        try:
            stats = load_json(STATS_FILE)
            now = datetime.now().strftime("%Y-%m-%d")

            if stats.get("last_reset") != now:
                save_json(SCORES_FILE, {})
                stats["last_reset"] = now
                save_json(STATS_FILE, stats)

        except Exception as e:
            print("BG Error:", e)

        time.sleep(60)

# ==========================================
# 🎮 القوائم
# ==========================================
def main_menu():
    return ReplyKeyboardMarkup([
        ["📊 استعلام", "🤖 AI"],
        ["💡 نصيحة", "🎮 تحدي"]
    ], resize_keyboard=True)

# ==========================================
# 🚀 start
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في النظام",
        reply_markup=main_menu()
    )

# ==========================================
# 🧠 منطق البوت
# ==========================================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    # 📊 استعلام
    if text == "📊 استعلام":
        await update.message.reply_text("أرسل رقمك التدريبي")
        return

    # 🔢 رقم تدريبي
    if text.isdigit():
        df = get_excel()
        if df is None:
            await update.message.reply_text("⚠️ لا يوجد بيانات")
            return

        res = df[df['stu_num'] == text]
        if res.empty:
            await update.message.reply_text("❌ غير موجود")
            return

        name = res.iloc[0]['stu_nam']
        await update.message.reply_text(f"👤 {name}")
        return

    # 💡 نصيحة
    if text == "💡 نصيحة":
        tips = ["خذ نسخة احتياطية", "حدث نظامك", "لا تثق بأي رابط"]
        await update.message.reply_text(random.choice(tips))
        return

    # 🎮 تحدي
    if text == "🎮 تحدي":
        await update.message.reply_text("❓ ما هو localhost؟")
        return

    await update.message.reply_text("اختر من القائمة", reply_markup=main_menu())

# ==========================================
# ▶️ التشغيل
# ==========================================
def main():
    Thread(target=background, daemon=True).start()
    Thread(target=run_web, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🚀 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
    