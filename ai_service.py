import requests

def ask_openclaw_api(user_message):
    # الرابط الصحيح والمغلق بعلامات التنصيص
    API_URL = "https://openclaw-server-2j6r.onrender.com/api/chat" 
    
    try:
        # إرسال الطلب للسيرفر (ننتظر 30 ثانية كحد أقصى)
        response = requests.post(API_URL, json={"message": user_message}, timeout=30)
        
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
