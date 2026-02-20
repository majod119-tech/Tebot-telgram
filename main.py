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

# --- 1. سيرفر الويب المطور (Web Dashboard) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            stats = load_json(STATS_FILE)
            scores = load_json(SCORES_FILE)
            html = f"""
            <html>
            <head>
                <title>لوحة قيادة قسم الحاسب</title>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; direction: rtl; background-color: #f4f7f6; margin: 0; padding: 20px; text-align: center; }}
                    .card-container {{ display: flex; justify-content: space-around; flex-wrap: wrap; margin-top: 30px; }}
                    .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 200px; margin: 10px; }}
                    .card h3 {{ color: #2c3e50; font-size: 16px; }}
                    .card p {{ font-size: 28px; font-weight: bold; color: #27ae60; margin: 0; }}
                    h1 {{ color: #2c3e50; border-bottom: 3px solid #27ae60; display: inline-block; padding-bottom: 10px; }}
                    table {{ margin: 30px auto; border-collapse: collapse; width: 90%; background: white; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                    th, td {{ padding: 12px 15px; border-bottom: 1px solid #ddd; text-align: center; }}
                    th {{ background-color: #27ae60; color: white; }}
                </style>
            </head>
            <body>
                <h1>📊 إحصائيات نظام قسم الحاسب الذكي</h1>
                <div class="card-container">
                    <div class="card"><h3>👥 إجمالي المتدربين</h3><p>{len(stats.get('users_list', []))}</p></div>
                    <div class="card"><h3>🤖 أسئلة الذكاء</h3><p>{stats.get('ai_questions', 0)}</p></div>
                    <div class="card"><h3>🎮 التحديات</h3><p>{stats.get('quiz_attempts', 0)}</p></div>
                    <div class="card"><h3>📞 طلبات التواصل</h3><p>{stats.get('contact_clicks', 0)}</p></div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is Live.")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. الإعدادات ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
TELEGRAM_CONTACT_LINK = "https://t.me/majod119"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"

# إعداد Gemini
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
feedback_sessions = {}
active_challenges = {}

# --- 3. بنك المعلومات (نصائح تقنية) ---
TECH_TIPS = [
    "💡 **نصيحة:** استخدم اختصار `Win + L` لقفل جهازك فوراً عند الابتعاد عنه لضمان خصوصيتك.",
    "🛡️ **أمن:** لا تستخدم نفس كلمة المرور لأكثر من حساب؛ استخدم برامج إدارة كلمات المرور (Password Managers).",
    "🚀 **برمجة:** في لغة بايثون، تعتبر المسافات البادئة (Indentation) جزءاً أساسياً من الكود وليس مجرد تنسيق.",
    "🌐 **شبكات:** عنوان `127.0.0.1` يشير دائماً إلى جهازك المحلي (Loopback address).",
    "💾 **صيانة:** إعادة تشغيل الجهاز (Restart) تحل أكثر من 70% من مشاكل تعليق النظام البسيطة.",
    "⚡ **اختصار:** استخدم `Ctrl + Shift + T` في المتصفح لاستعادة آخر تبويب قمت بإغلاقه بالخطأ."
]

# بنك أسئلة التحدي
QUESTIONS = [
    {"q": "ما هو عنوان الـ IP الذي يُعرف بـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1},
    {"q": "أي من المكونات يعتبر 'العقل المدبر' للحاسب؟", "options": ["HDD", "RAM", "CPU", "Motherboard"], "answer": 2},
    {"q": "أمر في لينكس لعرض قائمة الملفات؟", "options": ["cd", "ls", "pwd", "mkdir"], "answer": 1},
    {"q": "أي الكيابل يوفر أعلى سرعة نقل بيانات؟", "options": ["Coaxial", "Fiber Optic", "UTP", "Phone"], "answer": 1}
]

# --- 4. تصميم القوائم ---
def get_main_menu():
    keyboard = [
        ["🤖 المعلم الذكي (اسألني)"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["👨‍🏫 تواصل مع رئيس القسم"],
        ["🕹️ قسم الألعاب والإضافات"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_games_menu():
    keyboard = [
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"],
        ["💡 نصيحة تقنية", "📬 صندوق المقترحات"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_plans_menu():
    return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🖥️ برامج فصلية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 5. التنسيق البصري (Separator) ---
SEP = "\n━━━━━━━━━━━━━━\n"

# --- 6. المهام والمنطق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    stats = load_json(STATS_FILE)
    users = stats.get("users_list", [])
    if user_id not in users:
        users.append(user_id)
        stats["users_list"] = users
        save_json(STATS_FILE, stats)
    ai_sessions[user_id] = False
    feedback_sessions[user_id] = False
    
    welcome_text = (
        f"أهلاً بك {update.effective_user.first_name} {SEP}"
        f"مرحباً بك في المنظمة الذكية لقسم الحاسب 💻✨\n"
        f"أنا مساعدك الرقمي، اختر خدمتك من الأسفل 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if text == "🔙 الرجوع للقائمة الرئيسية":
        ai_sessions[user_id] = False
        feedback_sessions[user_id] = False
        await update.message.reply_text("🏠 عدنا للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # --- 🤖 المعلم الذكي ---
    if text == "🤖 المعلم الذكي (اسألني)":
        ai_sessions[user_id] = True
        msg = f"🤖 **المعلم الذكي جاهز!**{SEP}اكتب سؤالك التقني بوضوح وسأقوم بشرحه لك بطريقة مبسطة..."
        await update.message.reply_text(msg, reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        update_stat("ai_questions")
        status_msg = await update.message.reply_text("⏳ جاري التفكير...")
        try:
            prompt = f"أنت معلم حاسب آلي سعودي، أجب بوضوح على: {text}"
            response = await ai_model.generate_content_async(prompt)
            await status_msg.delete()
            await update.message.reply_text(f"📝 **الإجابة:**\n{response.text}{SEP}هل لديك سؤال آخر؟", parse_mode='Markdown')
        except:
            await status_msg.delete()
            await update.message.reply_text("⚠️ المعلم الذكي في استراحة قصيرة، جرب لاحقاً.")
        return

    # --- 📬 صندوق المقترحات ---
    if text == "📬 صندوق المقترحات":
        feedback_sessions[user_id] = True
        await update.message.reply_text(f"📬 **صوتك مسموع!**{SEP}اكتب مقترحك أو تطوير تود رؤيته في البوت، وسيوصل مباشرة لإدارة القسم.", reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if feedback_sessions.get(user_id) == True:
        try:
            feedback_msg = f"💡 **مقترح جديد من متدرب:**\nالاسم: {update.effective_user.first_name}\nالرسالة: {text}"
            await context.bot.send_message(chat_id=GROUP_ID, text=feedback_msg)
            feedback_sessions[user_id] = False
            await update.message.reply_text("✅ تم إرسال مقترحك للإدارة بنجاح. شكراً لمشاركتك!", reply_markup=get_games_menu())
        except:
            await update.message.reply_text("⚠️ عذراً، فشل إرسال المقترح.")
        return

    # --- 🕹️ قسم الألعاب والإضافات ---
    if text == "🕹️ قسم الألعاب والإضافات":
        await update.message.reply_text(f"🕹️ **ساحة الإبداع والتفاعل**{SEP}هنا تجد التحديات، المعلومات، وصوتك المسموع.", reply_markup=get_games_menu(), parse_mode='Markdown')
        return

    if text == "💡 نصيحة تقنية":
        tip = random.choice(TECH_TIPS)
        await update.message.reply_text(f"💡 **نصيحة اليوم:**\n{SEP}{tip}", parse_mode='Markdown')
        return

    # --- الخطط التدريبية ---
    term_plans = {
        "1️⃣ الفصل الأول": "📚 **مقررات الفصل الأول:**\n🔹 أساسيات الحاسب\n🔹 ثقافة إسلامية 1\n🔹 رياضيات 1\n🔹 إنجليزية 1",
        "2️⃣ الفصل الثاني": "📚 **مقررات الفصل الثاني:**\n🔹 تطبيقات الحاسب\n🔹 سلوك مهني\n🔹 رياضيات 2\n🔹 إنجليزية 2",
        "3️⃣ الفصل الثالث": "📚 **مقررات الفصل الثالث:**\n🔹 أساسيات الكهرباء\n🔹 أجهزة وقياس\n🔹 رياضيات 3\n🔹 تطبيقات مفتوحة المصدر",
        "4️⃣ الفصل الرابع": "📚 **مقررات الفصل الرابع:**\n🔹 أساسيات الشبكات\n🔹 مكونات الحاسب 1\n🔹 لغة برمجة 1\n🔹 تقنيات الإنترنت",
        "5️⃣ الفصل الخامس": "📚 **مقررات الفصل الخامس:**\n🔹 شبكات الحاسب\n🔹 صيانة الأجهزة الكفية\n🔹 لغة برمجة 2\n🔹 تمديد النحاس",
        "6️⃣ الفصل السادس": "📚 **مقررات الفصل السادس:**\n🔹 تمديد الألياف الضوئية\n🔹 قواعد البيانات\n🔹 صيانة الحاسب\n🔹 نظام تشغيل الشبكة",
        "🖥️ برامج فصلية": "📚 دورة إدخال البيانات ومعالجة النصوص المستقلة."
    }

    if text in term_plans:
        await update.message.reply_text(f"{term_plans[text]}{SEP}🔗 الحقائب: {DRIVE_LINK}", parse_mode='Markdown')
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 اختر الفصل التدريبي:", reply_markup=get_plans_menu())
        return

    # --- بقية الخدمات ---
    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        scores = load_json(SCORES_FILE)
        user_data = scores.get(user_id, {"answered": []})
        available = [i for i in range(len(QUESTIONS)) if i not in user_data.get("answered", [])]
        if not available:
            await update.message.reply_text("🎉 بطل! لقد أنهيت جميع تحديات هذا الأسبوع.")
            return
        q_idx = random.choice(available)
        active_challenges[user_id] = time.time()
        keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans_{q_idx}_{i}")] for i, opt in enumerate(QUESTIONS[q_idx]['options'])]
        await update.message.reply_text(f"❓ **تحدي:**\n{QUESTIONS[q_idx]['q']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if text == "🏆 بطل الأسبوع":
        scores = load_json(SCORES_FILE)
        if not scores:
            await update.message.reply_text("📉 لم تبدأ المنافسة بعد!")
            return
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        top = sorted_scores[0][1]
        await update.message.reply_text(f"🥇 **بطل الصدارة:** {top['name']}\n🌟 النقاط: {top['score']}", parse_mode='Markdown')
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text(f"🔎 **نظام البحث**{SEP}أرسل رقمك التدريبي الآن للبحث عن سجل غيابك..", parse_mode='Markdown')
        return

    if text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text(f"📝 **رفع العذر**{SEP}أرسل صورة العذر واكتب رقمك التدريبي في الوصف.")
        return

    if text == "👨‍🏫 تواصل مع رئيس القسم":
        update_stat("contact_clicks")
        await update.message.reply_text(f"👨‍🏫 تواصل مع م. ماجد:\n{TELEGRAM_CONTACT_LINK}")
        return

    if text.isdigit():
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            result = df[df['stu_num'].astype(str).str.strip() == text]
            if not result.empty:
                name = result.iloc[0]['stu_nam']
                msg = f"✅ **النتائج لـ:** `{name}`{SEP}"
                for _, row in result.iterrows(): msg += f"📖 {row['c_nam']}: %{row['parsnt']}\n"
                await update.message.reply_text(msg, parse_mode='Markdown')
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: await update.message.reply_text("⚠️ ملف البيانات غير جاهز.")
        return

    # افتراضي
    if text not in ["🔙 الرجوع للقائمة الرئيسية"]:
        await update.message.reply_text("⚠️ فضلاً اختر خدمة من القائمة 👇", reply_markup=get_main_menu())

# --- معالجة الصور والأعذار ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ اكتب رقمك التدريبي في وصف الصورة.")
        return
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد:\nالبيانات: {update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ تم استلام عذرك بنجاح.")
    except: await update.message.reply_text("⚠️ خطأ في الإرسال.")

# --- معالجة الأزرار الشفافة ---
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
        if time_taken > 15: msg = "⌛ انتهى الوقت!"
        elif selected == QUESTIONS[q_idx]["answer"]:
            user_info["score"] += 10
            msg = "🎉 إجابة صحيحة! +10 نقاط."
        else: msg = "❌ إجابة خاطئة."
        user_info["answered"].append(q_idx)
        scores[user_id] = user_info
        save_json(SCORES_FILE, scores)
        await query.edit_message_text(f"❓ {QUESTIONS[q_idx]['q']}{SEP}{msg}")

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 البوت الاحترافي يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()
