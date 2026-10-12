import asyncio
import requests
from config import GEMINI_API_KEY, AI_KNOWLEDGE

async def get_gemini_response(user_query):
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر."
    
    # دالة الاتصال المباشر بجوجل (بدون مكتبات معقدة)
    def fetch_from_api():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "system_instruction": {
                "parts": {"text": AI_KNOWLEDGE}
            },
            "contents": [
                {"parts": [{"text": user_query}]}
            ]
        }
        
        # إرسال الطلب مع حد أقصى للوقت (15 ثانية)
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status() # التأكد من نجاح الطلب
        
        # استخراج النص من الرد
        return response.json()['candidates'][0]['content']['parts'][0]['text']

    try:
        # تشغيل الاتصال المباشر في مسار آمن
        answer = await asyncio.to_thread(fetch_from_api)
        return answer[:4000]
        
    except requests.exceptions.HTTPError as e:
        # إذا كان المفتاح خاطئ سيخبرك هنا
        if "400" in str(e) or "403" in str(e):
            return "⚠️ خطأ: مفتاح الذكاء الاصطناعي (API Key) غير صالح. تأكد منه في Koyeb."
        return f"⚠️ خطأ في السيرفر: {e}"
        
    except Exception as e:
        return f"⚠️ خطأ في الاتصال: {e}"
