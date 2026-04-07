import requests
import pandas as pd
import os

# أكيد عندك استدعاء لمكتبة جيميناي هنا مثل:
# import google.generativeai as genai 

# 1. الدالة اللي تسحب بيانات الخطة
def load_curriculum_data():
    # عدل المسار واسم الملف حسب مكان رفعك له
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'اسم_ملفك_هنا.xlsx') 
    try:
        df = pd.read_excel(file_path)
        text_data = df.to_string(index=False)
        return f"\nبيانات الخطة التدريبية (الإصدار الثالث):\n{text_data}"
    except Exception as e:
        print(f"خطأ في قراءة الخطة: {e}")
        return ""

# حفظ الخطة في متغير
curriculum_context = load_curriculum_data()

# 2. دمج الخطة في شخصية البوت
SYSTEM_PROMPT = f"""
أنت المساعد الذكي الرسمي لقسم الحاسب بالمعهد الصناعي الثانوي ببريدة.
مهمتك مساعدة المتدربين والرد على استفساراتهم باحترافية.
اعتمد بشكل أساسي على هذه الخطة التدريبية المعتمدة للإجابة على الأسئلة:
{curriculum_context}
"""

# ... (وبعدها يكمل كودك العادي حق تجهيز الموديل)



def ask_openclaw_api(user_message):
    # الرابط الصحيح والمغلق بعلامات التنصيص
    API_URL = "https://openclaw-server-2j6r.onrender.com/api/chat" 
    
    try:
        # إرسال الطلب للسيرفر (ننتظر 30 ثانية كحد أقصى)
        response = requests.post(API_URL, json={"message": user_message}, timeout=90)
        
        # 🛡️ الدرع الأول: السيرفر متصل لكنه زعلان (رفض الطلب)
        if response.status_code != 200:
            return f"⚠️ **السيرفر رفض الطلب!**\nكود الخطأ: `{response.status_code}`\nرسالة السيرفر: `{response.text[:150]}`"

        # 🛡️ الدرع الثاني: تفكيك الرد
        try:
            data = response.json()
            return data.get("response", data.get("answer", "✅ السيرفر رد، لكن لم أجد الإجابة داخل البيانات."))
            
        except requests.exceptions.JSONDecodeError:
            return f"⚠️ **خطأ في صيغة الرد!** السيرفر رد بنص عادي (ليس JSON).\nشكل الرد: `{response.text[:150]}...`"

    # 🛡️ الدرع الثالث: السيرفر ما يرد (ميت)
    except requests.exceptions.Timeout:
        return "⚠️ **انتهى الوقت (Timeout)!** سيرفر OpenClaw عليه ضغط أو مغلق."
        
    # 🛡️ الدرع الرابع: الرابط غلط أو السيرفر محذوف
    except requests.exceptions.ConnectionError:
        return "⚠️ **فشل الاتصال!** تأكد أن رابط سيرفر OpenClaw يعمل وأن السيرفر قيد التشغيل."
        
    except Exception as e:
        return f"⚠️ **خطأ غير متوقع:** `{str(e)}`"
