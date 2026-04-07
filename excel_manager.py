import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.document:
        await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        return
        
    try:
        status_msg = await message.reply_text("⏳ جاري قراءة الملفين ومطابقة الأعمدة بذكاء... ثواني بس 🔍")
        
        # 1. تحميل الملف القديم من التيليجرام
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        # 2. فتح الملفين 
        wb_old = openpyxl.load_workbook(old_file_path, data_only=True)
        ws_old = wb_old.active
        
        # التأكد من اسم قالب الجودة
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        ws_new = wb_new.active 
        
        # 🌟 دالة البحث الذكي عن الأعمدة (مثل عين الإنسان) 🌟
        def find_col_and_row(ws, keywords, search_rows=50):
            for r in range(1, search_rows):
                for c in range(1, ws.max_column + 1):
                    val = ws.cell(row=r, column=c).value
                    if val and any(k in str(val) for k in keywords):
                        return c, r
            return None, None

        # استخراج أماكن الأعمدة في الملف القديم أياً كان مكانها!
        old_week_col, _ = find_col_and_row(ws_old, ["سبوع"])
        old_unit_col, _ = find_col_and_row(ws_old, ["وحدات", "موضوع"])
        old_hours_col, _ = find_col_and_row(ws_old, ["ساعات"])
        old_goals_col, _ = find_col_and_row(ws_old, ["أهداف"])
        old_strat_col, _ = find_col_and_row(ws_old, ["ستراتيجية"])
        old_eval_col, _ = find_col_and_row(ws_old, ["آلية", "أدوات", "تقييم"])
        old_deg_col, _ = find_col_and_row(ws_old, ["درجة"])

        # استخراج أماكن الأعمدة في القالب الجديد
        new_week_col, header_row = find_col_and_row(ws_new, ["سبوع"])
        new_unit_col, _ = find_col_and_row(ws_new, ["وحدات", "موضوع"])
        new_hours_col, _ = find_col_and_row(ws_new, ["ساعات"])
        new_goals_col, _ = find_col_and_row(ws_new, ["أهداف"])
        new_strat_col, _ = find_col_and_row(ws_new, ["ستراتيجية"])
        new_eval_col, _ = find_col_and_row(ws_new, ["أدوات", "آلية"])
        new_deg_col, _ = find_col_and_row(ws_new, ["درجة"])

        # 🎯 تحديد صف البداية للبيانات في الملف القديم
        start_row_old = 1
        if old_week_col:
            for r in range(1, ws_old.max_row + 1):
                val = ws_old.cell(row=r, column=old_week_col).value
                if val and ("الأول" in str(val) or str(val).strip() == "1"):
                    start_row_old = r
                    break

        # 🎯 تحديد صف البداية في القالب الجديد (بمجرد ما يلقى كلمة الأول)
        start_row_new = None
        if new_week_col:
            for r in range(1, ws_new.max_row + 1):
                val = ws_new.cell(row=r, column=new_week_col).value
                if val and ("الأول" in str(val) or str(val).strip() == "1"):
                    start_row_new = r
                    break
        if not start_row_new:
            start_row_new = (header_row + 2) if header_row else 5

        # 🛡️ دالة الكتابة الآمنة لتخطي مشكلة الدمج
        def write_safe(ws, r, c, val):
            if not c or val is None: return
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    ws.cell(row=merged_range.min_row, column=merged_range.min_col).value = val
                    return
            cell.value = val

        # 🔄 عملية النقل الذكية
        current_new_row = start_row_new
        for r in range(start_row_old, ws_old.max_row + 1):
            week_val = ws_old.cell(row=r, column=old_week_col).value if old_week_col else None
            unit_val = ws_old.cell(row=r, column=old_unit_col).value if old_unit_col else None
            
            # تخطي الصفوف الفارغة بالكامل
            if not week_val and not unit_val:
                continue

            write_safe(ws_new, current_new_row, new_week_col, week_val)
            write_safe(ws_new, current_new_row, new_unit_col, unit_val)
            
            if old_hours_col: write_safe(ws_new, current_new_row, new_hours_col, ws_old.cell(row=r, column=old_hours_col).value)
            if old_goals_col: write_safe(ws_new, current_new_row, new_goals_col, ws_old.cell(row=r, column=old_goals_col).value)
            if old_strat_col: write_safe(ws_new, current_new_row, new_strat_col, ws_old.cell(row=r, column=old_strat_col).value)
            if old_eval_col: write_safe(ws_new, current_new_row, new_eval_col, ws_old.cell(row=r, column=old_eval_col).value)
            if old_deg_col: write_safe(ws_new, current_new_row, new_deg_col, ws_old.cell(row=r, column=old_deg_col).value)

            current_new_row += 1

        # 💾 حفظ وإرسال الملف
        output_filename = f"الخطة_المحدثة_v3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            await message.reply_document(document=doc, caption="🎉 تم النقل بذكاء بنجاح!\nالبوت قام بمطابقة الأعمدة القديمة مع القالب الجديد آلياً وتخطي جميع الخلايا المدمجة.")
            
        os.remove(old_file_path)
        os.remove(output_filename)
        await status_msg.delete()
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ غير متوقع: {str(e)}\nيرجى التأكد من أن الملف القديم يحتوي على جدول خطة واضح.")
        context.user_data['waiting_for_plan'] = False
