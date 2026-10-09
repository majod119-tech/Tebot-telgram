import os
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==========================================
# 1. خادم الويب الأساسي (Health Check)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health():
    return "Bot Service is Active and Running", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# تشغيل خادم الويب فوراً قبل أي شيء
threading.Thread(target=run_web_server, daemon=True).start()

# ==========================================
# 2. القوائم والواجهات المضمنة (UX/UI)
# ==========================================
def get_main_menu():
    keyboard = [
        ["🤖 المعلم الذكي"],
        ["📄 الخطط التدريبية", "📚 الحقائب التدريبية"],
        ["🔗 المنصات والخدمات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم", "❓ الأسئلة الشائعة"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_plans_inline_menu():
    keyboard = [
        [
            InlineKeyboardButton("1️⃣ الفصل الأول", callback_data="plan_1"),
            InlineKeyboardButton("2️⃣ الفصل الثاني", callback_data="plan_2")
        ],
        [
            InlineKeyboardButton("3️⃣ الفصل الثالث", callback_data="plan_3"),
            InlineKeyboardButton("4️⃣ الفصل الرابع", callback_data="plan_4")
        ],
        [
            InlineKeyboardButton("5️⃣ الفصل الخامس", callback_data="plan_5"),
            InlineKeyboardButton("6️⃣ الفصل السادس", callback_data="plan_6")
        ],
        [
            InlineKeyboardButton("🖥️ البرامج الفصلية والتطويرية", callback_data="plan_extra")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_platforms_inline_menu():
    keyboard = [
        [
            InlineKeyboardButton("📱 منصة تقني الإلكترونية", url="https://tech.tvtc.gov.sa"),
            InlineKeyboardButton("🌐 بوابة رايات للمتدربين", url="https://rayat.tvtc.gov.sa")
        ],
        [
            InlineKeyboardButton("💻 بلاك بورد التدريب الإلكتروني", url="https://lms.elearning.edu.sa"),
            InlineKeyboardButton("🏛️ بوابة المؤسسة العامة", url="https://tvtc.gov.sa")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_curricula_inline_menu():
    keyboard = [
        [
            InlineKeyboardButton("📚 بوابة المقررات الرسمية (CDD)", url="https://tvtc.gov.sa/ar/Departments/tvtcdepartments/cdd/Pages/packages.aspx")
        ],
        [
            InlineKeyboardButton("📑 منصة إيثاق للمناهج والخطط", url="https://eythaq.tvtc.gov.sa"),
            InlineKeyboardButton("📦 المستودع الرقمي للمناهج", url="https://cdd.tvtc.gov.sa/curricula")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# 3. بيانات الخطط الرسمية (نصفي 1446هـ)
# ==========================================
PLANS_DATA = {
    "plan_1": (
        "📘 *خطة الفصل التدريبي الأول (المعتمدة)*\n"
        "──────────────────────\n"
        "▫️ *ثقافة إسلامية - 1* `(اسلم 001)` — 2 ساعة معتمدة\n"
        "▫️ *لغة إنجليزية - 1* `(انجل 001)` — 3 ساعات معتمدة\n"
        "▫️ *رياضيات - 1* `(رياض 001)` — 2 ساعة معتمدة\n"
        "▫️ *فيزياء* `(فيزي 001)` — 3 ساعات معتمدة\n"
        "▫️ *التربية البدنية - 1* `(بدني 001)` — 2 ساعة معتمدة\n"
        "▫️ *لغة عربية - 1* `(عربي 001)` — 2 ساعة معتمدة\n"
        "▫️ *أساسيات الحاسب الآلي* `(حاسب 001)` — 3 ساعات (6 عملي)\n"
        "▫️ *مدخل إلى مهارات القرن 21* `(ماهر 001)` — 2 ساعة معتمدة\n"
        "▫️ *السلامة والصحة المهنية* `(مهني 002)` — 2 ساعة معتمدة\n"
        "──────────────────────\n"
        "📊 *إجمالي الوحدات:* 21 وحدة | 30 ساعة أسبوعياً."
    ),
    "plan_2": (
        "📘 *خطة الفصل التدريبي الثاني (المعتمدة)*\n"
        "──────────────────────\n"
        "▫️ *سلوك مهني* `(اسلك 001)` — 2 ساعة معتمدة\n"
        "▫️ *لغة عربية - 2* `(عربي 002)` — 2 ساعة معتمدة\n"
        "▫️ *لغة إنجليزية - 2* `(انجل 002)` — 3 ساعات معتمدة\n"
        "▫️ *رياضيات - 2* `(رياض 002)` — 2 ساعة معتمدة\n"
        "▫️ *التربية البدنية - 2* `(بدني 002)` — 1 ساعة معتمدة\n"
        "▫️ *ثقافة إسلامية - 2* `(اسلم 002)` — 2 ساعة معتمدة\n"
        "▫️ *تطبيقات الحاسب الآلي* `(حاسب 002)` — 3 ساعات (6 عملي)\n"
        "▫️ *مهارات التواصل والتعاون* `(ماهر 002)` — 2 ساعة معتمدة\n"
        "▫️ *التفكير الناقد والإبداعي* `(ماهر 003)` — 2 ساعة معتمدة\n"
        "▫️ *ورش تأسيسية* `(مهني 001)` — 3 ساعات (6 عملي)\n"
        "──────────────────────\n"
        "📊 *إجمالي الوحدات:* 22 وحدة | 30 ساعة أسبوعياً."
    ),
    "plan_3": (
        "📘 *خطة الفصل التدريبي الثالث (المعتمدة)*\n"
        "──────────────────────\n"
        "▫️ *ثقافة إسلامية - 3* `(اسلم 003)` — 2 ساعة معتمدة\n"
        "▫️ *رياضيات - 3* `(رياض 003)` — 2 ساعة معتمدة\n"
        "▫️ *لغة إنجليزية - 3* `(انجل 003)` — 3 ساعات معتمدة\n"
        "▫️ *بحث ومصادر المعلومات* `(ماهر 004)` — 2 ساعة معتمدة\n"
        "▫️ *الرسم الهندسي* `(مهني 003)` — 2 ساعة معتمدة\n"
        "▫️ *أجهزة وقياس* `(الكت 010)` — 2 ساعة معتمدة\n"
        "▫️ *أساسيات الكهرباء* `(حاكر 012)` — 2 ساعة معتمدة\n"
        "▫️ *أساسيات الإلكترونيات* `(حاكر 013)` — 2 ساعة معتمدة\n"
        "▫️ *تطبيقات مفتوحة المصدر* `(حاسب 011)` — 2 ساعة معتمدة\n"
        "──────────────────────\n"
        "📊 *إجمالي الوحدات:* 19 وحدة | 30 ساعة أسبوعياً."
    ),
    "plan_4": (
        "📘 *خطة الفصل التدريبي الرابع (المعتمدة)*\n"
        "──────────────────────\n"
        "▫️ *مقدمة في ريادة الأعمال* `(مهني 004)` — 2 ساعة معتمدة\n"
        "▫️ *تقنيات الإنترنت* `(حاسب 012)` — 2 ساعة معتمدة\n"
        "▫️ *مكونات الحاسب - 1* `(حاسب 021)` — 2 ساعة معتمدة\n"
        "▫️ *لغة برمجة - 1 (Python)* `(حاسب 031)` — 2 ساعة معتمدة\n"
        "▫️ *أساسيات الشبكات* `(حاسب 041)` — 2 ساعة معتمدة\n"
        "▫️ *رسم الشبكات بالحاسب* `(حاسب 042)` — 2 ساعة معتمدة\n"
        "▫️ *أساسيات نظام لينكس* `(حاسب 051)` — 2 ساعة معتمدة\n"
        "▫️ *أنشطة مهنية - 1* `(نشاط 001)` — ساعتان تدريبية\n"
        "──────────────────────\n"
        "📊 *إجمالي الوحدات:* 14 وحدة | 30 ساعة أسبوعياً."
    ),
    "plan_5": (
        "📘 *خطة الفصل التدريبي الخامس (المعتمدة)*\n"
        "──────────────────────\n"
        "▫️ *مكونات الحاسب - 2* `(حاسب 022)` — 2 ساعة معتمدة\n"
        "▫️ *صيانة الأجهزة الكفية* `(حاسب 023)` — 2 ساعة معتمدة\n"
        "▫️ *لغة برمجة - 2 (Python)* `(حاسب 032)` — 2 ساعة معتمدة\n"
        "▫️ *تمديد الكيابل النحاسية* `(حاسب 043)` — 2 ساعة معتمدة\n"
        "▫️ *شبكات الحاسب* `(حاسب 044)` — 2 ساعة معتمدة\n"
        "▫️ *نظام تشغيل الشبكة - 1* `(حاسب 052)` — 2 ساعة معتمدة\n"
        "▫️ *مشاريع إنتاجية* `(حاسب 091)` — 2 ساعة معتمدة\n"
        "▫️ *أنشطة مهنية - 2* `(نشاط 002)` — ساعتان تدريبية\n"
        "──────────────────────\n"
        "📊 *إجمالي الوحدات:* 14 وحدة | 30 ساعة أسبوعياً."
    ),
    "plan_6": (
        "📘 *خطة الفصل التدريبي السادس (المعتمدة)*\n"
        "──────────────────────\n"
        "▫️ *مبادئ قواعد البيانات* `(حاسب 013)` — 2 ساعة معتمدة\n"
        "▫️ *طرفيات الحاسب* `(حاسب 024)` — 2 ساعة معتمدة\n"
        "▫️ *مهارات صيانة الحاسب* `(حاسب 025)` — 2 ساعة معتمدة\n"
        "▫️ *تمديد كيابل الألياف الضوئية* `(حاسب 045)` — 2 ساعة معتمدة\n"
        "▫️ *نظام تشغيل الشبكة - 2* `(حاسب 053)` — 2 ساعة معتمدة\n"
        "▫️ *تدريب إنتاجي* `(حاسب 098)` — 3 ساعات (6 عملي)\n"
        "▫️ *أنشطة مهنية - 3* `(نشاط 003)` — 4 ساعات تدريبية\n"
        "──────────────────────\n"
        "📊 *إجمالي الوحدات:* 13 وحدة | 30 ساعة أسبوعياً."
    ),
    "plan_extra": (
        "🖥️ *البرامج والمسارات التطويرية المساندة:*\n"
        "──────────────────────\n"
        "• دورة لحام وفحص الألياف الضوئية المتقدمة.\n"
        "• ورشة تجميع وترقية وصيانة أجهزة الحاسب.\n"
        "• أساسيات إدارة خوادم أنظمة التشغيل (Windows Server).\n"
        "──────────────────────\n"
        "📢 التسجيل متاح دورياً عبر إعلانات معامل قسم الحاسب."
    )
}

# ==========================================
# 4. تفاعل وأوامر البوت
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
# 5. تشغيل البوت
# ==========================================
if __name__ == "__main__":
    token = os.environ.get("TOKEN") or os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    
    if not token:
        print("WARNING: TOKEN is not set! Web server will keep container alive.")
        import time
        while True:
            time.sleep(3600)
    else:
        print("Starting Telegram Bot Polling...")
        application = ApplicationBuilder().token(token).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
        application.run_polling()
