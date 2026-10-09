import os
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

# استيراد القوائم التفاعلية من ملف menus.py
from menus import (
    get_main_menu,
    get_plans_menu,
    get_admin_menu,
    get_cancel_menu,
    get_back_menu,
)

# ==========================================
# 1. إعداد خادم الويب المصغر (Health Check)
# ==========================================
server = Flask(__name__)

@server.route('/')
def health_check():
    """الرد على فحوصات Koyeb الدورية بحالة 200 OK"""
    return "Bot is healthy and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# ==========================================
# 2. معالجات الأوامر والرسائل للبوت
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على أمر /start وإظهار القائمة المخففة الجديدة"""
    welcome_text = (
        "أهلاً بك في المساعد الذكي لقسم الحاسب الآلي ✨\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة أدناه:"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على أزرار القوائم"""
    text = update.message.text

    if text == "🤖 المعلم الذكي":
        await update.message.reply_text(
            "مرحباً بك! أنا مستشارك الذكي لقسم الحاسب. تفضل بطرح أي سؤال تخصصي أو استفسار.",
            reply_markup=get_main_menu()
        )
    elif text == "📄 الخطط التدريبية":
        await update.message.reply_text(
            "اختر الفصل التدريبي لعرض الخطة:",
            reply_markup=get_plans_menu()
        )
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text(
            "يمكنك استعراض وتحميل الحقائب التدريبية المعتمدة للقسم.",
            reply_markup=get_main_menu()
        )
    elif text == "📅 التقويم التدريبي":
        await update.message.reply_text(
            "التقويم التدريبي للفصل الحالي متاح للاطلاع ومتابعة المواعيد الهامة.",
            reply_markup=get_main_menu()
        )
    elif text == "🔗 المنصات الإلكترونية":
        await update.message.reply_text(
            "منصات التدريب والرايات وبوابة المتدربين متاحة عبر الروابط الرسمية.",
            reply_markup=get_main_menu()
        )
    elif text == "📰 أخبار القسم والمعهد":
        await update.message.reply_text(
            "تابع أحدث الإعلانات والأنشطة وورش العمل الخاصة بالقسم.",
            reply_markup=get_main_menu()
        )
    elif text == "❓ الأسئلة الشائعة":
        await update.message.reply_text(
            "هنا تجد إجابات على أكثر الأسئلة تكراراً حول المقررات والتسجيل والاختبارات.",
            reply_markup=get_main_menu()
        )
    elif text == "🔙 الرجوع للقائمة الرئيسية" or text == "❌ إلغاء العملية":
        await update.message.reply_text(
            "تمت العودة للقائمة الرئيسية.",
            reply_markup=get_main_menu()
        )
    else:
        await update.message.reply_text(
            f"تم استلام طلبك: {text}",
            reply_markup=get_main_menu()
        )

# ==========================================
# 3. نقطة التشغيل الرئيسية
# ==========================================
def main():
    token = os.environ.get("TOKEN")
    if not token:
        raise ValueError("خطأ: لم يتم العثور على متغير البيئة TOKEN في Koyeb!")

    # تشغيل سيرفر الويب في خيط منفصل لتفادي توقف الحاوية
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # بناء وتشغيل تطبيق البوت
    app = ApplicationBuilder().token(token).build()

    # تسجيل المعالجات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    # بدء الاستماع الدائم للتحديثات (Polling)
    app.run_polling()

if __name__ == "__main__":
    main()
