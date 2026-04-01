import os
import random
import json
import urllib.request
import xml.etree.ElementTree as ET
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# استدعاء الإعدادات
from bot_settings import SCORES_FILE, STATS_FILE, SEP

# دالة مساعدة لقراءة الملفات
def load_json_local(f):
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: return {}
    return {}

# استدعاء بنك الأسئلة
try:
    from questions_bank import QUESTIONS
except ImportError:
    QUESTIONS = [{"q": "سؤال تجريبي", "options": ["1", "2"], "answer": 1}]

# ==========================================
# محرك الخدمات الإضافية والترفيهية
# ==========================================
async def process_extra_features(update: Update, text: str):
    if text == "📅 التقويم التدريبي":
        caption_msg = "📅 *التقويم للعام التدريبي الحالي:*"
        if os.path.exists('calendar.pdf'):
            return await update.message.reply_document(document=open('calendar.pdf', 'rb'), caption=caption_msg, parse_mode='Markdown')
        elif os.path.exists('calendar.jpg'):
            return await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), caption=caption_msg, parse_mode='Markdown')
        else:
            return await update.message.reply_text(caption_msg + "\n⚠️ *(جاري تحديث التقويم)*", parse_mode='Markdown')

    if text == "🎮 تحدي الأسبوع":
        # تحديث إحصائية لعب التحدي
        s = load_json_local(STATS_FILE)
        s["quiz_attempts"] = s.get("quiz_attempts", 0) + 1
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as file: json.dump(s, file, ensure_ascii=False)
        except: pass

        try:
            q = random.choice(QUESTIONS)
            kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
            return await update.message.reply_text(f"❓ *تحدي الأسبوع:*\n\n{q['q']}\n\n👇 اختر الإجابة الصحيحة:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        except: return await update.message.reply_text("⚠️ لا توجد أسئلة مسجلة حالياً في بنك الأسئلة.")

    if text == "🏆 بطل الأسبوع":
        sc = load_json_local(SCORES_FILE)
        if not sc: return await update.message.reply_text("📉 لا توجد نقاط مسجلة حالياً، كن أنت البطل الأول!")
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        return await update.message.reply_text(f"🏆 *بطل الأسبوع:* {top['name']}\n🌟 *النقاط:* {top['score']}", parse_mode='Markdown')

    if text == "🌐 أخبار التقنية":
        try:
            req = urllib.request.Request("https://www.tech-wd.com/wd/feed/", headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            root = ET.fromstring(response.read())
            news_msg = f"🌐 *آخر الأخبار التقنية*\n{SEP}\n"
            for i, item in enumerate(root.findall('.//item')):
                if i >= 3: break
                news_msg += f"🔹 [{item.find('title').text}]({item.find('link').text})\n\n"
            return await update.message.reply_text(news_msg, parse_mode='Markdown', disable_web_page_preview=True)
        except:
            return await update.message.reply_text("⚠️ تعذر جلب الأخبار حالياً، حاول لاحقاً.")
