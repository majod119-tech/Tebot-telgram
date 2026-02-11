import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# --- 1. إعداد خادم الويب ---
app = Flask('')
@app.route('/')
def home():
    return "البوت يعمل بنجاح!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- 2. إعداد كود البوت ---
TOKEN = os.environ.get("TOKEN") 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إنشاء قائمة أزرار سفلية
    keyboard = [
        ["📍 موقع المعهد"],
        ["📊 استعلام عن نسبة الغياب"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "مرحباً بك في بوت المعهد! 🏢\nاختر من القائمة أدناه، أو أرسل **الرقم (ID)** مباشرة للبحث:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # إذا ضغط المستخدم على زر موقع المعهد
    if text == "📍 موقع المعهد":
        await update.message.reply_text(
            "📍 **موقع المعهد على خرائط جوجل:**\nhttps://maps.app.goo.gl/SgBNPgmNHKXager36"
        )
        return
        
    # إذا ضغط المستخدم على زر الاستعلام
    elif text == "📊 استعلام عن نسبة الغياب":
        await update.message.reply_text("الرجاء إرسال **الرقم (ID)** الآن للبحث:")
        return

    # إذا أرسل المستخدم رقماً (للبحث في الإكسل)
    try:
        # قراءة الملف مع دعم ترميز اللغة العربية وإزالة المسافات المخفية
