import requests
import pandas as pd
import os

# 1. الدالة اللي تسحب بيانات الخطة من مجلد data
def load_curriculum_data():
    # المسار المحدث لملف الخطة التدريبية الجديد
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx') 
    try:
        df = pd.read_excel(file_path)
        # تحويل الجدول لنص عشان يفهمه الذكاء الاصطناعي
        text_data = df.to_string(index=False)
        return f"\n--- بيانات الخطة التدريبية للإصدار الثالث ---\n{text_data}\n-----------------------------------\n"
    except Exception as e:
        print(f"خطأ في قراءة ملف الخطة: {e}")
        return ""

# حفظ الخطة في متغير
curriculum_context = load_curriculum_data()

# 2. تجهيز شخصية البوت (التعليمات الأساسية)
SYSTEM_PROMPT = f"""
أنت المساعد الذكي الرسمي لقسم الحاسب بالمعهد الصناعي الثانوي ببريدة.
مهمتك مساعدة المتدربين والرد على استفساراتهم باحترافية ودقة.
يجب عليك الاعتماد بشكل أساسي على الخطة التدريبية التالية للإجابة على أي سؤال يخص المناهج والساعات:
{curriculum_context}
"""

# 3. دالة الاتصال بسيرفر OpenClaw
def ask_openclaw_api(user_message):
    # الرابط الصحيح والمغلق بعلامات التنصيص
    API_URL = "https://openclaw-server-2j6r.onrender.com/api/chat" 
    
    # 💡 حقن الخطة مع سؤال المتدرب عشان السيرفر يفهم السياق ويجاوب من الخطة
    full_message = f"{SYSTEM_PROMPT}\n\nسؤال المتدرب: {user_message}"
    
    try:
        # إرسال الطلب للسيرفر (ننتظر 90 ثانية كحد أقصى)
        response = requests.post(API_URL, json={"message": full_message}, timeout=90)
        
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
