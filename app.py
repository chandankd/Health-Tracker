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
    </style>
""", unsafe_allow_html=True)

# 2. Configure Gemini API
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except KeyError:
    st.error("⚠️ Gemini API Key missing! Add GEMINI_API_KEY to Streamlit Secrets.")

# 3. Data Storage
DATA_FILE = "zentrack_data.json"
TODAY = str(date.today())

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            if TODAY in data:
                return data
    return {TODAY: {"calories_in": 0, "calories_burned": 0, "protein": 0, "carbs": 0, "fat": 0, "water_ml": 0, "meals": [], "activity": []}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()
day = data[TODAY]
TARGET_CALS = 2200

# Calculate Net Calories
net_calories = day["calories_in"] - day["calories_burned"]

# 4. UI: Dashboard & Full Day Summary
st.title("🍏 ZenTrack AI")
st.markdown(f"**Today:** {date.today().strftime('%d %b %Y')}")

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("📊 Track Your Full Day Summary")
st.write(f"**Eaten:** {day['calories_in']} kcal | **Burned:** {day['calories_burned']} kcal | **Net:** {net_calories} kcal")
st.progress(min(max(net_calories / TARGET_CALS, 0.0), 1.0))

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<p class="macro-text">Protein</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="macro-val">{day["protein"]}g</p>', unsafe_allow_html=True)
with col2:
    st.markdown('<p class="macro-text">Carbs</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="macro-val">{day["carbs"]}g</p>', unsafe_allow_html=True)
with col3:
    st.markdown('<p class="macro-text">Fat</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="macro-val">{day["fat"]}g</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# 5. UI: AI Food Scanner & Manual Entry (Hindi/Indian Food Support)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("📸 Log Meals")
tab1, tab2, tab3 = st.tabs(["Just Type", "AI Photo", "Manual Numbers"])

with tab1:
    st.info("💡 You can type in Hindi, English, or Odia (e.g., 'Maine 2 idli aur 1 katori dalma khaya' or '1 bowl oats with chia seeds')")
    food_text = st.text_input("What did you eat?")
    if st.button("Calculate Macros"):
        if food_text:
            with st.spinner("Calculating..."):
                prompt = f"""
                You are an expert Indian nutritionist. The user said: '{food_text}'.
                Understand Hindi, Hinglish, Odia, South Indian, and English food terms. 
                Estimate total calories and macros for this meal.
                Return ONLY valid JSON with keys: "food_name", "calories", "protein", "carbs", "fat". Values must be integers. Do not use markdown blocks.
                """
                response = model.generate_content(prompt)
                try:
                    res = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                    st.success(f"Estimated: {res['food_name']}")
                    st.write(f"**Calories:** {res['calories']} | **P:** {res['protein']}g | **C:** {res['carbs']}g | **F:** {res['fat']}g")
                    
                    if st.button("Save this meal"):
                        day['calories_in'] += int(res['calories'])
                        day['protein'] += int(res['protein'])
                        day['carbs'] += int(res['carbs'])
                        day['fat'] += int(res['fat'])
                        day['meals'].append(f"✍️ {res['food_name']} ({res['calories']} kcal)")
                        save_data(data); st.rerun()
                except:
                    st.error("Error reading data. Try again.")

with tab2:
    photo = st.camera_input("Snap your meal")
    if photo:
        with st.spinner("Analyzing AI-Powered Photo..."):
            prompt = "Analyze this food image. Identify Indian/Odia dishes if present. Return ONLY valid JSON with keys: 'food_name', 'calories', 'protein', 'carbs', 'fat' as integers. No markdown."
            response = model.generate_content([prompt, Image.open(photo)])
            try:
                res = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                st.success(f"Detected: {res['food_name']}")
                st.write(f"**Calories:** {res['calories']} | **P:** {res['protein']}g")
                if st.button("Save Photo Meal"):
                    day['calories_in'] += int(res['calories']); day['protein'] += int(res['protein']); day['carbs'] += int(res['carbs']); day['fat'] += int(res['fat'])
                    day['meals'].append(f"📸 {res['food_name']} ({res['calories']} kcal)")
                    save_data(data); st.rerun()
            except:
                st.error("Could not scan clearly.")

with tab3:
    col_n, col_c = st.columns(2)
    m_name = col_n.text_input("Food Name")
    m_cal = col_c.number_input("Kcal", min_value=0, step=10)
    if st.button("Save Manual"):
        day['calories_in'] += m_cal; day['meals'].append(f"🔢 {m_name} ({m_cal} kcal)")
        save_data(data); st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# 6. UI: Log Your Daily Exercise
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("🏃‍♂️ Log Your Daily Exercise")
st.info("💡 Type your activity in any language (e.g., '30 min morning jogging' or '45 min gym kiya')")
act_text = st.text_input("What was your workout?")
if st.button("Calculate Burned Calories"):
    if act_text:
        with st.spinner("Calculating..."):
            act_prompt = f"User did this activity: '{act_text}'. Estimate calories burned for an average 70kg male. Return ONLY valid JSON with keys: 'activity_name', 'calories_burned' (integer). No markdown."
            response = model.generate_content(act_prompt)
            try:
                act_res = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                st.success(f"Burned {act_res['calories_burned']} kcal from {act_res['activity_name']}")
                if st.button("Save Workout"):
                    day['calories_burned'] += int(act_res['calories_burned'])
                    day['activity'].append(f"🏃 {act_res['activity_name']} (-{act_res['calories_burned']} kcal)")
                    save_data(data); st.rerun()
            except:
                st.error("Error reading workout data.")
                
if len(day['activity']) > 0:
    for act in day['activity']:
        st.write(act)
st.markdown('</div>', unsafe_allow_html=True)
