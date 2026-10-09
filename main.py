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
# 1. خادم الويب لفحص الصحة (Health Check)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Service is Healthy and Running", 200

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
        await update.message.reply_text("مرحباً بك في خدمة المعلم الذكي. تفضل بطرح استفسارك.", reply_markup=get_main_menu())
    elif text == "📄 الخطط التدريبية":
        await update.message.reply_text("اختر الفصل التدريبي لعرض الخطة:", reply_markup=get_plans_menu())
    elif text in ["🔙 الرجوع للقائمة الرئيسية", "❌ إلغاء العملية"]:
        await update.message.reply_text("تمت العودة للقائمة الرئيسية.", reply_markup=get_main_menu())
    else:
        await update.message.reply_text(f"تم استلام طلبك: {text}", reply_markup=get_main_menu())

# ==========================================
# 3. تشغيل البوت في خيط مستقل بأمان تام
# ==========================================
def start_bot_thread():
    token = os.environ.get("TOKEN")
    if not token:
        print("CRITICAL: TOKEN is missing!")
        return

    # إنشاء حلقة أحداث مخصصة للخيط
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    # النقطة الجوهرية: stop_signals=None تمنع خطأ set_wakeup_fd نهائياً
    application.run_polling(stop_signals=None, close_loop=False)

# ==========================================
# 4. نقطة الانطلاق
# ==========================================
if __name__ == "__main__":
    # تشغيل البوت في الخلفية بدون اعتراض للإشارات
    t = threading.Thread(target=start_bot_thread, daemon=True)
    t.start()

    # تشغيل سيرفر الويب في الخيط الرئيسي
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
