from telegram import ReplyKeyboardMarkup

# --- 🌟 القوائم التفاعلية 🌟 ---

def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المعلم الذكي"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 المنصات الإلكترونية", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["❓ الأسئلة الشائعة", "📘 دليل المتدرب"],
        ["📬 الاقتراحات والشكاوى", "🕹️ قسم الألعاب والإضافات"]
    ], resize_keyboard=True, is_persistent=True)

def get_cancel_menu(): 
    return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)

def get_back_menu(): 
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

def get_plans_menu(): 
    return ReplyKeyboardMarkup([
        ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], 
        ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], 
        ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], 
        ["🖥️ برامج فصلية", "🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_games_menu(): 
    return ReplyKeyboardMarkup([
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], 
        ["💡 نصيحة تقنية", "🌐 أخبار التقنية"], 
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_pledge_step1_menu(): 
    return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب"]], resize_keyboard=True)

def get_pledge_step2_menu(): 
    return ReplyKeyboardMarkup([
        ["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"], 
        ["🚗 مشكلة في المواصلات", "⚙️ أعطال تقنية/أخرى"], 
        ["❌ إلغاء العملية"]
    ], resize_keyboard=True)

def get_pledge_step3_menu(): 
    return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)

# في ملف قائمة المدير menus.py
def get_admin_menu():
    return ReplyKeyboardMarkup([
        ["إرسال تعميم 📢", "كشف الحالات الحرجة ⚠️"],
        ["حالة قاعدة البيانات 📊", "تقرير سير العملية 📑"],
        ["سحب نسخة احتياطية 💾", "🦞 مساعد OpenClaw"],
        ["🔄 تحويل الخطط للقالب الجديد"], # 🌟 تمت إضافة الزر الجديد هنا 🌟
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)
    
def get_openclaw_menu():
    return ReplyKeyboardMarkup([
        ["❌ إنهاء محادثة الذكاء الاصطناعي"]
    ], resize_keyboard=True)
