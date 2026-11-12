import streamlit as st
import google.generativeai as genai
import json
import os
from datetime import date, datetime, timedelta
from PIL import Image

# ================= 1. PAGE CONFIG & ZENCALORIE EXACT CSS =================
st.set_page_config(page_title="ZenCalorie AI", page_icon="🍏", layout="centered")

st.markdown("""
<style>
.stApp { background-color: #EDF3EA; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.cal-strip {
    background: white; border-radius: 20px; padding: 14px 10px;
    display: flex; justify-content: space-around; align-items: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin-bottom: 14px; text-align: center;
}
.cal-day { font-size: 13px; color: #7A867A; font-weight: 600; }
.cal-num { font-size: 15px; color: #2C352C; font-weight: 600; margin-top: 6px; padding: 6px 10px; border-radius: 50%; }
.cal-active { background-color: #558B2F; color: white !important; }
.summary-pill {
    background: white; border-radius: 16px; padding: 14px 18px;
    display: flex; justify-content: space-between; align-items: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03); margin-bottom: 10px;
}
.pill-title { font-size: 16px; font-weight: 600; color: #2C352C; }
.pill-val { font-size: 15px; font-weight: 700; color: #386624; }
.meal-card {
    background: white; border-radius: 20px; padding: 18px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.04); margin-bottom: 16px;
}
.meal-title { font-size: 17px; font-weight: 700; color: #1C241C; margin-bottom: 2px; }
.meal-sub { font-size: 13px; color: #7A867A; margin-bottom: 12px; }
.ing-title { font-size: 15px; font-weight: 700; color: #1C241C; margin-top: 10px; margin-bottom: 6px; }
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip { background: #F1F6EE; padding: 4px 12px; border-radius: 10px; font-size: 12px; font-weight: 600; color: #2C352C; }
.macro-grid {
    display: flex; justify-content: space-around; text-align: center;
    border-top: 1px solid #F0F3EF; padding-top: 12px; margin-top: 8px;
}
.m-label { font-size: 10px; color: #7A867A; font-weight: 700; letter-spacing: 0.5px; }
.m-cal { font-size: 18px; font-weight: 800; color: #558B2F; }
.m-carb { font-size: 18px; font-weight: 800; color: #1E88E5; }
.m-pro { font-size: 18px; font-weight: 800; color: #8E24AA; }
.m-fat { font-size: 18px; font-weight: 800; color: #FB8C00; }
.m-pct { font-size: 11px; color: #7A867A; margin-top: 2px; }
.time-stamp { font-size: 12px; color: #7A867A; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= 2. GEMINI MODEL LOADER =================
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    preferred = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
    try:
        available = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        for p in preferred:
            if p in available:
                return genai.GenerativeModel(p)
        if available:
            return genai.GenerativeModel(available[0])
    except Exception:
        pass
    return genai.GenerativeModel("gemini-flash-latest")

model = init_gemini()

# ================= 3. AUTO-TARGET CALCULATOR FUNCTION =================
def calculate_smart_targets(age, gender, height_cm, current_kg, target_kg, activity_level):
    # Mifflin-St Jeor BMR Formula
    if gender == "Male":
        bmr = (10 * current_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * current_kg) + (6.25 * height_cm) - (5 * age) - 161

    multipliers = {
        "Sedentary (Desk job, little exercise)": 1.2,
        "Lightly Active (Morning walk/jog 1-3 km)": 1.375,
        "Moderately Active (Daily run/workout 3-5 days/wk)": 1.55,
        "Very Active (Hard training 6-7 days/wk)": 1.725
    }
    tdee = bmr * multipliers.get(activity_level, 1.375)

    # Adjust calories for Weight Loss, Maintenance, or Muscle Gain
    diff = target_kg - current_kg
    if diff < -0.5:
        target_cals = int(max(tdee - 450, 1300))  # Safe fat-loss deficit
        protein_g = int(current_kg * 1.8)         # High protein to protect muscle
    elif diff > 0.5:
        target_cals = int(tdee + 350)             # Lean bulk surplus
        protein_g = int(current_kg * 1.7)
    else:
        target_cals = int(tdee)                   # Maintenance
        protein_g = int(current_kg * 1.5)

    fat_g = int((target_cals * 0.25) / 9)
    rem_cals = max(target_cals - (protein_g * 4) - (fat_g * 9), 200)
    carbs_g = int(rem_cals / 4)

    # Water intake: 35ml per kg of body weight + 300ml for active lifestyle
    water_ml = int((current_kg * 35) + (300 if "Active" in activity_level else 0))
    water_ml = round(water_ml / 100) * 100

    return {
        "target_cals": target_cals,
        "target_p": protein_g,
        "target_c": carbs_g,
        "target_f": fat_g,
        "water_goal": water_ml
    }

# ================= 4. BUILT-IN INDIAN / ODIA / SOUTH INDIAN FOOD DATABASE =================
FOOD_DB = {
    "Chia Seeds with Lemon Water (250ml)": {"cal": 78, "c": 7, "p": 3, "f": 5, "items": [{"n": "Chia seeds (15g)", "cal": 73, "c": 6, "p": 3, "f": 5}, {"n": "Lemon water (250ml)", "cal": 5, "c": 1, "p": 0, "f": 0}]},
    "Steamed White Rice (1 Bowl / 150g)": {"cal": 195, "c": 42, "p": 4, "f": 0, "items": [{"n": "Boiled Rice (150g)", "cal": 195, "c": 42, "p": 4, "f": 0}]},
    "Odia Dalma (1 Bowl / 200g)": {"cal": 185, "c": 24, "p": 9, "f": 6, "items": [{"n": "Toor Dal & Mixed Veggies (200g)", "cal": 150, "c": 24, "p": 9, "f": 2}, {"n": "Mustard Oil & Tadka (4g)", "cal": 35, "c": 0, "p": 0, "f": 4}]},
    "Pakhala Bhata (1 Bowl / 300g)": {"cal": 210, "c": 45, "p": 4, "f": 1, "items": [{"n": "Fermented Rice & Water (280g)", "cal": 195, "c": 44, "p": 4, "f": 0}, {"n": "Curd & Seasoning (20g)", "cal": 15, "c": 1, "p": 0, "f": 1}]},
    "Odia Saga Bhaja (1 Katori / 100g)": {"cal": 85, "c": 8, "p": 3, "f": 5, "items": [{"n": "Leafy Greens & Garlic (100g)", "cal": 85, "c": 8, "p": 3, "f": 5}]},
    "Chhena Poda (1 Piece / 60g)": {"cal": 190, "c": 22, "p": 7, "f": 8, "items": [{"n": "Baked Cottage Cheese & Sugar (60g)", "cal": 190, "c": 22, "p": 7, "f": 8}]},
    "Boiled Eggs (2 Whole Eggs)": {"cal": 155, "c": 1, "p": 13, "f": 11, "items": [{"n": "Boiled Eggs (100g)", "cal": 155, "c": 1, "p": 13, "f": 11}]},
    "Oats Porridge with Milk (1 Bowl / 250g)": {"cal": 225, "c": 34, "p": 9, "f": 6, "items": [{"n": "Rolled Oats (40g)", "cal": 150, "c": 27, "p": 5, "f": 3}, {"n": "Milk (120ml)", "cal": 75, "c": 7, "p": 4, "f": 3}]},
    "Soya Chunks Curry / Dry (1 Bowl / 50g raw)": {"cal": 215, "c": 17, "p": 26, "f": 4, "items": [{"n": "Soya Chunks (50g dry weight)", "cal": 172, "c": 16, "p": 26, "f": 1}, {"n": "Spices & Oil", "cal": 43, "c": 1, "p": 0, "f": 3}]},
    "Plain Curd / Dahi (1 Katori / 100g)": {"cal": 60, "c": 4, "p": 3, "f": 3, "items": [{"n": "Fresh Curd (100g)", "cal": 60, "c": 4, "p": 3, "f": 3}]},
    "Toor Dal / Yellow Dal Tadka (1 Bowl / 150g)": {"cal": 165, "c": 20, "p": 8, "f": 6, "items": [{"n": "Cooked Yellow Dal (150g)", "cal": 165, "c": 20, "p": 8, "f": 6}]},
    "Roti / Chapati (2 Pieces)": {"cal": 170, "c": 34, "p": 6, "f": 1, "items": [{"n": "Whole Wheat Roti (2 pcs)", "cal": 170, "c": 34, "p": 6, "f": 1}]},
    "South Indian Idli (2 Pieces with Sambar)": {"cal": 190, "c": 36, "p": 6, "f": 2, "items": [{"n": "Steamed Idli (2 pcs)", "cal": 130, "c": 28, "p": 4, "f": 0}, {"n": "Sambar (100ml)", "cal": 60, "c": 8, "p": 2, "f": 2}]},
    "Masala Dosa (1 Medium with Chutney)": {"cal": 320, "c": 45, "p": 7, "f": 12, "items": [{"n": "Dosa with Potato Masala (150g)", "cal": 260, "c": 42, "p": 5, "f": 8}, {"n": "Coconut Chutney (30g)", "cal": 60, "c": 3, "p": 2, "f": 4}]},
    "Upma (1 Bowl / 150g)": {"cal": 195, "c": 32, "p": 5, "f": 5, "items": [{"n": "Rava Upma with Veggies (150g)", "cal": 195, "c": 32, "p": 5, "f": 5}]},
    "Home Style Chicken Curry (1 Bowl / 200g)": {"cal": 280, "c": 6, "p": 28, "f": 16, "items": [{"n": "Chicken Pieces (120g)", "cal": 190, "c": 0, "p": 27, "f": 9}, {"n": "Onion Tomato Gravy (80g)", "cal": 90, "c": 6, "p": 1, "f": 7}]},
    "Fish Besara / Mustard Fish Curry (1 Bowl)": {"cal": 240, "c": 4, "p": 22, "f": 15, "items": [{"n": "Rohu Fish & Mustard Gravy (150g)", "cal": 240, "c": 4, "p": 22, "f": 15}]},
    "Grape Juice (1 Glass / 250ml)": {"cal": 150, "c": 37, "p": 1, "f": 0, "items": [{"n": "Grape juice (250ml)", "cal": 150, "c": 37, "p": 1, "f": 0}]},
    "Morning Walk / Jogging (1 km / 12 mins)": {"cal": -75, "c": 0, "p": 0, "f": 0, "is_exercise": True, "items": []},
    "Morning Running (3 km / 20 mins)": {"cal": -210, "c": 0, "p": 0, "f": 0, "is_exercise": True, "items": []}
}

# ================= 5. DATA STORAGE =================
DATA_FILE = "zentrack_v2.json"
TODAY = str(date.today())

def load_data():
    default_prof = {
        "age": 29,
        "gender": "Male",
        "height_cm": 170.0,
        "weight_kg": 72.0,
        "target_weight_kg": 66.0,
        "activity_level": "Lightly Active (Morning walk/jog 1-3 km)",
        "target_cals": 1820,
        "target_c": 205,
        "target_p": 130,
        "target_f": 50,
        "water_goal": 2800
    }
    default = {"profile": default_prof, "days": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = default
    else:
        data = default

    if "profile" not in data:
        data["profile"] = default_prof
    else:
        for k, v in default_prof.items():
            if k not in data["profile"]:
                data["profile"][k] = v

    if "days" not in data:
        data["days"] = {}
    if TODAY not in data["days"]:
        data["days"][TODAY] = {"water_ml": 0, "entries": []}
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()
prof = data["profile"]
day_log = data["days"][TODAY]

# Calculate Daily Totals
tot_cal = sum(e["cal"] for e in day_log["entries"] if not e.get("is_exercise", False))
tot_burn = sum(abs(e["cal"]) for e in day_log["entries"] if e.get("is_exercise", False))
net_cal = max(tot_cal - tot_burn, 0)
tot_c = sum(e.get("c", 0) for e in day_log["entries"])
tot_p = sum(e.get("p", 0) for e in day_log["entries"])
tot_f = sum(e.get("f", 0) for e in day_log["entries"])

# ================= 6. TOP NAVIGATION & ZENCALORIE CALENDAR STRIP =================
st.markdown("<h3 style='text-align:center; color:#1C241C; margin-bottom:8px;'>Today ⌄</h3>", unsafe_allow_html=True)

today_dt = date.today()
start_week = today_dt - timedelta(days=today_dt.weekday())
days_letters = ["M", "T", "W", "T", "F", "S", "S"]
cal_html = '<div class="cal-strip">'
for i in range(7):
    d = start_week + timedelta(days=i)
    active_cls = "cal-num cal-active" if d == today_dt else "cal-num"
    cal_html += f'<div><div class="cal-day">{days_letters[i]}</div><div class="{active_cls}">{d.day}</div></div>'
cal_html += '</div>'
st.markdown(cal_html, unsafe_allow_html=True)

# Summary Pills
st.markdown(
    f'<div class="summary-pill"><span class="pill-title">🔥 Calories</span><span class="pill-val">{net_cal} / {prof["target_cals"]:,} kcal ⌄</span></div>'
    f'<div class="summary-pill"><span class="pill-title">📊 Macros</span><span class="pill-val">'
    f'<span style="color:#1E88E5;">C {tot_c}/{prof["target_c"]}g</span> &nbsp;'
    f'<span style="color:#8E24AA;">P {tot_p}/{prof["target_p"]}g</span> &nbsp;'
    f'<span style="color:#FB8C00;">F {tot_f}/{prof["target_f"]}g</span> ⌄</span></div>',
    unsafe_allow_html=True
)

# ================= 7. MAIN TABS =================
tab_feed, tab_add, tab_water, tab_prof = st.tabs(["📋 Activity Feed", "➕ Log Food / Exercise", "💧 Water", "⚙️ BMI & Auto-Goals"])

# ----------------- TAB 1: ZENCALORIE FEED (NO INDENTATION BUG) -----------------
with tab_feed:
    st.markdown("<h4 style='color:#2E5A1C; margin-top:5px;'>Activity</h4>", unsafe_allow_html=True)
    if not day_log["entries"]:
        st.info("No meals or workouts logged yet today. Tap '➕ Log Food / Exercise' above to add your first entry!")
    else:
        for entry in reversed(day_log["entries"]):
            if entry.get("is_exercise", False):
                card_html = (
                    f'<div class="meal-card">'
                    f'<div class="meal-title">🏃‍♂️ {entry["title"]}</div>'
                    f'<div class="meal-sub">{entry.get("subtitle", "Daily Workout")}</div>'
                    f'<div style="font-size:20px; font-weight:800; color:#558B2F;">🔥 {abs(entry["cal"])} Calories Burned</div>'
                    f'<div class="time-stamp">{entry.get("time", "")}</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
            else:
                ing_parts = []
                for item in entry.get("items", []):
                    ing_parts.append(
                        f'<div class="ing-title">{item["n"]}</div>'
                        f'<div class="chip-row">'
                        f'<span class="chip">Calories: {item["cal"]}</span>'
                        f'<span class="chip">C: {item["c"]}g</span>'
                        f'<span class="chip">P: {item["p"]}g</span>'
                        f'<span class="chip">F: {item["f"]}g</span>'
                        f'</div>'
                    )
                ing_html = "".join(ing_parts)
                c_pct = int((entry["cal"] / max(prof["target_cals"], 1)) * 100)
                carb_pct = int((entry["c"] / max(prof["target_c"], 1)) * 100)
                pro_pct = int((entry["p"] / max(prof["target_p"], 1)) * 100)
                fat_pct = int((entry["f"] / max(prof["target_f"], 1)) * 100)

                card_html = (
                    f'<div class="meal-card">'
                    f'<div class="meal-title">{entry["title"]}</div>'
                    f'<div class="meal-sub">{entry.get("subtitle", entry["title"])}</div>'
                    f'{ing_html}'
                    f'<div class="macro-grid">'
                    f'<div><div class="m-label">CALORIES</div><div class="m-cal">{entry["cal"]}</div><div class="m-pct">{c_pct}%</div></div>'
                    f'<div><div class="m-label">CARBS</div><div class="m-carb">{entry["c"]}g</div><div class="m-pct">{carb_pct}%</div></div>'
                    f'<div><div class="m-label">PROTEIN</div><div class="m-pro">{entry["p"]}g</div><div class="m-pct">{pro_pct}%</div></div>'
                    f'<div><div class="m-label">FAT</div><div class="m-fat">{entry["f"]}g</div><div class="m-pct">{fat_pct}%</div></div>'
                    f'</div>'
                    f'<div class="time-stamp">{entry.get("time", "")}</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

        if st.button("🗑️ Clear Today's Log"):
            day_log["entries"] = []
            save_data(data)
            st.rerun()

# ----------------- TAB 2: LOG FOOD / EXERCISE -----------------
with tab_add:
    sub1, sub2, sub3 = st.tabs(["🔍 Database Search", "✨ AI Text (Hindi/Odia/Eng)", "📷 Camera / Gallery"])

    with sub1:
        st.caption("Start typing to get instant suggestions from the Indian, Odia & South Indian database:")
        selected_food = st.selectbox("Search Food or Exercise Database", options=[""] + list(FOOD_DB.keys()))
        qty = st.slider("Portion Multiplier (Servings)", 0.5, 5.0, 1.0, 0.5)

        if selected_food:
            item_data = FOOD_DB[selected_food]
            s_cal = int(item_data["cal"] * qty)
            s_c = int(item_data["c"] * qty)
            s_p = int(item_data["p"] * qty)
            s_f = int(item_data["f"] * qty)

            st.info(f"**Selected:** {selected_food} (x{qty}) → **{abs(s_cal)} kcal** | C: {s_c}g | P: {s_p}g | F: {s_f}g")
            if st.button("✅ Add to Today's Log", key="db_add"):
                scaled_items = [
                    {"n": i["n"], "cal": int(i["cal"] * qty), "c": int(i["c"] * qty), "p": int(i["p"] * qty), "f": int(i["f"] * qty)}
                    for i in item_data.get("items", [])
                ]
                day_log["entries"].append({
                    "title": f"{selected_food} (x{qty})" if qty != 1.0 else selected_food,
                    "subtitle": "Logged from Verified Indian Database",
                    "cal": s_cal, "c": s_c, "p": s_p, "f": s_f,
                    "is_exercise": item_data.get("is_exercise", False),
                    "items": scaled_items,
                    "time": datetime.now().strftime("%I:%M %p")
                })
                save_data(data)
                st.success("Added! Check your Activity Feed.")
                st.rerun()

    with sub2:
        st.caption("Type in Hindi, Odia, Hinglish, or English (e.g., '1 bowl dalma, 1 cup rice and 2 boiled eggs' or '20 min morning running')")
        user_query = st.text_input("What did you eat or exercise?")

        if st.button("✨ Analyze with AI"):
            if not model:
                st.error("⚠️ GEMINI_API_KEY missing in Streamlit Secrets!")
            elif user_query:
                with st.spinner("Calculating breakdown..."):
                    prompt = f"""
                    You are an Indian nutrition & fitness AI. Analyze: "{user_query}".
                    Understand Hindi, Odia, South Indian, and English food or exercise.
                    Return ONLY raw JSON (no markdown blocks) in this exact structure:
                    {{
                      "title": "Main Dish or Workout Title (with total weight/duration)",
                      "subtitle": "{user_query}",
                      "cal": 250,
                      "c": 30,
                      "p": 12,
                      "f": 8,
                      "is_exercise": false,
                      "items": [
                        {{"n": "Ingredient 1 (weight)", "cal": 150, "c": 20, "p": 8, "f": 5}}
                      ]
                    }}
                    If it is an exercise/workout, set "is_exercise": true, "c": 0, "p": 0, "f": 0, and "cal" to positive calories burned.
                    """
                    try:
                        resp = model.generate_content(prompt)
                        clean = resp.text.replace("```json", "").replace("```", "").strip()
                        st.session_state["ai_draft"] = json.loads(clean)
                    except Exception as e:
                        st.error(f"AI Error: {e}")

        if "ai_draft" in st.session_state:
            d = st.session_state["ai_draft"]
            st.success(f"**{d['title']}** → {d['cal']} kcal | C: {d['c']}g | P: {d['p']}g | F: {d['f']}g")
            if st.button("💾 Save AI Entry to Today's Log"):
                d["time"] = datetime.now().strftime("%I:%M %p")
                day_log["entries"].append(d)
                save_data(data)
                del st.session_state["ai_draft"]
                st.rerun()

    with sub3:
        cam_mode = st.radio("Choose Image Source", ["Upload from Gallery", "Turn On Camera"], horizontal=True)
        img_file = None
        if cam_mode == "Upload from Gallery":
            img_file = st.file_uploader("Upload food photo", type=["jpg", "jpeg", "png"])
        else:
            enable_cam = st.toggle("🔓 Switch ON Camera")
            if enable_cam:
                img_file = st.camera_input("Snap your plate")

        if img_file and st.button("🔍 Scan Food Photo"):
            with st.spinner("Scanning plate & estimating Indian portions..."):
                img = Image.open(img_file)
                prompt = """
                Analyze this food photo (recognize Indian, Odia, South Indian, or general dishes).
                Return ONLY valid JSON (no markdown) with exact keys:
                {"title": "Meal Name (total grams)", "subtitle": "AI Photo Scan", "cal": 350, "c": 45, "p": 15, "f": 10, "is_exercise": false,
                "items": [{"n": "Item 1 (g)", "cal": 200, "c": 30, "p": 5, "f": 2}]}
                """
                try:
                    resp = model.generate_content([prompt, img])
                    clean = resp.text.replace("```json", "").replace("```", "").strip()
                    st.session_state["photo_draft"] = json.loads(clean)
                except Exception as e:
                    st.error(f"Photo scan failed: {e}")

        if "photo_draft" in st.session_state:
            pd = st.session_state["photo_draft"]
            st.success(f"Detected: **{pd['title']}** ({pd['cal']} kcal)")
            if st.button("💾 Save Photo Meal"):
                pd["time"] = datetime.now().strftime("%I:%M %p")
                day_log["entries"].append(pd)
                save_data(data)
                del st.session_state["photo_draft"]
                st.rerun()

# ----------------- TAB 3: WATER TRACKER -----------------
with tab_water:
    st.markdown('<div class="meal-card">', unsafe_allow_html=True)
    st.subheader(f"💧 Hydration: {day_log['water_ml']} / {prof['water_goal']} ml")
    st.progress(min(day_log["water_ml"] / max(prof["water_goal"], 1), 1.0))
    w1, w2, w3 = st.columns(3)
    if w1.button("+ 250ml Glass"):
        day_log["water_ml"] += 250; save_data(data); st.rerun()
    if w2.button("+ 500ml Bottle"):
        day_log["water_ml"] += 500; save_data(data); st.rerun()
    if w3.button("Reset Water"):
        day_log["water_ml"] = 0; save_data(data); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 4: BMI & AUTO-CALCULATED TARGETS -----------------
with tab_prof:
    st.markdown('<div class="meal-card">', unsafe_allow_html=True)
    st.subheader("⚖️ Body Details & Automatic Goal Planner")
    st.caption("Enter your body details below—the app will automatically calculate your daily Calories, Protein, Carbs, Fat, and Water targets.")

    col_a, col_g = st.columns(2)
    age = col_a.number_input("Age (Years)", 15, 90, int(prof.get("age", 29)))
    gender = col_g.selectbox("Gender", ["Male", "Female"], index=0 if prof.get("gender", "Male") == "Male" else 1)

    col_h, col_cw, col_tw = st.columns(3)
    h = col_h.number_input("Height (cm)", 120.0, 230.0, float(prof.get("height_cm", 170.0)), step=0.5)
    cw = col_cw.number_input("Current Weight (kg)", 30.0, 200.0, float(prof.get("weight_kg", 72.0)), step=0.5)
    tw = col_tw.number_input("Target Weight (kg)", 30.0, 200.0, float(prof.get("target_weight_kg", 66.0)), step=0.5)

    act_options = [
        "Sedentary (Desk job, little exercise)",
        "Lightly Active (Morning walk/jog 1-3 km)",
        "Moderately Active (Daily run/workout 3-5 days/wk)",
        "Very Active (Hard training 6-7 days/wk)"
    ]
    saved_act = prof.get("activity_level", act_options[1])
    act_idx = act_options.index(saved_act) if saved_act in act_options else 1
    act_level = st.selectbox("Daily Activity Level", act_options, index=act_idx)

    # Calculate BMI & Smart Plan Preview Live
    bmi = cw / ((h / 100) ** 2)
    bmi_status = "Normal Weight ✅" if 18.5 <= bmi <= 24.9 else ("Overweight ⚠️" if bmi > 24.9 else "Underweight ℹ️")
    auto_plan = calculate_smart_targets(age, gender, h, cw, tw, act_level)

    weight_diff = tw - cw
    goal_label = f"Lose {abs(weight_diff):.1f} kg" if weight_diff < -0.5 else (f"Gain {weight_diff:.1f} kg" if weight_diff > 0.5 else "Maintain Weight")

    st.info(
        f"**Current BMI:** `{bmi:.1f}` ({bmi_status}) | **Goal:** `{goal_label}`\n\n"
        f"**Recommended Daily Plan:**\n"
        f"- 🔥 **Calories:** `{auto_plan['target_cals']} kcal/day`\n"
        f"- 💪 **Protein:** `{auto_plan['target_p']} g` | 🍚 **Carbs:** `{auto_plan['target_c']} g` | 🥑 **Fat:** `{auto_plan['target_f']} g`\n"
        f"- 💧 **Daily Water Goal:** `{auto_plan['water_goal']} ml` ({auto_plan['water_goal']/1000:.1f} Liters)"
    )

    if st.button("✨ Auto-Set & Save My Daily Targets"):
        prof.update({
            "age": age,
            "gender": gender,
            "height_cm": h,
            "weight_kg": cw,
            "target_weight_kg": tw,
            "activity_level": act_level,
            "target_cals": auto_plan["target_cals"],
            "target_p": auto_plan["target_p"],
            "target_c": auto_plan["target_c"],
            "target_f": auto_plan["target_f"],
            "water_goal": auto_plan["water_goal"]
        })
        save_data(data)
        st.success("Your personalized calorie, macro, and water targets have been updated!")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
