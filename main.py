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
active_challenges = {}

# --- 3. بنك الأسئلة ---
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
        ["🕹️ قسم الألعاب والتحديات"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_games_menu():
    return ReplyKeyboardMarkup([["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

def get_plans_menu():
    keyboard = [
        ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"],
        ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"],
        ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"],
        ["🖥️ برامج فصلية"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 5. المهام والمنطق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    stats = load_json(STATS_FILE)
    users = stats.get("users_list", [])
    if user_id not in users:
        users.append(user_id)
        stats["users_list"] = users
        save_json(STATS_FILE, stats)
    ai_sessions[user_id] = False
    await update.message.reply_text(f"أهلاً بك {update.effective_user.first_name} في بوت قسم الحاسب 💻✨", reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if text == "🔙 الرجوع للقائمة الرئيسية":
        ai_sessions[user_id] = False
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # --- إدارة الخطط التدريبية (التي تم إصلاحها) ---
    term_plans = {
        "1️⃣ الفصل الأول": "📚 **مقررات الفصل التدريبي الأول:**\n🔹 ثقافة إسلامية 1\n🔹 لغة إنجليزية 1\n🔹 رياضيات 1\n🔹 فيزياء\n🔹 التربية البدنية 1\n🔹 لغة عربية 1\n🔹 أساسيات الحاسب الآلي\n🔹 مدخل إلى مهارات القرن 21\n🔹 السلامة والصحة المهنية",
        "2️⃣ الفصل الثاني": "📚 **مقررات الفصل التدريبي الثاني:**\n🔹 سلوك مهني\n🔹 لغة عربية 2\n🔹 لغة إنجليزية 2\n🔹 رياضيات 2\n🔹 التربية البدنية 2\n🔹 ثقافة إسلامية 2\n🔹 ورش تأسيسية\n🔹 تطبيقات الحاسب الآلي\n🔹 مهارات التواصل والتعاون\n🔹 التفكير الناقد والإبداعي",
        "3️⃣ الفصل الثالث": "📚 **مقررات الفصل التدريبي الثالث:**\n🔹 ثقافة إسلامية 3\n🔹 الرسم الهندسي\n🔹 بحث ومصادر المعلومات\n🔹 رياضيات 3\n🔹 لغة إنجليزية 3\n🔹 أجهزة وقياس\n🔹 أساسيات الكهرباء\n🔹 أساسيات الإلكترونيات\n🔹 تطبيقات مفتوحة المصدر",
        "4️⃣ الفصل الرابع": "📚 **مقررات الفصل التدريبي الرابع:**\n🔹 مقدمة في ريادة الأعمال\n🔹 تقنيات الانترنت\n🔹 مكونات الحاسب 1\n🔹 لغة برمجة 1\n🔹 أساسيات الشبكات\n🔹 رسم الشبكات بالحاسب\n🔹 أساسيات نظام لينكس\n🔹 أنشطة مهنية",
        "5️⃣ الفصل الخامس": "📚 **مقررات الفصل التدريبي الخامس:**\n🔹 مكونات الحاسب 2\n🔹 صيانة الأجهزة الكفية\n🔹 لغة برمجة 2\n🔹 تمديد الكيابل النحاسية\n🔹 شبكات الحاسب\n🔹 نظام تشغيل الشبكة 1\n🔹 مشاريع إنتاجية\n🔹 أنشطة مهنية 2",
        "6️⃣ الفصل السادس": "📚 **مقررات الفصل التدريبي السادس:**\n🔹 مبادئ قواعد البيانات\n🔹 طرفيات الحاسب\n🔹 مهارات صيانة الحاسب\n🔹 تمديد كيابل الألياف الضوئية\n🔹 نظام تشغيل الشبكة 2\n🔹 تدريب إنتاجي\n🔹 أنشطة مهنية 3",
        "🖥️ برامج فصلية": "📚 **البرامج القصيرة:**\n🔹 **برنامج إدخال البيانات ومعالجة النصوص**\nيُعد هذا البرنامج دورة مستقلة عن خطة الدبلوم."
    }

    if text in term_plans:
        reply_content = f"{term_plans[text]}\n\n🔗 **لتحميل الحقائب التدريبية:**\n{DRIVE_LINK}"
        await update.message.reply_text(reply_content, parse_mode='Markdown', disable_web_page_preview=True)
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 اختر الفصل التدريبي المطلوب 👇", reply_markup=get_plans_menu())
        return

    # --- بقية الخدمات ---
    if text == "🕹️ قسم الألعاب والتحديات":
        await update.message.reply_text("🕹️ **ساحة التحدي والمنافسة**", reply_markup=get_games_menu(), parse_mode='Markdown')
        return

    if text == "🤖 المعلم الذكي (اسألني)":
        ai_sessions[user_id] = True
        await update.message.reply_text("🤖 اكتب سؤالك التقني الآن وسأشرحه لك فوراً...", reply_markup=get_back_menu())
        return

    if ai_sessions.get(user_id) == True:
        update_stat("ai_questions")
        status_msg = await update.message.reply_text("⏳ جاري التفكير...")
        try:
            prompt = f"أنت معلم حاسب آلي سعودي، أجب بوضوح على: {text}"
            response = await ai_model.generate_content_async(prompt)
            await status_msg.delete()
            await update.message.reply_text(response.text)
        except:
            await status_msg.delete()
            await update.message.reply_text("⚠️ المعلم الذكي غير متاح حالياً.")
        return

    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        scores = load_json(SCORES_FILE)
        user_data = scores.get(user_id, {"answered": []})
        available = [i for i in range(len(QUESTIONS)) if i not in user_data.get("answered", [])]
        if not available:
            await update.message.reply_text("🎉 أكملت جميع تحديات الأسبوع!")
            return
        q_idx = random.choice(available)
        active_challenges[user_id] = time.time()
        keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans_{q_idx}_{i}")] for i, opt in enumerate(QUESTIONS[q_idx]['options'])]
        await update.message.reply_text(f"❓ {QUESTIONS[q_idx]['q']}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if text == "🏆 بطل الأسبوع":
        scores = load_json(SCORES_FILE)
        if not scores:
            await update.message.reply_text("📉 لا يوجد نقاط بعد.")
            return
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        top = sorted_scores[0][1]
        await update.message.reply_text(f"🥇 بطل الأسبوع الحالي: {top['name']}\n🌟 الرصيد: {top['score']} نقطة")
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 أرسل رقمك التدريبي الآن للبحث..")
        return

    if text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 أرسل صورة العذر واكتب رقمك التدريبي في الوصف.")
        return

    if text == "📰 أخبار القسم والمعهد":
        await update.message.reply_text("📰 الأسبوع القادم موعد اختبارات الفترة الأولى.\n🔗 [حساب المعهد](https://x.com/tvtc_m_buraidah)")
        return
        
    if text == "📚 الحقائب التدريبية":
        await update.message.reply_text(f"📚 مستودع الحقائب: {DRIVE_LINK}")
        return

    if text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 منصة تقني: https://tvtclms.edu.sa\n بوابة رايات: https://rayat.tvtc.gov.sa")
        return

    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 الموقع الجغرافي للقسم:\nhttps://maps.app.goo.gl/3wG8F4")
        return

    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'): await update.message.reply_photo(photo=open('calendar.jpg', 'rb'))
        else: await update.message.reply_text("⚠️ ملف التقويم غير متوفر.")
        return

    if text == "👨‍🏫 تواصل مع رئيس القسم":
        update_stat("contact_clicks")
        await update.message.reply_text(f"👨‍🏫 تواصل مباشر: {TELEGRAM_CONTACT_LINK}")
        return

    if text.isdigit():
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            result = df[df['stu_num'].astype(str).str.strip() == text]
            if not result.empty:
                name = result.iloc[0]['stu_nam']
                msg = f"✅ النتائج لـ: {name}\n"
                for _, row in result.iterrows(): msg += f"📖 {row['c_nam']}: %{row['parsnt']}\n"
                await update.message.reply_text(msg)
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: await update.message.reply_text("⚠️ خطأ في قراءة ملف البيانات.")
        return

    await update.message.reply_text("⚠️ اختر خدمة من القائمة 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ يجب كتابة الرقم التدريبي في الوصف.")
        return
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد:\nالبيانات: {update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للمسؤول.")
    except: await update.message.reply_text("⚠️ خطأ في إرسال العذر.")

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
            msg = "🎉 صح! +10 نقاط."
        else: msg = "❌ خطأ!"
        user_info["answered"].append(q_idx)
        scores[user_id] = user_info
        save_json(SCORES_FILE, scores)
        await query.edit_message_text(f"{QUESTIONS[q_idx]['q']}\n\n{msg}")

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()

if __name__ == '__main__':
    main()
