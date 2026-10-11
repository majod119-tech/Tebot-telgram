def get_platforms_inline_menu():
    """أزرار تفتح الروابط مباشرة (مع البوت المساند)"""
    keyboard = [
        [
            InlineKeyboardButton("📱 منصة تقني الإلكترونية", url="https://tech.tvtc.gov.sa"),
            InlineKeyboardButton("🌐 بوابة رايات للمتدربين", url="https://rayat.tvtc.gov.sa")
        ],
        [
            InlineKeyboardButton("💻 بلاك بورد التدريب", url="https://lms.elearning.edu.sa"),
            InlineKeyboardButton("🏛️ بوابة المؤسسة العامة", url="https://tvtc.gov.sa")
        ],
        [
            # الزر الجديد الخاص بالبوت المساند الذي اقترحته
            InlineKeyboardButton("🤖 خدمات المتدربين (بوت مساند)", url="https://t.me/Abr20k1bot")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
