import asyncio
import requests
from config import GEMINI_API_KEY, AI_KNOWLEDGE

async def get_gemini_response(user_query):
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر."
    
    # دالة الاتصال المباشر والآمن (بدون استخدام مكتبة genai)
    def fetch_from_api():
        # الرابط الرسمي الصحيح والمباشر لنموذج Gemini 1.5 Flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "system_instruction": {
                "parts": {"text": AI_KNOWLEDGE}
            },
            "contents": [
                {"parts": [{"text": user_query}]}
            ]
        }
        
        # إرسال الطلب مع مهلة 20 ثانية لتجنب التعليق
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status() # التحقق من عدم وجود أخطاء (مثل 404 أو 403)
        
        # استخراج النص من الرد مباشرة
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']

    try:
        # تشغيل الدالة في مسار آمن لكي لا يتجمد تليجرام
        answer = await asyncio.to_thread(fetch_from_api)
        return answer[:4000]
        
    except requests.exceptions.HTTPError as e:
        error_msg = str(e)
        if "400" in error_msg or "403" in error_msg:
            return "⚠️ خطأ: مفتاح الذكاء الاصطناعي (API Key) غير صالح. تأكد منه في إعدادات Koyeb."
        return f"⚠️ خطأ في سيرفرات جوجل:\n{error_msg}"
        
    except Exception as e:
        return f"⚠️ خطأ في الاتصال:\n{e}"
