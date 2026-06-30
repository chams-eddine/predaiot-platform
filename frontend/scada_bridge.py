import requests
import time
import math
import random
from datetime import datetime

# ==========================================
# إعدادات جسر الأنظمة (SCADA Bridge Config)
# ==========================================
CLOUD_API_URL = "https://predaiot-platform.onrender.com/api/v1/audit"
POLL_INTERVAL_SECONDS = 60  # أرسل البيانات كل 60 ثانية (للتجربة السريعة، اجعله 300 للإنتاج الحقيقي)

def generate_live_scada_data():
    """
    هذه الدالة تحاكي قراءات أجهزة الاستشعار الحقيقية في الميدان.
    تولد 288 نقطة (24 ساعة) بناءً على الساعة الحالية في حاسوبك.
    """
    time_series = []
    actual_soc = 0.2
    e_max = 100
    
    # معرفة الساعة الحالية لجعل المحاكاة واقعية جداً
    current_hour_idx = datetime.now().hour * 12 + (datetime.now().minute // 5)

    for i in range(288):
        # إزاحة منحنى السعر ليكون الساعة الحالية هي نقطة الذروة أو الانخفاض
        basePrice = 30 + 70 * math.sin(((i - current_hour_idx) - 36) * (math.pi / 180))
        noise = (random.random() - 0.5) * 10
        price = max(0, float(f"{basePrice + noise:.2f}"))

        # محاكاة قراءات التيار/التفريغ الفعلية من العداد (PMU/RTU)
        actual_discharge = 0
        actual_charge = 0

        if price < 20 and actual_soc < 0.9:
            actual_charge = 40 # المحطة تشحن
        if price > 40 and price < 80 and actual_soc > 0.2:
            actual_discharge = 40 # المحطة تفرغ بسعر متوسط (خطأ بشري)
            
        max_possible_discharge = (actual_soc - 0.2) * e_max
        if actual_discharge > max_possible_discharge:
            actual_discharge = max_possible_discharge

        actual_soc = actual_soc + (actual_charge * 0.95 / e_max) - (actual_discharge / 0.95 / e_max)
        
        time_series.append({
            "hour": i, 
            "price": price, 
            "actual_discharge": actual_discharge
        })

    return time_series

def send_to_predaiot_cloud():
    """إرسال البيانات إلى السحابة"""
    payload = {
        "asset": { "p_max": 50, "e_max": 100, "soc_init": 0.2, "eta_ch": 0.95, "eta_dis": 0.95, "deg_cost": 5.0 },
        "time_series": generate_live_scada_data()
    }

    try:
        # ملاحظة: في المرة الأولى قد يستغرق الأمر 30-60 ثانية لأن سيرفر Render يستيقظ من النوم (Cold Start)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] جاري إرسال البيانات الحية إلى السحابة...")
        response = requests.post(CLOUD_API_URL, json=payload, timeout=90)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ تم التحديث بنجاح! | DQ: {data['dq_score']*100:.1f}% | الفجوة المالية: -${data['total_gap_usd']:,.2f}")
        else:
            print(f"❌ فشل الإرسال. كود الخطأ: {response.status_code}")
    except requests.exceptions.Timeout:
        print("⏳ انتهت مهلة الاتصال. السيرفر ربما يستيقظ من النوم (حاول الانتظار دقيقة أخرى).")
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")

# ==========================================
# الحلقة الرئيسية (Main Loop) - تحاكي عمل PLC
# ==========================================
if __name__ == "__main__":
    print("🚀 بدء تشغيل جسر SCADA (محاكي الأنظمة الحية)")
    print(f"🔗 الهدف: {CLOUD_API_URL}")
    print(f"⏱️ فترة التحديث: كل {POLL_INTERVAL_SECONDS} ثانية")
    print("-" * 50)
    
    try:
        while True:
            send_to_predaiot_cloud()
            print(f"💤 انتظار {POLL_INTERVAL_SECONDS} ثانية حتى القراءة التالية...\n")
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف جسر SCADA يدوياً.")