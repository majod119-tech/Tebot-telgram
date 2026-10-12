from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    keyboard = [
        ["🤖 المعلم الذكي", "🛠️ تقني عابر"],
        ["📄 الخطط التدريبية", "📚 الحقائب التدريبية"],
        ["🔗 المنصات والخدمات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم", "❓ الأسئلة الشائعة"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 العودة للقائمة الرئيسية"]], resize_keyboard=True)

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
    """تم تحديث رابط منصة تقني والإبقاء على بلاك بورد"""
    keyboard = [
        [
            # الرابط الجديد لمنصة تقني
            InlineKeyboardButton("📱 منصة تقني الإلكترونية", url="https://tvtclms.edu.sa"),
            InlineKeyboardButton("🌐 بوابة رايات للمتدربين", url="https://rayat.tvtc.gov.sa")
        ],
        [
            # الإبقاء على بلاك بورد
            InlineKeyboardButton("💻 بلاك بورد التدريب", url="https://lms.elearning.edu.sa"),
            InlineKeyboardButton("🏛️ بوابة المؤسسة العامة", url="https://tvtc.gov.sa")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_curricula_inline_menu():
    """تم إضافة رابط ملفات المناهج الجديد على جوجل درايف"""
    keyboard = [
        [
            # الرابط الجديد المباشر لملفات المناهج (Google Drive)
            InlineKeyboardButton("📁 ملفات المناهج والحقائب (Google Drive)", url="https://drive.google.com/drive/folders/1ZLqgZ4OE3P9SrmzV9298uo8KxFqNU8wQ")
        ],
        [
            InlineKeyboardButton("📑 منصة إيثاق للمناهج", url="https://eythaq.tvtc.gov.sa"),
            InlineKeyboardButton("📦 المستودع الرقمي", url="https://cdd.tvtc.gov.sa/curricula")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
