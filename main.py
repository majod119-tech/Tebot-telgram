import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# استيراد الإعدادات والبيانات من ملف config
from config import TOKEN, PORT, PLANS_DATA

# استيراد التصاميم والقوائم من ملف menus
from menus import (
    get_main_menu,
    get_plans_inline_menu,
    get_platforms_inline_menu,
    get_curricula_inline_menu,
)

# ==========================================
# 1. خادم الويب الأساسي (لضمان استقرار Koyeb)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health():
    return "Bot Service is Active and Running", 200

def run_web_server():
    web_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

threading.Thread(target=run_web_server, daemon=True).start()

# ==========================================
# 2. تفاعل وأوامر البوت (Handlers)
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *أهلاً بك في البوابة الذكية لقسم الحاسب الآلي*\n\n"
        "خدماتك التدريبية والمقررات الرسمية متاحة بين يديك بتصميم منظم وسهل.\n"
        "اختر الخدمة المطلوبة من القائمة أدناه 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "المعلم الذكي" in text:
        msg = (
            "🤖 *مرحباً بك في خدمة المعلم الذكي*\n"
            "──────────────────────\n"
            "أنا جاهز للإجابة على استفساراتك التخصصية:\n"
            "• شروحات البرمجة (Python, SQL).\n"
            "• الشبكات، الألياف الضوئية، وصيانة الحاسب.\n"
            "• مساندة المقررات وتطبيقات المعامل.\n\n"
            "💬 *اكتب سؤالك وسأجيبك فوراً!*"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif "الخطط التدريبية" in text:
        msg = (
            "📄 *الخطط التدريبية المعتمدة — قسم الحاسب الآلي*\n"
            "اختر الفصل التدريبي لعرض المقررات والساعات المعتمدة:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_plans_inline_menu())

    elif "الحقائب التدريبية" in text:
        msg = (
            "📚 *الحقائب والمناهج التدريبية الرسمية*\n"
            "──────────────────────\n"
            "يمكنك استعراض وتحميل كافة الحقائب المعتمدة بصيغة PDF عبر المنصات أدناه:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_curricula_inline_menu())

    elif "المنصات" in text:
        msg = (
            "🔗 *المنصات والخدمات الإلكترونية للمتدرب*\n"
            "──────────────────────\n"
            "اضغط على المنصة للفتح المباشر:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_platforms_inline_menu())

    elif "التقويم التدريبي" in text:
        msg = (
            "📅 *التقويم التدريبي المعتمد للفصل الحالي*\n"
            "──────────────────────\n"
            "📌 *أهم المحطات التدريبية:*\n"
            "• *الأسبوع الأول:* نهاية فترة تعديل الجداول في رايات.\n"
            "• *الأسبوع 7 و 8:* الاختبارات النصفية التحريرية والعملية.\n"
            "• *الأسبوع 9:* صدور الإنذار الأول للغياب (15%).\n"
            "• *الأسبوع 11 - 13:* الاختبارات العملية والنهائية.\n\n"
            "⚠️ يُرجى متابعة الحضور لتفادي الحرمان التلقائي."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif "أخبار" in text:
        msg = (
            "📰 *لوحة إعلانات وأخبار قسم الحاسب والمعهد*\n"
            "──────────────────────\n"
            "📢 التسجيل في الأنشطة التقنية وورش الصيانة متاح حالياً.\n"
            "📢 مراجعة المرشد التدريبي لتثبيت الحالات التدريبية.\n"
            "📢 تسجيل الحضور يتم إلكترونياً وبصورة يومية."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif "الأسئلة الشائعة" in text:
        msg = (
            "❓ *الأسئلة الأكثر تكراراً (FAQ)*\n"
            "──────────────────────\n"
            "🔹 *س: متى يقع الحرمان من المقرر؟*\n"
            "ج: عند بلوغ نسبة الغياب 20% فأكثر بدون عذر رسمي.\n\n"
            "🔹 *س: كيف أقدم العذر الطبي؟*\n"
            "ج: عبر منصة صحتي موثقاً وتقديمه للوكالة خلال 3 أيام عمل.\n\n"
            "🔹 *س: كيف استرجع حسابي التدريبي؟*\n"
            "ج: عبر بوابة استعادة كلمة المرور في موقع المؤسسة أو مراجعة معمل الحاسب."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    else:
        await update.message.reply_text(
            f"تم استلام رسالتك: {text}\nإذا كان لديك سؤال تخصصي تفضل باختيار '🤖 المعلم الذكي'.",
            reply_markup=get_main_menu()
        )

# ==========================================
# 3. معالج الأزرار المضمنة (Inline Keyboard Callback)
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data
    
    if plan_key in PLANS_DATA:
        await query.message.reply_text(
            PLANS_DATA[plan_key],
            parse_mode="Markdown",
            reply_markup=get_curricula_inline_menu()
        )

# ==========================================
# 4. تشغيل البوت
# ==========================================
if __name__ == "__main__":
    if not TOKEN:
        print("WARNING: TOKEN is not set! Web server will keep container alive.")
        import time
        while True:
            time.sleep(3600)
    else:
        print("Starting Telegram Bot with Clean Architecture...")
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
        application.run_polling()
