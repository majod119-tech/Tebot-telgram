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

# استيراد القوائم من ملف menus.py
from menus import (
    get_main_menu,
    get_plans_menu,
    get_admin_menu,
    get_cancel_menu,
    get_back_menu,
)

# ==========================================
# 1. إعداد خادم الويب (Health Check)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Service is Healthy and Running", 200

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==========================================
# 2. معالجات الأوامر والتفاعل
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك في المساعد الذكي لقسم الحاسب الآلي ✨\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة أدناه:"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # --- 1. المعلم الذكي ---
    if "المعلم الذكي" in text:
        msg = (
            "🤖 *مرحباً بك في خدمة المعلم الذكي لقسم الحاسب الآلي*\n\n"
            "أنا هنا للإجابة على استفساراتك التخصصية:\n"
            "• شرح المفاهيم البرمجية (Python, C++, HTML/CSS).\n"
            "• صيانة وتجميع الحاسب وشبكات الحاسب.\n"
            "• المساعدة في فهم المقررات التدريبية.\n\n"
            "💬 *تفضل بكتابة سؤالك وسأجيبك فوراً!*"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_menu())

    # --- 2. الخطط التدريبية ---
    elif "الخطط التدريبية" in text:
        msg = (
            "📄 *الخطط التدريبية المعتمدة - قسم الحاسب الآلي*\n\n"
            "اختر الفصل التدريبي المطلوب من القائمة أدناه لعرض تفاصيل الخطة وتوزيع الساعات التدريبية:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_plans_menu())

    # --- 3. معالجة فصول الخطط التدريبية ---
    elif any(f in text for f in ["الفصل الأول", "الفصل الثاني", "الفصل الثالث", "الفصل الرابع", "الفصل الخامس", "الفصل السادس"]):
        plan_info = {
            "الفصل الأول": "📘 *خطة الفصل الأول:*\n• مقدمة تطبيقات الحاسب\n• صيانة الحاسب الآلي وتجميعه\n• نظام التشغيل Windows\n• مبادئ السلامة المهنية",
            "الفصل الثاني": "📘 *خطة الفصل الثاني:*\n• أساسيات شبكات الحاسب\n• حزمة البرامج المكتبية المتقدمة\n• التمديدات السلكية والألياف الضوئية\n• مبادئ الكهرباء والإلكترونيات للحاسب",
            "الفصل الثالث": "📘 *خطة الفصل الثالث:*\n• صيانة الشبكات وربط الملحقات\n• أساسيات البرمجة بلغة بايثون\n• أمن وسلامة المعلومات\n• أنظمة التشغيل (Linux)",
            "الفصل الرابع": "📘 *خطة الفصل الرابع:*\n• تصميم وتطوير مواقع الإنترنت\n• قواعد البيانات الأساسية\n• الصيانة الوقائية ومعالجة الأعطال المتقدمة",
            "الفصل الخامس": "📘 *خطة الفصل الخامس:*\n• الدعم الفني وخدمة العملاء\n• إدارة خوادم الشبكات\n• برمجة التطبيقات الذكية",
            "الفصل السادس": "📘 *خطة الفصل السادس:*\n• مشروع التخرج الميداني\n• التدريب التعاوني في بيئة العمل"
        }
        selected = next((k for k in plan_info if k in text), text)
        response_text = plan_info.get(selected, f"خطة {text} المعتمدة لقسم الحاسب الآلي.")
        await update.message.reply_text(
            f"{response_text}\n\nلتحميل الحقائب كاملة بصيغة PDF راجع بوابة الإدارة العامة للمناهج.",
            parse_mode="Markdown",
            reply_markup=get_plans_menu()
        )

    elif "برامج فصلية" in text:
        await update.message.reply_text(
            "🖥️ *البرامج والدورات التطويرية المساندة:*\n• دورة صيانة ولحام الألياف الضوئية.\n• ورشة تجميع وصيانة الحاسب.\n• مبادئ الأمن السيبراني.",
            parse_mode="Markdown",
            reply_markup=get_plans_menu()
        )

    # --- 4. الحقائب التدريبية ---
    elif "الحقائب التدريبية" in text:
        msg = (
            "📚 *الحقائب والمناهج التدريبية المعتمدة:*\n\n"
            "يمكنك استعراض وتحميل الحقائب التخصصية والأدلة بصيغة PDF مباشرة عبر الرابط الرسمي:\n"
            "🌐 https://cdd.tvtc.gov.sa\n\n"
            "💡 للحصول على المذكرات العملية وملازم القسم، راجع معمل الحاسب المخصص."
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_menu())

    # --- 5. التقويم التدريبي ---
    elif "التقويم التدريبي" in text:
        msg = (
            "📅 *التقويم التدريبي للعام التدريبي الحالي:*\n\n"
            "📌 *أهم المحطات التدريبية:*\n"
            "• نهاية فترة الحذف والإضافة: نهاية الأسبوع الأول.\n"
            "• الاختبارات النصفية التحريرية والعملية: الأسبوع 7 و 8.\n"
            "• إصدار الإنذار الأول في الغياب (15%): الأسبوع 9.\n"
            "• الاختبارات العملية والنهائية: من الأسبوع 11 إلى 13.\n\n"
            "⚠️ يُرجى الالتزام التام بنسب الحضور لتفادي الحرمان في رايات."
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_menu())

    # --- 6. المنصات الإلكترونية ---
    elif "المنصات الإلكترونية" in text:
        msg = (
            "🔗 *أهم المنصات الإلكترونية للمتدرب:*\n\n"
            "1️⃣ *بوابة رايات (الجدول، الحضور، والدرجات):*\n"
            "🌐 https://rayat.tvtc.gov.sa\n\n"
            "2️⃣ *منصة التدريب الإلكتروني (بلاك بورد):*\n"
            "🌐 https://lms.elearning.edu.sa\n\n"
            "3️⃣ *بوابة المؤسسة العامة للتدريب التقني:*\n"
            "🌐 https://tvtc.gov.sa"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_menu())

    # --- 7. أخبار القسم والمعهد ---
    elif "أخبار القسم" in text or "أخبار" in text:
        msg = (
            "📰 *أحدث أخبار قسم الحاسب الآلي والمعهد:*\n\n"
            "📢 بدء التسجيل في الأنشطة التقنية وحلقات الدعم الفني.\n"
            "📢 على المتدربين الراغبين بتعديل الجداول مراجعة المرشد التدريبي.\n"
            "📢 تنبيه: الحضور يسجل يومياً ومباشرة عبر الأنظمة المركزية."
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_menu())

    # --- 8. الأسئلة الشائعة ---
    elif "الأسئلة الشائعة" in text:
        msg = (
            "❓ *الأسئلة الأكثر تكراراً:*\n\n"
            "🔹 *س: متى يصدر قرار الحرمان؟*\n"
            "ج: عند بلوغ نسبة الغياب 20% فأكثر بدون عذر رسمي معتمد.\n\n"
            "🔹 *س: أين أقدم الإجازة المرضية؟*\n"
            "ج: عبر منصة صحتي موثقة وتقديمها لوكالة شؤون المتدربين خلال 3 أيام.\n\n"
            "🔹 *س: كيف استرجع حساب رايات؟*\n"
            "ج: عبر بوابة استعادة الحساب بالموقع أو مراجعة وحدة تقنية المعلومات بالمعهد."
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_menu())

    # --- 9. الرجوع للقائمة الرئيسية وإلغاء العمليات ---
    elif "الرجوع" in text or "إلغاء" in text:
        await update.message.reply_text("تمت العودة للقائمة الرئيسية بنجاح ✨", reply_markup=get_main_menu())

    # --- 10. الرد الافتراضي ---
    else:
        await update.message.reply_text(
            f"تم استلام رسالتك: {text}\nإذا كان لديك سؤال تخصصي تفضل باختيار '🤖 المعلم الذكي' وسأجيبك فوراً.",
            reply_markup=get_main_menu()
        )

# ==========================================
# 3. نقطة الانطلاق الرئيسية
# ==========================================
if __name__ == "__main__":
    token = os.environ.get("TOKEN")
    if not token:
        print("CRITICAL ERROR: TOKEN environment variable not found!")
        exit(1)

    # 1. تشغيل خادم الويب في الخلفية (Health Check لـ Koyeb)
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # 2. تشغيل بوت تليجرام في الخيط الرئيسي لمنع أخطاء الإشارات وبقاء السيرفر حياً
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    print("Telegram Bot is running in Main Thread...")
    application.run_polling()
