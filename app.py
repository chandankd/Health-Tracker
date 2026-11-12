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
.date-nav { display: flex; justify-content: space-between; align-items: center; background: white; padding: 10px 20px; border-radius: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin-bottom: 15px; }
.summary-pill { background: white; border-radius: 16px; padding: 16px 18px; box-shadow: 0 2px 6px rgba(0,0,0,0.03); margin-bottom: 10px; }
.pill-title { font-size: 16px; font-weight: 600; color: #2C352C; }
.pill-val { font-size: 15px; font-weight: 700; color: #386624; }
.meal-card { background: white; border-radius: 20px; padding: 18px; box-shadow: 0 3px 10px rgba(0,0,0,0.04); margin-bottom: 5px; margin-top: 15px; }
.meal-title { font-size: 17px; font-weight: 700; color: #1C241C; margin-bottom: 2px; }
.meal-sub { font-size: 13px; color: #7A867A; margin-bottom: 12px; }
.ing-title { font-size: 15px; font-weight: 700; color: #1C241C; margin-top: 10px; margin-bottom: 6px; }
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip { background: #F1F6EE; padding: 4px 12px; border-radius: 10px; font-size: 12px; font-weight: 600; color: #2C352C; }
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
        for p in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]:
            if p in available: return genai.GenerativeModel(p)
        if available: return genai.GenerativeModel(available[0])
    except Exception: pass
    return genai.GenerativeModel("gemini-flash-latest")

model = init_gemini()

# ================= 3. AUTO-TARGET CALCULATOR FUNCTION =================
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

# ================= 5. DATA STORAGE & DATE SYSTEM =================
DATA_FILE = "zentrack_v2.json"

if "sel_date" not in st.session_state:
    st.session_state.sel_date = date.today()

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

# Calculate Exact Balance for Selected Date
tot_cal = sum(e["cal"] for e in day_log["entries"] if not e.get("is_exercise", False))
tot_burn = sum(abs(e["cal"]) for e in day_log["entries"] if e.get("is_exercise", False))
net_cal = max(tot_cal - tot_burn, 0)
tot_c = sum(e.get("c", 0) for e in day_log["entries"])
tot_p = sum(e.get("p", 0) for e in day_log["entries"])
tot_f = sum(e.get("f", 0) for e in day_log["entries"])

# ================= 6. TOP NAVIGATION & DASHBOARD =================
# Date Navigator (History)
c1, c2, c3 = st.columns([1, 4, 1])
if c1.button("◀ Prev"): st.session_state.sel_date -= timedelta(days=1); st.rerun()
with c2:
    new_date = st.date_input("Date", st.session_state.sel_date, label_visibility="collapsed")
    if new_date != st.session_state.sel_date: st.session_state.sel_date = new_date; st.rerun()
if c3.button("Next ▶"): st.session_state.sel_date += timedelta(days=1); st.rerun()

# Exact Energy Balance & Macros
st.markdown(
    f'<div class="summary-pill" style="display:flex; flex-direction:column; align-items:flex-start;">'
    f'<div style="font-size: 14px; color: #7A867A; font-weight: 700; margin-bottom: 8px;">ENERGY BALANCE</div>'
    f'<div class="balance-row">'
    f'<div>🍔 In: <b style="color:#2C352C;">{tot_cal}</b></div>'
    f'<div>➖</div>'
    f'<div>🏃‍♂️ Out: <b style="color:#558B2F;">{tot_burn}</b></div>'
    f'<div>🟰</div>'
    f'<div>⚖️ Net: <b style="color:#1E88E5;">{net_cal}</b> / {prof["target_cals"]}</div>'
    f'</div></div>'
    f'<div class="summary-pill"><span class="pill-title">📊 Macros (Net)</span><span class="pill-val">'
    f'<span style="color:#1E88E5;">C {tot_c}/{prof["target_c"]}g</span> &nbsp;'
    f'<span style="color:#8E24AA;">P {tot_p}/{prof["target_p"]}g</span> &nbsp;'
    f'<span style="color:#FB8C00;">F {tot_f}/{prof["target_f"]}g</span> ⌄</span></div>',
    unsafe_allow_html=True
)

# ================= 7. MAIN TABS =================
tab_feed, tab_add, tab_water, tab_prof = st.tabs(["📋 Activity Feed", "➕ Add Log", "💧 Water", "⚙️ Goals"])

# ----------------- TAB 1: EDITABLE FEED -----------------
with tab_feed:
    if not day_log["entries"]:
        st.info("No logs for this date. Tap '➕ Add Log' to track food or exercise.")
    else:
        for idx, entry in enumerate(reversed(day_log["entries"])):
            real_idx = len(day_log["entries"]) - 1 - idx
            
            # Display Card
            if entry.get("is_exercise", False):
                st.markdown(f'<div class="meal-card"><div class="meal-title">🏃‍♂️ {entry["title"]}</div>'
                            f'<div class="meal-sub">Activity / Workout</div>'
                            f'<div style="font-size:20px; font-weight:800; color:#558B2F;">🔥 {abs(entry["cal"])} Calories Burned</div>'
                            f'<div class="time-stamp">{entry.get("time", "")}</div></div>', unsafe_allow_html=True)
            else:
                c_pct = int((entry["cal"] / max(prof["target_cals"], 1)) * 100)
                st.markdown(f'<div class="meal-card"><div class="meal-title">{entry["title"]}</div>'
                            f'<div class="meal-sub">{entry.get("subtitle", "Meal Log")}</div>'
                            f'<div class="macro-grid">'
                            f'<div><div class="m-label">CALORIES</div><div class="m-cal">{entry["cal"]}</div><div class="m-pct">{c_pct}%</div></div>'
                            f'<div><div class="m-label">CARBS</div><div class="m-carb">{entry.get("c",0)}g</div></div>'
                            f'<div><div class="m-label">PROTEIN</div><div class="m-pro">{entry.get("p",0)}g</div></div>'
                            f'<div><div class="m-label">FAT</div><div class="m-fat">{entry.get("f",0)}g</div></div>'
                            f'</div><div class="time-stamp">{entry.get("time", "")}</div></div>', unsafe_allow_html=True)
            
            # Edit / Delete Menu for each item
            with st.expander(f"⚙️ Edit / Delete '{entry['title'][:15]}...'"):
                with st.form(key=f"edit_form_{SEL_DATE_STR}_{real_idx}"):
                    e_title = st.text_input("Name", entry["title"])
                    e_cal = st.number_input("Calories (Use negative for exercise)", value=entry["cal"])
                    e_c = st.number_input("Carbs (g)", value=entry.get("c", 0))
                    e_p = st.number_input("Protein (g)", value=entry.get("p", 0))
                    e_f = st.number_input("Fat (g)", value=entry.get("f", 0))
                    
                    col_save, col_del = st.columns(2)
                    if col_save.form_submit_button("✅ Save Changes"):
                        day_log["entries"][real_idx].update({"title": e_title, "cal": e_cal, "c": e_c, "p": e_p, "f": e_f})
                        save_data(data); st.rerun()
                    if col_del.form_submit_button("🗑️ Delete Item"):
                        day_log["entries"].pop(real_idx)
                        save_data(data); st.rerun()

# ----------------- TAB 2: ADD LOG -----------------
with tab_add:
    sub1, sub2, sub3 = st.tabs(["🔍 Database", "✨ AI Text", "📷 Photo"])

    with sub1:
        selected_food = st.selectbox("Search Food or Exercise", options=[""] + list(FOOD_DB.keys()))
        qty = st.slider("Portions / Multiplier", 0.5, 5.0, 1.0, 0.5)
        if selected_food:
            item_data = FOOD_DB[selected_food]
            is_ex = item_data.get("is_exercise", False)
            s_cal = int(item_data["cal"] * qty)
            st.info(f"**Selected:** {selected_food} (x{qty}) → **{abs(s_cal)} kcal**")
            
            if st.button("✅ Add to Log", key="db_add"):
                day_log["entries"].append({
                    "title": f"{selected_food} (x{qty})" if qty != 1.0 else selected_food,
                    "subtitle": "Database Log",
                    "cal": s_cal, "c": int(item_data["c"] * qty), "p": int(item_data["p"] * qty), "f": int(item_data["f"] * qty),
                    "is_exercise": is_ex, "time": datetime.now().strftime("%I:%M %p")
                })
                save_data(data); st.success("Added!"); st.rerun()

    with sub2:
        user_query = st.text_input("Type meal or workout (Hindi/Eng/Odia):")
        if st.button("✨ Analyze with AI") and user_query:
            with st.spinner("Calculating..."):
                prompt = f"""Analyze: "{user_query}". Return ONLY raw JSON:
                {{"title": "Name", "subtitle": "AI Text", "cal": 250, "c": 30, "p": 12, "f": 8, "is_exercise": false}}
                If exercise/workout (steps, jogging), set "is_exercise": true, "c":0, "p":0, "f":0, and "cal" as NEGATIVE integer (-200)."""
                try:
                    resp = model.generate_content(prompt)
                    st.session_state["ai_draft"] = json.loads(resp.text.replace("```json", "").replace("```", "").strip())
                except: st.error("AI Error. Try again.")

        if "ai_draft" in st.session_state:
            d = st.session_state["ai_draft"]
            st.success(f"**{d['title']}** → {abs(d['cal'])} kcal")
            if st.button("💾 Save AI Entry"):
                d["time"] = datetime.now().strftime("%I:%M %p")
                day_log["entries"].append(d); save_data(data); del st.session_state["ai_draft"]; st.rerun()

    with sub3:
        enable_cam = st.toggle("🔓 Switch ON Camera")
        img_file = st.camera_input("Snap plate") if enable_cam else st.file_uploader("Upload photo", type=["jpg", "png"])
        if img_file and st.button("🔍 Scan Photo"):
            with st.spinner("Scanning..."):
                prompt = """Analyze photo. Return ONLY raw JSON:
                {"title": "Name", "subtitle": "AI Photo Scan", "cal": 350, "c": 45, "p": 15, "f": 10, "is_exercise": false}"""
                try:
                    resp = model.generate_content([prompt, Image.open(img_file)])
                    st.session_state["photo_draft"] = json.loads(resp.text.replace("```json", "").replace("```", "").strip())
                except: st.error("Photo scan failed.")

        if "photo_draft" in st.session_state:
            pd = st.session_state["photo_draft"]
            st.success(f"Detected: **{pd['title']}** ({pd['cal']} kcal)")
            if st.button("💾 Save Photo"):
                pd["time"] = datetime.now().strftime("%I:%M %p")
                day_log["entries"].append(pd); save_data(data); del st.session_state["photo_draft"]; st.rerun()

# ----------------- TAB 3: WATER -----------------
with tab_water:
    st.markdown('<div class="meal-card">', unsafe_allow_html=True)
    st.subheader(f"💧 Hydration: {day_log['water_ml']} / {prof['water_goal']} ml")
    st.progress(min(day_log["water_ml"] / max(prof["water_goal"], 1), 1.0))
    w1, w2, w3 = st.columns(3)
    if w1.button("+ 250ml"): day_log["water_ml"] += 250; save_data(data); st.rerun()
    if w2.button("+ 500ml"): day_log["water_ml"] += 500; save_data(data); st.rerun()
    if w3.button("Reset"): day_log["water_ml"] = 0; save_data(data); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 4: GOALS -----------------
with tab_prof:
    st.markdown('<div class="meal-card">', unsafe_allow_html=True)
    st.subheader("⚖️ Body Details & Goals")
    col_a, col_g = st.columns(2)
    age = col_a.number_input("Age", 15, 90, int(prof.get("age", 29)))
    gender = col_g.selectbox("Gender", ["Male", "Female"], index=0 if prof.get("gender", "Male") == "Male" else 1)
    
    col_h, col_cw, col_tw = st.columns(3)
    h = col_h.number_input("Height (cm)", 120.0, 230.0, float(prof.get("height_cm", 170.0)))
    cw = col_cw.number_input("Weight (kg)", 30.0, 200.0, float(prof.get("weight_kg", 72.0)))
    tw = col_tw.number_input("Target (kg)", 30.0, 200.0, float(prof.get("target_weight_kg", 66.0)))
    
    act_opts = ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"]
    act_idx = next((i for i, v in enumerate(act_opts) if v in prof.get("activity_level", "Lightly Active")), 1)
    act_level = st.selectbox("Activity Level", act_opts, index=act_idx)

    auto_plan = calculate_smart_targets(age, gender, h, cw, tw, act_level)
    st.info(f"**Recommended Plan:** 🔥 {auto_plan['target_cals']} kcal | P: {auto_plan['target_p']}g | C: {auto_plan['target_c']}g | F: {auto_plan['target_f']}g")

    if st.button("✨ Auto-Set & Save Targets"):
        prof.update({"age": age, "gender": gender, "height_cm": h, "weight_kg": cw, "target_weight_kg": tw, "activity_level": act_level, **auto_plan})
        save_data(data); st.success("Targets updated!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
