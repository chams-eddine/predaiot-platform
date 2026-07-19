import pandas as pd

def prepare_oman_data():
    prod_path = 'Monthly electricity production by energy source (MWh), by year.xlsx'
    peak_path = 'Monthly electricity  peak demand by system (MW).xlsx'

    print("📂 جاري معالجة البيانات باستخدام المسميات الدقيقة...")

    # تحميل البيانات
    df_prod = pd.read_excel(prod_path, engine='openpyxl')
    df_peak = pd.read_excel(peak_path, engine='openpyxl')

    # تنظيف وتوحيد المسميات (بناءً على ما ظهر في الـ Terminal)
    # ملاحظة: سنستخدم أسماء الأعمدة الفعلية من ملفاتك
    df_prod.rename(columns={
        'اسم الأصل': 'Date',
        'انتاج  الكهرباء الشهري لكل سنة MWh حسب مصدر الانتاج ': 'Production_MWh'
    }, inplace=True)

    df_peak.rename(columns={
        'اسم الأصل': 'Date',
        'ذروة الطلب على الكهرباء بشكل شهري لكل نظام  MW ': 'Peak_Demand_MW'
    }, inplace=True)

    # تحويل التاريخ (بما أن 'اسم الأصل' يحتوي على التاريخ، سنعالجه)
    # ملاحظة: إذا كان التاريخ موجوداً في صفوف بيانات، سنقوم بتصحيح ذلك
    df_prod['Date'] = pd.to_datetime(df_prod['Date'], errors='coerce')
    df_peak['Date'] = pd.to_datetime(df_peak['Date'], errors='coerce')

    # الدمج
    df_merged = pd.merge(df_prod, df_peak, on='Date', how='inner')

    # تجهيز للـ API الخاص بـ PREDAIOT
    df_merged['hour'] = range(len(df_merged))
    df_merged['price'] = 25.0
    df_merged['actual_discharge'] = df_merged['Production_MWh']

    # الحفظ
    df_merged.to_csv('oman_integrated_data.csv', index=False)
    print("✅ تم الدمج بنجاح! الملف جاهز للرفع: oman_integrated_data.csv")

if __name__ == "__main__":
    prepare_oman_data()
