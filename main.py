    # --- البحث في ملف البيانات بالرقم ---
    try:
        # قراءة الملف
        df = pd.read_csv('data.csv', sep=';', encoding='utf-8-sig')
        
        # 🧹 سطر التنظيف: يزيل أي مسافات مخفية من أسماء الأعمدة تلقائياً
        df.columns = df.columns.str.strip()
        
        # أسماء الأعمدة 
        col_id = 'id'    
        col_name = 'name' 
        col_subject = 'c_nam'
        col_subject_num = 'c_number'
        col_absence = 'apsent'
