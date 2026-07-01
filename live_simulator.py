import requests
import time
import random
from datetime import datetime

# Your PREDAIOT Render URL
PREDAIOT_API_URL = "https://predaiot-platform.onrender.com/api/v1/live/step"

def generate_synthetic_payload():
    """Generates realistic data for a 500MW plant with Battery Storage."""
    # Simulating a day/night cycle for prices and solar output
    current_hour = datetime.now().hour
    
    # Higher prices during evening peak (e.g., 6 PM - 10 PM)
    is_peak = 18 <= current_hour <= 22
    base_price = 45.0 if is_peak else 20.0
    market_price = base_price + random.uniform(-5.0, 5.0)
    
    return {
        "market_price": round(market_price, 2),
        "actual_discharge": round(random.uniform(50.0, 500.0), 2),
        "actual_charge": round(random.uniform(0.0, 100.0) if not is_peak else 0.0, 2),
        "soc": round(random.uniform(20.0, 95.0), 1), # Battery State of Charge %
        "p_max": 500.0,
        "e_max": 2000.0,
        "eta_charge": 0.95,
        "eta_discharge": 0.95,
        "deg_cost": 5.0, # Degradation cost per cycle
        "curtailment": round(random.uniform(0.0, 10.0), 2),
        "forecast_price": round(market_price + random.uniform(-2.0, 5.0), 2),
        "grid_limit": 500.0
    }

def run_simulator(interval_seconds=10):
    print(f"🚀 Starting PREDAIOT Live Simulator...")
    print(f"📡 Target: {PREDAIOT_API_URL}")
    print("-" * 40)
    
    while True:
        payload = generate_synthetic_payload()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending Payload: {payload['market_price']} OMR/MWh | SOC: {payload['soc']}%")
        
        try:
            # Send the POST request to your Render app
            response = requests.post(PREDAIOT_API_URL, json=payload, timeout=5)
            
            if response.status_code == 200:
                audit_result = response.json()
                print(f"✅ Audit Received: Gap = {audit_result.get('economic_gap', 0)} | Action = {audit_result.get('recommended_action', 'N/A')}")
            else:
                print(f"⚠️ Error {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection Error: Is the Render server awake? ({e})")
            
        print("-" * 40)
        time.sleep(interval_seconds) # Wait before sending the next interval

if __name__ == "__main__":
    # Test by sending 1 message every 10 seconds
    run_simulator(interval_seconds=10)