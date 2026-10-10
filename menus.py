from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# 1. القائمة السفلية الرئيسية (Reply Keyboard)
# ==========================================
def get_main_menu():
    keyboard = [
        ["🤖 المعلم الذكي"],
        ["📄 الخطط التدريبية", "📚 الحقائب التدريبية"],
        ["🔗 المنصات والخدمات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم", "❓ الأسئلة الشائعة"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 العودة للقائمة الرئيسية"]], resize_keyboard=True)

# ==========================================
# 2. القوائم المضمنة (Inline Keyboards)
# ==========================================
def get_plans_inline_menu():
    """أزرار الفصول مرتبة هندسياً لسهولة اللمس"""
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
    """أزرار تفتح الروابط مباشرة"""
    keyboard = [
        [
            InlineKeyboardButton("📱 منصة تقني الإلكترونية", url="https://tech.tvtc.gov.sa"),
            InlineKeyboardButton("🌐 بوابة رايات للمتدربين", url="https://rayat.tvtc.gov.sa")
        ],
        [
            InlineKeyboardButton("💻 بلاك بورد التدريب", url="https://lms.elearning.edu.sa"),
            InlineKeyboardButton("🏛️ بوابة المؤسسة العامة", url="https://tvtc.gov.sa")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_curricula_inline_menu():
    """روابط الحقائب والمناهج المعتمدة"""
    keyboard = [
        [
            InlineKeyboardButton("📚 بوابة المقررات الرسمية (CDD)", url="https://tvtc.gov.sa/ar/Departments/tvtcdepartments/cdd/Pages/packages.aspx")
        ],
        [
            InlineKeyboardButton("📑 منصة إيثاق للمناهج", url="https://eythaq.tvtc.gov.sa"),
            InlineKeyboardButton("📦 المستودع الرقمي", url="https://cdd.tvtc.gov.sa/curricula")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
