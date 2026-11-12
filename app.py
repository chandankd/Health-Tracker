import streamlit as st
import google.generativeai as genai
import json
import os
from datetime import date, datetime, timedelta
from PIL import Image

# ================= 1. PAGE CONFIG & CSS =================
st.set_page_config(page_title="ZenCalorie AI", page_icon="🍏", layout="centered")

st.markdown("""
<style>
.stApp { background-color: #EDF3EA; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.date-nav { display: flex; justify-content: space-between; align-items: center; background: white; padding: 10px 20px; border-radius: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin-bottom: 15px; }
.summary-pill { background: white; border-radius: 16px; padding: 16px 18px; box-shadow: 0 2px 6px rgba(0,0,0,0.03); margin-bottom: 10px; }
.pill-title { font-size: 16px; font-weight: 600; color: #2C352C; }
.pill-val { font-size: 15px; font-weight: 700; color: #386624; }
.meal-card { background: white; border-radius: 20px; padding: 18px; box-shadow: 0 3px 10px rgba(0,0,0,0.04); margin-bottom: 5px; margin-top: 15px; }
.meal-title { font-size: 17px; font-weight: 700; color: #1C241C; margin-bottom: 2px; }
.meal-sub { font-size: 13px; color: #7A867A; margin-bottom: 12px; }
.macro-grid { display: flex; justify-content: space-around; text-align: center; border-top: 1px solid #F0F3EF; padding-top: 12px; margin-top: 8px; }
.m-label { font-size: 10px; color: #7A867A; font-weight: 700; letter-spacing: 0.5px; }
.m-cal { font-size: 18px; font-weight: 800; color: #558B2F; }
.m-carb { font-size: 18px; font-weight: 800; color: #1E88E5; }
.m-pro { font-size: 18px; font-weight: 800; color: #8E24AA; }
.m-fat { font-size: 18px; font-weight: 800; color: #FB8C00; }
.m-pct { font-size: 11px; color: #7A867A; margin-top: 2px; }
.time-stamp { font-size: 12px; color: #7A867A; margin-top: 10px; }
.balance-row { display: flex; justify-content: space-between; width: 100%; margin-top: 8px; font-size: 16px; }
</style>
""", unsafe_allow_html=True)

# ================= 2. GEMINI MODEL LOADER =================
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return None
    genai.configure(api_key=api_key)
    try:
        available = [m.name.replace("models/", "") for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for p in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            if p in available: return genai.GenerativeModel(p)
        if available: return genai.GenerativeModel(available[0])
    except Exception: pass
    return genai.GenerativeModel("gemini-1.5-flash")

model = init_gemini()

# ================= 3. AUTO-TARGET CALCULATOR =================
def calculate_smart_targets(age, gender, height_cm, current_kg, target_kg, activity_level):
    if gender == "Male": bmr = (10 * current_kg) + (6.25 * height_cm) - (5 * age) + 5
    else: bmr = (10 * current_kg) + (6.25 * height_cm) - (5 * age) - 161

    mults = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    act_key = next((k for k in mults if k in activity_level), "Lightly Active")
    tdee = bmr * mults[act_key]

    diff = target_kg - current_kg
    if diff < -0.5:
        target_cals = int(max(tdee - 450, 1300))
        protein_g = int(current_kg * 1.8)
    elif diff > 0.5:
        target_cals = int(tdee + 350)
        protein_g = int(current_kg * 1.7)
    else:
        target_cals = int(tdee)
        protein_g = int(current_kg * 1.5)

    fat_g = int((target_cals * 0.25) / 9)
    carbs_g = int(max(target_cals - (protein_g * 4) - (fat_g * 9), 200) / 4)
    water_ml = round(int((current_kg * 35) + (300 if "Active" in activity_level else 0)) / 100) * 100

    return {"target_cals": target_cals, "target_p": protein_g, "target_c": carbs_g, "target_f": fat_g, "water_goal": water_ml}

# ================= 4. BUILT-IN DATABASE =================
FOOD_DB = {
    "Chia Seeds with Lemon Water (250ml)": {"cal": 78, "c": 7, "p": 3, "f": 5},
    "Steamed White Rice (1 Bowl / 150g)": {"cal": 195, "c": 42, "p": 4, "f": 0},
    "Odia Dalma (1 Bowl / 200g)": {"cal": 185, "c": 24, "p": 9, "f": 6},
    "Pakhala Bhata (1 Bowl / 300g)": {"cal": 210, "c": 45, "p": 4, "f": 1},
    "Odia Saga Bhaja (1 Katori / 100g)": {"cal": 85, "c": 8, "p": 3, "f": 5},
    "Chhena Poda (1 Piece / 60g)": {"cal": 190, "c": 22, "p": 7, "f": 8},
    "Boiled Eggs (2 Whole Eggs)": {"cal": 155, "c": 1, "p": 13, "f": 11},
    "Oats Porridge with Milk (1 Bowl / 250g)": {"cal": 225, "c": 34, "p": 9, "f": 6},
    "Soya Chunks Curry (1 Bowl / 50g raw)": {"cal": 215, "c": 17, "p": 26, "f": 4},
    "Plain Curd / Dahi (1 Katori / 100g)": {"cal": 60, "c": 4, "p": 3, "f": 3},
    "Toor Dal Tadka (1 Bowl / 150g)": {"cal": 165, "c": 20, "p": 8, "f": 6},
    "Roti / Chapati (2 Pieces)": {"cal": 170, "c": 34, "p": 6, "f": 1},
    "Idli with Sambar (2 Pieces)": {"cal": 190, "c": 36, "p": 6, "f": 2},
    "Home Style Chicken Curry (200g)": {"cal": 280, "c": 6, "p": 28, "f": 16},
    "Grape Juice (1 Glass / 250ml)": {"cal": 150, "c": 37, "p": 1, "f": 0},
    "Morning Walk / Steps (30 mins)": {"cal": -120, "c": 0, "p": 0, "f": 0, "is_exercise": True},
    "Morning Jogging / Running (20 mins)": {"cal": -210, "c": 0, "p": 0, "f": 0, "is_exercise": True}
}

# ================= 5. DATA STORAGE =================
DATA_FILE = "zentrack_v2.json"

if "sel_date" not in st.session_state: st.session_state.sel_date = date.today()

def load_data():
    default_prof = {"age": 29, "gender": "Male", "height_cm": 170.0, "weight_kg": 72.0, "target_weight_kg": 66.0, "activity_level": "Lightly Active (Morning walk/jog 1-3 km)", "target_cals": 1820, "target_c": 205, "target_p": 130, "target_f": 50, "water_goal": 2800}
    default = {"profile": default_prof, "days": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: data = json.load(f)
        except Exception: data = default
    else: data = default

    for k, v in default_prof.items():
        if k not in data.get("profile", {}): data.setdefault("profile", {})[k] = v
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

data = load_data()
prof = data["profile"]
SEL_DATE_STR = str(st.session_state.sel_date)

if SEL_DATE_STR not in data.get("days", {}):
    data.setdefault("days", {})[SEL_DATE_STR] = {"water_ml": 0, "entries": []}
day_log = data["days"][SEL_DATE_STR]

tot_cal = sum(e["cal"] for e in day_log["entries"] if not e.get("is_exercise", False))
tot_burn = sum(abs(e["cal"]) for e in day_log["entries"] if e.get("is_exercise", False))
net_cal = max(tot_cal - tot_burn, 0)
tot_c = sum(e.get("c", 0) for e in day_log["entries"])
tot_p = sum(e.get("p", 
