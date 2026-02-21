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

# --- 1. سيرفر الويب المطور (Dashboard) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            stats = load_json(STATS_FILE)
            scores = load_json(SCORES_FILE)
            html = f"""
            <html><head><title>لوحة قيادة قسم الحاسب</title>
            <style>
                body {{ font-family: 'Segoe UI'; direction: rtl; background: #f4f7f6; padding: 20px; text-align: center; }}
                .card-container {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }}
                .card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 200px; }}
                .card p {{ font-size: 24px; color: #27ae60; font-weight: bold; }}
                table {{ margin: 30px auto; width: 90%; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border-collapse: collapse; }}
                th, td {{ padding: 15px; border-bottom: 1px solid #ddd; }}
                th {{ background: #27ae60; color: white; }}
            </style></head><body>
            <h1>📊 لوحة إحصائيات النظام الذكي</h1>
            <div class="card-container">
                <div class="card"><h3>👥 المستخدمين</h3><p>{len(stats.get('users_list', []))}</p></div>
                <div class="card"><h3>🤖 أسئلة الذكاء</h3><p>{stats.get('ai_questions', 0)}</p></div>
                <div class="card"><h3>🎮 التحديات</h3><p>{stats.get('quiz_attempts', 0)}</p></div>
            </div>
            <h2>🏆 قائمة المتصدرين</h2>
            <table><tr><th>الاسم</th><th>النقاط</th><th>التحديات</th></tr>
            {"".join([f"<tr><td>{v['name']}</td><td>{v['score']}</td><td>{len(v.get('answered', []))}</td></tr>" for k,v in sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)])}
            </table></body></html>"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot Server Online")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. الإعدادات والبيانات الأساسية ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
TELEGRAM_CONTACT_LINK = "https://t.me/majod119"
SEP = "\n━━━━━━━━━━━━━━\n"

# تغذية عقل الذكاء الاصطناعي
AI_KNOWLEDGE = f"""أنت المساعد الذكي لقسم الحاسب. معلوماتك:
- الحقائب التدريبية: {DRIVE_LINK}
- الغياب: تنبيه عند 15% وحرمان عند 20%.
- إذا سألك الطالب عن درجاته أو غيابه، اطلب منه كتابة الرقم التدريبي في القائمة الرئيسية.
- أنت تشرح مواد الشبكات والبرمجة والصيانة بأسلوب سعودي تقني مهذب."""

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
    except: ai_model = None

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"

def load_json(f): return json.load(open(f, "r")) if os.path.exists(f) else {}
def save_json(f, d): json.dump(d, open(f, "w"))
def update_stat(cat):
    s = load_json(STATS_FILE); s[cat] = s.get(cat, 0) + 1; save_json(STATS_FILE, s)

ai_sessions = {}
feedback_sessions = {}
active_challenges = {}

TECH_TIPS = [
    "💡 استخدم اختصار Win + L لقفل جهازك فوراً.",
    "🛡️ لا تستخدم نفس كلمة المرور لأكثر من حساب.",
    "🚀 في بايثون، المسافات البادئة (Indentation) أساسية لعمل الكود.",
    "🌐 عنوان 127.0.0.1 يشير دائماً لجهازك المحلي."
]

QUESTIONS = [
    {"q": "ما هو عنوان الـ IP الذي يُعرف بـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1},
    {"q": "أي من المكونات يعتبر 'العقل المدبر' للحاسب؟", "options": ["HDD", "RAM", "CPU", "Motherboard"], "answer": 2}
]

# --- 3. تصميم القوائم (الواجهة المكتملة) ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المعلم الذكي (الدليل الشامل)"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["👨‍🏫 تواصل مع رئيس القسم"],
        ["🕹️ قسم الألعاب والإضافات"]
    ], resize_keyboard=True, is_persistent=True)

def get_plans_menu():
    return ReplyKeyboardMarkup([
        ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"],
        ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"],
        ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"],
        ["🖥️ برامج فصلية"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_games_menu():
    return ReplyKeyboardMarkup([
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"],
        ["💡 نصيحة تقنية", "📬 صندوق المقترحات"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_back_menu(): return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 4. المنطق البرمجي الشامل ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    stats = load_json(STATS_FILE); users = stats.get("users_list", [])
    if user_id not in users: users.append(user_id); stats["users_list"] = users; save_json(STATS_FILE, stats)
    ai_sessions[user_id] = False
    feedback_sessions[user_id] = False
    await update.message.reply_text(f"أهلاً بك {update.effective_user.first_name} في نظام قسم الحاسب الذكي 💻{SEP}اختر من القائمة أدناه للبدء 👇", reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    # الرجوع
    if text == "🔙 الرجوع للقائمة الرئيسية":
        ai_sessions[user_id] = False; feedback_sessions[user_id] = False
        await update.message.reply_text("🏠 عدنا للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # 🤖 المعلم الذكي
    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        ai_sessions[user_id] = True
        await update.message.reply_text(f"🤖 **مرحباً بك في الدليل الذكي**{SEP}اسألني عن (المواد، الحقائب، الأنظمة) أو أي موضوع تقني وسأجيبك فوراً 👇", reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        update_stat("ai_questions")
        status_msg = await update.message.reply_text("⏳ جاري التفكير...")
        try:
            resp = ai_model.generate_content(f"{AI_KNOWLEDGE}\nالمتدرب: {text}")
            await status_msg.delete()
            await update.message.reply_text(f"📝 **رد المعلم الذكي:**\n{SEP}{resp.text}", parse_mode='Markdown')
        except: await status_msg.delete(); await update.message.reply_text("⚠️ المعلم مشغول حالياً.")
        return

    # 📬 صندوق المقترحات
    if text == "📬 صندوق المقترحات":
        feedback_sessions[user_id] = True
        await update.message.reply_text(f"📬 **صندوق المقترحات**{SEP}اكتب مقترحك الآن ليصل للإدارة مباشرة 👇", reply_markup=get_back_menu())
        return

    if feedback_sessions.get(user_id) == True:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 مقترح من {update.effective_user.first_name}:\n{text}")
        feedback_sessions[user_id] = False
        await update.message.reply_text("✅ تم إرسال مقترحك، شكراً لك!", reply_markup=get_games_menu())
        return

    # 📄 الخطط التدريبية (المحتوى الكامل)
    term_plans = {
        "1️⃣ الفصل الأول": "📚 الفصل 1: أساسيات الحاسب، ثقافة إسلامية 1، رياضيات 1، إنجليزية 1.",
        "2️⃣ الفصل الثاني": "📚 الفصل 2: تطبيقات الحاسب، سلوك مهني، رياضيات 2، إنجليزية 2.",
        "3️⃣ الفصل الثالث": "📚 الفصل 3: أساسيات الكهرباء، أجهزة وقياس، رياضيات 3، تطبيقات مفتوحة.",
        "4️⃣ الفصل الرابع": "📚 الفصل 4: شبكات، مكونات حاسب 1، لغة برمجة 1، تقنيات الإنترنت.",
        "5️⃣ الفصل الخامس": "📚 الفصل 5: شبكات متقدمة، صيانة أجهزة، لغة برمجة 2، تمديد نحاس.",
        "6️⃣ الفصل السادس": "📚 الفصل 6: ألياف ضوئية، قواعد بيانات، صيانة حاسب، تشغيل شبكات.",
        "🖥️ برامج فصلية": "📚 دورة إدخال البيانات ومعالجة النصوص."
    }
    if text in term_plans:
        await update.message.reply_text(f"{term_plans[text]}{SEP}🔗 الحقائب: {DRIVE_LINK}", parse_mode='Markdown')
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 اختر الفصل:", reply_markup=get_plans_menu()); return

    # 🕹️ قسم الألعاب
    if text == "🕹️ قسم الألعاب والإضافات":
        await update.message.reply_text(f"🕹️ **ساحة التفاعل**{SEP}اختر من الأسفل 👇", reply_markup=get_games_menu(), parse_mode='Markdown'); return

    if text == "💡 نصيحة تقنية":
        await update.message.reply_text(f"💡 **نصيحة اليوم:**\n{SEP}{random.choice(TECH_TIPS)}", parse_mode='Markdown'); return

    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        q = random.choice(QUESTIONS)
        active_challenges[user_id] = time.time()
        kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
        await update.message.reply_text(f"❓ {q['q']}", reply_markup=InlineKeyboardMarkup(kb)); return

    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: await update.message.reply_text("📉 لا يوجد نقاط."); return
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        await update.message.reply_text(f"🥇 البطل: {top['name']}\n🌟 النقاط: {top['score']}"); return

    # 📊 استعلام الغياب (Excel)
    if text == "📊 استعلام الغياب":
        await update.message.reply_text(f"🔎 **استعلام الغياب**{SEP}أرسل رقمك التدريبي الآن للبحث.."); return

    if text.isdigit():
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            res = df[df['stu_num'].astype(str).str.strip() == text]
            if not res.empty:
                m = f"✅ **النتائج لـ:** `{res.iloc[0]['stu_nam']}`{SEP}"
                for _, r in res.iterrows(): m += f"📖 {r['c_nam']}: %{r['parsnt']}\n"
                await update.message.reply_text(m, parse_mode='Markdown')
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: await update.message.reply_text("⚠️ ملف الغياب غير متوفر.")
        return

    # خدمات أخرى
    if text == "📝 رفع الغياب والأعذار": await update.message.reply_text(f"📝 **رفع العذر**{SEP}أرسل صورة العذر واكتب رقمك في الوصف."); return
    if text == "📚 الحقائب التدريبية": await update.message.reply_text(f"📚 الحقائب: {DRIVE_LINK}"); return
    if text == "🔗 منصة تقني ورايات": await update.message.reply_text("🌐 تقني: https://tvtclms.edu.sa\nرايات: https://rayat.tvtc.gov.sa"); return
    if text == "📍 موقع القسم": await update.message.reply_text("📍 الموقع:\nhttp://googleusercontent.com/maps.google.com/3"); return
    if text == "📰 أخبار القسم والمعهد": await update.message.reply_text("📰 الأسبوع القادم اختبارات الفترة الأولى."); return
    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'): await update.message.reply_photo(photo=open('calendar.jpg', 'rb'))
        else: await update.message.reply_text("⚠️ ملف التقويم مفقود."); return
    if text == "👨‍🏫 تواصل مع رئيس القسم": 
        update_stat("contact_clicks")
        await update.message.reply_text(f"👨‍🏫 تواصل مباشر: {TELEGRAM_CONTACT_LINK}"); return

    await update.message.reply_text("⚠️ اختر من القائمة 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption: await update.message.reply_text("⚠️ اكتب رقمك التدريبي في الوصف."); return
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر من {update.effective_user.first_name}:\n{update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ تم استلام عذرك بنجاح.");
    except: await update.message.reply_text("⚠️ خطأ في الإرسال.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id = str(query.from_user.id); await query.answer()
    if query.data.startswith("ans_"):
        parts = query.data.split("_"); q_idx, sel = int(parts[1]), int(parts[2])
        sc = load_json(SCORES_FILE); ui = sc.get(user_id, {"name": query.from_user.first_name, "score": 0, "answered": []})
        if sel == QUESTIONS[q_idx]["answer"]: ui["score"] += 10; m = "🎉 صح! +10"
        else: m = "❌ خطأ"
        ui["answered"].append(q_idx); sc[user_id] = ui; save_json(SCORES_FILE, sc)
        await query.edit_message_text(f"{QUESTIONS[q_idx]['q']}{SEP}{m}")

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 تم تشغيل النسخة الكاملة والمصلحة...")
    app.run_polling()

if __name__ == '__main__': main()
