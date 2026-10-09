import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# استيراد القوائم التفاعلية
from menus import (
    get_main_menu,
    get_plans_menu,
    get_cancel_menu,
    get_back_menu,
)

# ==========================================
# 1. إعداد خادم الويب (Health Check)
# ==========================================
app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

# ==========================================
# 2. معالجات تليجرام
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك في المساعد الذكي لقسم الحاسب الآلي ✨\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة أدناه:"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🤖 المعلم الذكي":
        await update.message.reply_text("مرحباً بك! أنا مستشارك الذكي لقسم الحاسب. تفضل بطرح أي سؤال تخصصي.", reply_markup=get_main_menu())
    elif text == "📄 الخطط التدريبية":
        await update.message.reply_text("اختر الفصل التدريبي لعرض الخطة:", reply_markup=get_plans_menu())
    elif text in ["🔙 الرجوع للقائمة الرئيسية", "❌ إلغاء العملية"]:
        await update.message.reply_text("تمت العودة للقائمة الرئيسية.", reply_markup=get_main_menu())
    else:
        await update.message.reply_text(f"تم اختيار: {text}", reply_markup=get_main_menu())

# ==========================================
# 3. تشغيل البوت في مسار منفصل
# ==========================================
def run_telegram_bot():
    token = os.environ.get("TOKEN")
    if not token:
        print("ERROR: TOKEN environment variable not found!")
        return

    # إنشاء حلقة أحداث مخصصة لمسار البوت
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    application.run_polling(close_loop=False)

# ==========================================
# 4. نقطة الانطلاق الرئيسية
# ==========================================
if __name__ == "__main__":
    # تشغيل البوت في الخلفية
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # تشغيل Flask كعملية حابسة (Blocking) في الواجهة لمنع خروج بايثون
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
