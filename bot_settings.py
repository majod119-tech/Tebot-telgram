import os
import json

# --- 🌟 إعدادات الروابط والمفاتيح 🌟 ---
TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.getenv("MONGODB_URI")
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com/api/chat"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 🌟 ثوابت النظام والإدارة 🌟 ---
ADMIN_ID = "10073498"
GROUP_ID = "-1003701324722"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

# --- 🌟 ملفات البيانات المحلية 🌟 ---
SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"
INTERROGATIONS_FILE = "interrogations.json"

# --- 🌟 دوال مساعدة (JSON) 🌟 ---
def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: return {}
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except: pass

# --- 🌟 المحتوى الثابت 🌟 ---
try:
    from questions_bank import QUESTIONS
except Exception as e:
    QUESTIONS = [{"q": "ما هو عنوان الـ IP لـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}]

AI_KNOWLEDGE = (
    "أنت 'المساعد الرقمي'، مساعد ذكي ورسمي لقسم الحاسب الآلي في المعهد الصناعي الثانوي ببريدة. "
    "مهمتك الإجابة على جميع استفسارات المستخدمين بشكل مبسط، ودي، ومختصر جداً.\n"
    f"رابط الحقائب التدريبية: {DRIVE_LINK}).\n"
)
