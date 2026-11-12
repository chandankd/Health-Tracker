import streamlit as st
import google.generativeai as genai
import json
import os
from datetime import date
from PIL import Image

# 1. Page Configuration & Custom CSS (Green/White Zencalorie Theme)
st.set_page_config(page_title="ZenTrack AI", page_icon="🍏", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #F4F7F4; }
    .card {
        background-color: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
        border-left: 5px solid #4CAF50;
    }
    .macro-text { font-size: 14px; color: #555; margin-bottom: 2px; }
    .macro-val { font-size: 18px; font-weight: bold; color: #333; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; justify-content: center; }
    </style>
""", unsafe_allow_html=True)

# 2. Configure Gemini API
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except KeyError:
    st.error("⚠️ Gemini API Key missing! Add GEMINI_API_KEY to Streamlit Secrets.")

# 3. Data Storage (Including Profile for BMI & Targets)
DATA_FILE = "zentrack_data.json"
TODAY = str(date.today())

def load_data():
    default_data = {
        "profile": {"height_cm": 170.0, "weight_kg": 70.0, "target_cals": 2200, "target_p": 120, "target_c": 250, "target_f": 60}
    }
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            if "profile" not in data:
                data["profile"] = default_data["profile"]
            if TODAY not in data:
                data[TODAY] = {"calories_in": 0, "calories_burned": 0, "protein": 0, "carbs": 0, "fat": 0, "meals": [], "activity": []}
            return data
    default_data[TODAY] = {"calories_in": 0, "calories_burned": 0, "protein": 0, "carbs": 0, "fat": 0, "meals": [], "activity": []}
    return default_data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()
day = data[TODAY]
profile = data["profile"]
net_calories = day["calories_in"] - day["calories_burned"]

# 4. App Navigation Tabs
nav1, nav2, nav3, nav4 = st.tabs(["📊 Dashboard", "📸 Log Meal", "🏃‍♂️ Activity", "⚙️ Profile"])

# ================= DASHBOARD TAB =================
with nav1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader(f"Today: {date.today().strftime('%d %b %Y')}")
    st.write(f"**Eaten:** {day['calories_in']} | **Burned:** {day['calories_burned']} | **Net:** {net_calories} / {profile['target_cals']} kcal")
    st.progress(min(max(net_calories / profile['target_cals'], 0.0), 1.0))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<p class="macro-text">Protein</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="macro-val">{day["protein"]}g / {profile["target_p"]}g</p>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="macro-text">Carbs</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="macro-val">{day["carbs"]}g / {profile["target_c"]}g</p>', unsafe_allow_html=True)
    with col3:
        st.markdown('<p class="macro-text">Fat</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="macro-val">{day["fat"]}g / {profile["target_f"]}g</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🍽️ Meals Logged")
    if not day['meals']:
        st.write("No meals logged today yet.")
    for meal in day['meals']:
        st.write(meal)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= LOG MEAL TAB =================
with nav2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    log1, log2, log3 = st.tabs(["Just Type", "AI Photo", "Manual"])
    
    with log1:
        st.info("💡 Type in Hindi, English, or Odia (e.g., '1 katori dalma aur 1 cup rice')")
        food_text = st.text_input("What did you eat?")
        if st.button("Calculate Text Macros"):
            if food_text:
                with st.spinner("Calculating..."):
                    prompt = f"User said: '{food_text}'. Understand Hindi/Odia/Indian food. Estimate calories and macros. Return ONLY valid JSON with keys: 'food_name', 'calories', 'protein', 'carbs', 'fat' as integers. No markdown."
                    res_text = model.generate_content(prompt)
                    try:
                        res = json.loads(res_text.text.replace('```json', '').replace('```', '').strip())
                        st.success(f"Estimated: {res['food_name']} ({res['calories']} kcal)")
                        if st.button("Save this meal"):
                            day['calories_in'] += int(res['calories']); day['protein'] += int(res['protein']); day['carbs'] += int(res['carbs']); day['fat'] += int(res['fat'])
                            day['meals'].append(f"✍️ {res['food_name']} ({res['calories']} kcal)")
                            save_data(data); st.rerun()
                    except:
                        st.error("Error calculating. Please try again.")

    with log2:
        st.warning("🔒 Camera is off to save battery.")
        # FIX: The camera only turns on when this switch is turned ON.
        camera_on = st.toggle("📷 Switch on Camera to snap meal")
        if camera_on:
            photo = st.camera_input("Take a picture of your food")
            if photo:
                with st.spinner("Analyzing AI-Powered Photo..."):
                    prompt = "Analyze this food image. Identify Indian/Odia dishes if present. Return ONLY valid JSON with keys: 'food_name', 'calories', 'protein', 'carbs', 'fat' as integers. No markdown."
                    res_text = model.generate_content([prompt, Image.open(photo)])
                    try:
                        res = json.loads(res_text.text.replace('```json', '').replace('```', '').strip())
                        st.success(f"Detected: {res['food_name']} ({res['calories']} kcal)")
                        if st.button("Save Photo Meal"):
                            day['calories_in'] += int(res['calories']); day['protein'] += int(res['protein']); day['carbs'] += int(res['carbs']); day['fat'] += int(res['fat'])
                            day['meals'].append(f"📸 {res['food_name']} ({res['calories']} kcal)")
                            save_data(data); st.rerun()
                    except:
                        st.error("Could not scan clearly.")

    with log3:
        m_name = st.text_input("Food Name")
        col_c, col_p, col_cb, col_f = st.columns(4)
        m_cal = col_c.number_input("Kcal", min_value=0, step=10)
        m_pro = col_p.number_input("Protein", min_value=0, step=1)
        m_car = col_cb.number_input("Carbs", min_value=0, step=1)
        m_fat = col_f.number_input("Fat", min_value=0, step=1)
        if st.button("Save Manual"):
            day['calories_in'] += m_cal; day['protein'] += m_pro; day['carbs'] += m_car; day['fat'] += m_fat
            day['meals'].append(f"🔢 {m_name} ({m_cal} kcal)")
            save_data(data); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ================= ACTIVITY TAB =================
with nav3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏃‍♂️ Log Daily Exercise")
    act_text = st.text_input("Type your workout (e.g., '30 min jogging')")
    if st.button("Calculate Burned Calories"):
        if act_text:
            with st.spinner("Calculating..."):
                act_prompt = f"User did: '{act_text}'. Estimate calories burned. Return ONLY valid JSON with keys: 'activity_name', 'calories_burned' (integer). No markdown."
                act_res_text = model.generate_content(act_prompt)
                try:
                    act_res = json.loads(act_res_text.text.replace('```json', '').replace('```', '').strip())
                    st.success(f"Burned {act_res['calories_burned']} kcal from {act_res['activity_name']}")
                    if st.button("Save Workout"):
                        day['calories_burned'] += int(act_res['calories_burned'])
                        day['activity'].append(f"🏃 {act_res['activity_name']} (-{act_res['calories_burned']} kcal)")
                        save_data(data); st.rerun()
                except:
                    st.error("Error reading workout data.")
    
    if day['activity']:
        st.write("---")
        for act in day['activity']:
            st.write(act)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= PROFILE & BMI TAB =================
with nav4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚖️ BMI Calculator")
    h_cm = st.number_input("Height (cm)", min_value=50.0, max_value=250.0, value=float(profile.get("height_cm", 170.0)))
    w_kg = st.number_input("Weight (kg)", min_value=20.0, max_value=200.0, value=float(profile.get("weight_kg", 70.0)))
    
    bmi = w_kg / ((h_cm / 100) ** 2)
    st.write(f"**Your BMI is: {bmi:.1f}**")
    
    if bmi < 18.5: st.info("Status: Underweight")
    elif 18.5 <= bmi < 24.9: st.success("Status: Normal weight")
    elif 25 <= bmi < 29.9: st.warning("Status: Overweight")
    else: st.error("Status: Obese")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🎯 Set Your Daily Targets")
    t_cal = st.number_input("Target Calories", value=profile.get("target_cals", 2200), step=100)
    t_p = st.number_input("Target Protein (g)", value=profile.get("target_p", 120), step=5)
    t_c = st.number_input("Target Carbs (g)", value=profile.get("target_c", 250), step=5)
    t_f = st.number_input("Target Fat (g)", value=profile.get("target_f", 60), step=5)
    
    if st.button("Save Profile & Targets"):
        profile["height_cm"] = h_cm
        profile["weight_kg"] = w_kg
        profile["target_cals"] = t_cal
        profile["target_p"] = t_p
        profile["target_c"] = t_c
        profile["target_f"] = t_f
        save_data(data)
        st.success("Profile saved successfully!")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
