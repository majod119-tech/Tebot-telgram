import os
import subprocess
import json
import io
from flask import Flask, request, jsonify

app = Flask(__name__)

# الاتصال بالذاكرة الحية (MongoDB)
MONGO_URI = os.environ.get("MONGODB_URI", "").strip()
db_collection = None
rayat_collection = None
if MONGO_URI:
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        db_collection = client["computer_dept_db"]["trainees"]
        rayat_collection = client["computer_dept_db"]["rayat_data"]
        client.admin.command('ping')
    except Exception as e:
        print("خطأ صامت في القاعدة:", e)

@app.route('/')
def home():
    return "OpenClaw Rayat Analyst is Online!"

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("message", "").strip()
        clean_msg = user_message.replace("أ", "ا").replace("إ", "ا").lower()

        # 🧹 أمر الطوارئ: تفريغ قاعدة رايات يدوياً
        if clean_msg == "تفريغ رايات":
            if rayat_collection is not None:
                rayat_collection.delete_many({})
                return jsonify({"response": "✅ تم كنس وتفريغ جميع بيانات رايات من قاعدة البيانات بنجاح."}), 200
            else:
                return jsonify({"response": "❌ قاعدة البيانات غير متصلة."}), 200

        # 1️⃣ حفظ بيانات رايات (مع درع الحماية ضد التكرار)
        if user_message.startswith("حفظ_بيانات_رايات\n"):
            if rayat_collection is None:
                return jsonify({"response": "❌ خطأ: لم يتم الاتصال بقاعدة البيانات MongoDB."}), 200
            
            try:
                csv_data = user_message.split("\n", 1)[1]
                import pandas as pd
                
                df = pd.read_csv(io.StringIO(csv_data))
                
                # 🛡️ السطر السحري: مسح أي تكرار في البيانات تلقائياً
                df = df.drop_duplicates()
                records = df.to_dict('records')
                
                # مسح البيانات القديمة بالكامل وحفظ الجديدة النظيفة
                rayat_collection.delete_many({})
                rayat_collection.insert_many(records)
                
                return jsonify({"response": f"✅ **نجاح ساحق!**\nتم تنظيف الملف من التكرار، وحفظ {len(records)} متدرب في قاعدة (رايات) بنجاح.\nالنظام جاهز للتحليل."}), 200
            except Exception as e:
                return jsonify({"response": f"⚠️ خطأ أثناء حفظ البيانات: {str(e)}"}), 200

        # 2️⃣ تحليل بيانات رايات من القاعدة
        if clean_msg.startswith("حلل رايات") or clean_msg.startswith("رايات"):
            if rayat_collection is None or rayat_collection.count_documents({}) == 0:
                return jsonify({"response": "❌ قاعدة بيانات رايات فارغة! الرجاء رفع ملف رايات في التلجرام أولاً."}), 200
            
            try:
                import pandas as pd
                records = list(rayat_collection.find({}, {"_id": 0}))
                df = pd.DataFrame(records)
                
                sample_data = df.head(50).to_json(orient="records", force_ascii=False)
                columns_list = ", ".join(df.columns.tolist())
                total_rows = len(df)

                api_key = os.environ.get("GEMINI_API_KEY", "").strip()
                if api_key:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    
                    selected_model = 'gemini-pro'
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                            selected_model = m.name.replace('models/', '')
                            break
                            
                    model = genai.GenerativeModel(selected_model)
                    
                    ai_prompt = f"""
أنت (OpenClaw)، خبير استشاري ومحلل بيانات تعمل لدى رئيس قسم الحاسب.
هذه بيانات تم سحبها من قاعدة (رايات)، وتحتوي على {total_rows} سجل خالي من التكرار.
الأعمدة: {columns_list}

عينة البيانات:
{sample_data}

بناءً على الأرقام، قدم تقريراً إدارياً احترافياً:
1. نظرة عامة (كم عدد الطلاب، حالة الحضور).
2. تنبؤ استباقي: هل هناك طلاب معرضون للحرمان؟ اذكرهم.
3. توصية إدارية فورية.
                    """
                    ai_response = model.generate_content(ai_prompt)
                    reply = f"📊 *تحليل ذكي لقاعدة رايات الحية:*\n\n" + ai_response.text
                    return jsonify({"response": reply}), 200
                else:
                    return jsonify({"response": "⚠️ مفتاح الذكاء الاصطناعي مفقود."}), 200
            except Exception as e:
                return jsonify({"response": f"⚠️ خطأ أثناء التحليل: {str(e)}"}), 200

        # 3️⃣ الأوامر العامة والـ RAG
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                selected_model = 'gemini-pro'
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                        selected_model = m.name.replace('models/', '')
                        break
                model = genai.GenerativeModel(selected_model)
                sys_inst = "أنت مساعد تنفيذي قوي لرئيس قسم الحاسب، اسمك OpenClaw. أجب باختصار واحترافية: "
                ai_response = model.generate_content(sys_inst + user_message)
                return jsonify({"response": "🧠 رد المستشار:\n" + ai_response.text}), 200
            except Exception as e:
                return jsonify({"response": "⚠️ خطأ في الذكاء الاصطناعي: " + str(e)}), 200
        else:
            return jsonify({"response": "الأمر وصل: " + user_message}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


