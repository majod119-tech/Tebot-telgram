import os
import pandas as pd
import json
import random
import time
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر الويب ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running perfectly!")
    def log_message(self, format, *args): pass 

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. الإعدادات ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
TELEGRAM_CONTACT_LINK = "https://t.me/majod119"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "634887309" # رقمك الخاص في تليجرام ليظهر لك زر الإدارة

# إعداد الذكاء الاصطناعي (Gemini)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                ai_model = genai.GenerativeModel(m.name.replace('models/', ''))
                break
    except: ai_model = None

# ملفات البيانات
SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f: return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f: json.dump(data, f)

def update_stat(category):
    stats = load_json(STATS_FILE)
    stats[category] = stats.get(category, 0) + 1
    save_json(STATS_FILE, stats)

ai_sessions = {}
active_challenges = {}

# --- 3. بنك الأسئلة ---
QUESTIONS = [
    {"q": "ما هو عنوان الـ IP الذي يُعرف بـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1},
    {"q": "أي من المكونات يعتبر 'العقل المدبر' للحاسب؟", "options": ["HDD", "RAM", "CPU", "Motherboard"], "answer": 2},
    {"q": "أمر في لينكس لعرض قائمة الملفات؟", "options": ["cd", "ls", "pwd", "mkdir"], "answer": 1},
    {"q": "أي الكيابل يوفر أعلى سرعة نقل بيانات؟", "options": ["Coaxial", "Fiber Optic", "UTP", "Phone"], "answer": 1}
]

# --- 4. تصميم القوائم (UX المرتب) ---
def get_main_menu(user_id):
    keyboard = [
        ["🤖 المعلم الذكي (اسألني)"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], 
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["👨‍🏫 تواصل مع رئيس القسم"]
    ]
    # إضافة زر الإحصائيات للمدير فقط
    if str(user_id) == ADMIN_ID:
        keyboard.append(["📊 إحصائيات الإدارة"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_plans_menu():
    return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🖥️ برامج فصلية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 5. المهام والمنطق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    # تحديث إحصائية المستخدمين الجدد
    stats = load_json(STATS_FILE)
    users = stats.get("users_list", [])
    if user_id not in users:
        users.append(user_id)
        stats["users_list"] = users
        save_json(STATS_FILE, stats)
        
    ai_sessions[user_id] = False
    await update.message.reply_text(f"أهلاً بك {update.effective_user.first_name} في بوت قسم الحاسب 💻✨", reply_markup=get_main_menu(user_id))

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if text == "🔙 الرجوع للقائمة الرئيسية":
        ai_sessions[user_id] = False
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu(user_id))
        return

    # --- لوحة القيادة (للمدير فقط) ---
    if text == "📊 إحصائيات الإدارة" and user_id == ADMIN_ID:
        stats = load_json(STATS_FILE)
        scores = load_json(SCORES_FILE)
        msg = (
            "📊 **لوحة قيادة البوت (الإدارة):**\n\n"
            f"👥 **إجمالي المستخدمين:** {len(stats.get('users_list', []))}\n"
            f"🤖 **أسئلة المعلم الذكي:** {stats.get('ai_questions', 0)}\n"
            f"🎮 **محاولات التحدي:** {stats.get('quiz_attempts', 0)}\n"
            f"📞 **طلبات التواصل:** {stats.get('contact_clicks', 0)}\n"
            f"🏆 **طلاب لوحة الشرف:** {len(scores)}\n\n"
            "✨ *هذه البيانات تساعدك في تطوير القسم بناءً على اهتمامات المتدربين.*"
        )
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_back_menu())
        return

    # --- 🤖 المعلم الذكي ---
    if text == "🤖 المعلم الذكي (اسألني)":
        ai_sessions[user_id] = True
        await update.message.reply_text("🤖 **أهلاً بك في المعلم الذكي!** اكتب سؤالك التقني الآن وسأقوم بشرحه لك...", reply_markup=get_back_menu())
        return

    if ai_sessions.get(user_id) == True:
        update_stat("ai_questions")
        status_msg = await update.message.reply_text("⏳ جاري التفكير...")
        try:
            prompt = f"أنت معلم حاسب آلي سعودي خبير، أجب بوضوح وتدريب تقني على: {text}"
            response = await ai_model.generate_content_async(prompt)
            await status_msg.delete()
            await update.message.reply_text(response.text)
        except:
            await status_msg.delete()
            await update.message.reply_text("⚠️ عذراً، لم أتمكن من المعالجة حالياً.")
        return

    # --- بقية الأزرار ---
    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        scores = load_json(SCORES_FILE)
        user_data = scores.get(user_id, {"answered": []})
        available = [i for i in range(len(QUESTIONS)) if i not in user_data.get("answered", [])]
        if not available:
            await update.message.reply_text("✅ أكملت جميع الأسئلة!")
            return
        q_idx = random.choice(available)
        active_challenges[user_id] = time.time()
        keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans_{q_idx}_{i}")] for i, opt in enumerate(QUESTIONS[q_idx]['options'])]
        await update.message.reply_text(f"❓ {QUESTIONS[q_idx]['q']}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if text == "👨‍🏫 تواصل مع رئيس القسم":
        update_stat("contact_clicks")
        await update.message.reply_text(f"👨‍🏫 تواصل مباشر:\n{TELEGRAM_CONTACT_LINK}")
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("اختر الفصل المطلوب:", reply_markup=get_plans_menu())
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 أرسل **رقمك التدريبي** الآن..")
        return

    if text.isdigit():
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            result = df[df['stu_num'].astype(str).str.strip() == text]
            if not result.empty:
                msg = f"✅ النتائج لـ: {result.iloc[0]['stu_nam']}\n"
                for _, row in result.iterrows():
                    val = float(row['parsnt'])
                    msg += f"📖 {row['c_nam']}: %{val}\n"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("❌ غير مسجل.")
        except: await update.message.reply_text("⚠️ خطأ في الملف.")
        return

    # (أضف هنا أي ردود إضافية مفقودة من الكود السابق مثل الأخبار أو المواقع بنفس الطريقة)
    await update.message.reply_text("⚠️ اختر من القائمة أدناه 👇", reply_markup=get_main_menu(user_id))

# --- 6. الأزرار الشفافة ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    if query.data.startswith("ans_"):
        start_time = active_challenges.get(user_id, 0)
        time_taken = time.time() - start_time
        parts = query.data.split("_")
        q_idx, selected = int(parts[1]), int(parts[2])
        
        scores = load_json(SCORES_FILE)
        user_info = scores.get(user_id, {"name": query.from_user.first_name, "score": 0, "answered": []})
        
        if time_taken > 15:
            msg = "⌛ انتهى الوقت!"
        elif selected == QUESTIONS[q_idx]["answer"]:
            user_info["score"] += 10
            msg = "🎉 صح! +10 نقاط."
        else:
            msg = "❌ خطأ!"
            
        user_info["answered"].append(q_idx)
        scores[user_id] = user_info
        save_json(SCORES_FILE, scores)
        await query.edit_message_text(f"{QUESTIONS[q_idx]['q']}\n\n{msg}")

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 البوت يعمل مع لوحة القيادة...")
    app.run_polling()

if __name__ == '__main__':
    main()
