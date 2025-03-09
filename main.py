
# 1. DISABLE STREAMLIT WATCHER FIRST
import os
os.environ["STREAMLIT_SERVER_ENABLE_STATIC_FILE_WATCHER"] = "false"

# 2. MONKEYPATCH BEFORE ANY OTHER IMPORTS
import sys
import streamlit.watcher.local_sources_watcher as watcher

original_get_module_paths = watcher.get_module_paths

def patched_get_module_paths(module):
    """Skip torch.classes module inspection"""
    if 'torch._classes' in str(module):
        return []
    return original_get_module_paths(module)

watcher.get_module_paths = patched_get_module_paths

# 3. NOW IMPORT OTHER LIBRARIES
from datetime import datetime
from transformers import BertTokenizer, BertModel
import torch
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import streamlit as st
import google.generativeai as genai
import pdfkit
from io import BytesIO
import bcrypt
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
import re

# 4. REST OF YOUR ORIGINAL CODE FOLLOWS...
# [Keep all your existing code from the original file here]

# Configure Gemini API
API_KEY="AIzaSyBCNZBnzqNUkmfKLRbOrA9wOw1VaOzQ86Q"
genai.configure(api_key=API_KEY)  # Replace with your API key

# Configure PDFKit (Update path to your wkhtmltopdf installation)
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'  # Windows example
pdf_config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

USER_CREDENTIALS_FILE = "users.json"
# Load BERT model and tokenizer
bert_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
bert_model = BertModel.from_pretrained("bert-base-uncased")


def load_users():
    try:
        if os.path.exists(USER_CREDENTIALS_FILE):
            with open(USER_CREDENTIALS_FILE, "r") as file:
                users = json.load(file)
                # Ensure 'history' field exists for all users
                if isinstance(users, list):
                    users = {u['username']: u for u in users}
                for username, user_data in users.items():
                    if "history" not in user_data:
                        user_data["history"] = []  # Initialize history if missing
                return users
        return {}
    except Exception as e:
        st.error(f"Error loading users: {str(e)}")
        return {}


def save_users(users):
    try:
        with open(USER_CREDENTIALS_FILE, "w") as file:
            # Save as a list of user dictionaries
            json.dump(list(users.values()), file)
    except Exception as e:
        st.error(f"Error saving users: {str(e)}")

def delete_history_entry(username, timestamp):
    users = load_users()
    if username in users:
        users[username]["history"] = [entry for entry in users[username].get("history", []) if entry["timestamp"] != timestamp]
        save_users(users)
        st.success("History entry deleted successfully!")
        st.rerun()


def register_user(username, email, password, confirm_password):
    users = load_users()
    if username in users:
        return False, "Username already exists."
    if password != confirm_password:
        return False, "Passwords do not match."
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {
        "username": username,
        "email": email,
        "password": hashed_pw,
        "history": []  # Initialize history
    }
    save_users(users)
    return True, "Registration successful. Please log in."
# Update study plan generation
def save_study_plan(username, plan_data):
    users = load_users()
    if username in users:
        if "history" not in users[username]:
            users[username]["history"] = []  # Initialize history if missing
        users[username]["history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plan": plan_data
        })
        save_users(users)

def get_user_history(username):
    users = load_users()
    if username in users:
        return users[username].get("history", [])
    return []


def authenticate_user(username, password):
    users = load_users()
    user_data = users.get(username)
    if user_data and bcrypt.checkpw(password.encode(), user_data["password"].encode()):
        return True
    return False


def extract_bert_embedding(text):
    """Extracts a meaningful sentence embedding from BERT."""
    inputs = bert_tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        outputs = bert_model(**inputs)

    # CLS token embedding (used to represent the entire sentence)
    sentence_embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
    return sentence_embedding


def analyze_study_preferences(topic, goals, strengths, weaknesses):
    """Computes insights using BERT embeddings."""
    # Extract embeddings
    topic_emb = extract_bert_embedding(topic)
    goal_emb = extract_bert_embedding(goals)
    strength_emb = extract_bert_embedding(strengths)
    weakness_emb = extract_bert_embedding(weaknesses)

    # Compute similarity scores
    goal_similarity = cosine_similarity([topic_emb], [goal_emb])[0][0]
    strength_similarity = cosine_similarity([topic_emb], [strength_emb])[0][0]
    weakness_similarity = cosine_similarity([topic_emb], [weakness_emb])[0][0]

    insights = f"""
    - Goal Alignment Score: {goal_similarity:.2f}
    - Strength Relevance Score: {strength_similarity:.2f}
    - Weakness Impact Score: {weakness_similarity:.2f}
    """
    return insights


# Study Plan Generation
def generate_study_plan(topic, hours_per_day, goals, strengths, weaknesses, preferences):
    """Generates a study plan using Gemini AI with insights from BERT."""
    insights = analyze_study_preferences(topic, goals, strengths, weaknesses)

    prompt = f"""
    Create a structured, personalized study plan for the topic: {topic}.

    User Preferences:
    - Daily Study Hours: {hours_per_day}
    - Preferred Learning Methods: {preferences}

    AI-Driven Insights:
    {insights}

    Please include:
    - A structured daily schedule
    - Techniques to improve weak areas
    - How to leverage strengths effectively
    - A revision strategy
    - Recommended resources based on learning methods
    """

    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)

    return response.text if response else "Error generating study plan."


# Initialize Session States
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "main"
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "study_plan" not in st.session_state:
    st.session_state.study_plan = None

# Page Configuration
st.set_page_config(page_title="StudBud - AI Study Planner", layout="centered")

# Custom CSS
# Prevent Scrolling by Limiting Content Height
st.markdown("""
    <style>
        /* Fix page layout to prevent scrolling */
        .main .block-container {
            max-width: 600px;
            margin: auto;
            padding-top: 50px;
        }
        /* Center text */
        .centered-text {
            text-align: center;
        }
        /* Increase button size */
        .stButton>button {
            font-size: 16px;
            font-weight: bold;
            padding: 10px;
            width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

# Header Section (Always Visible)
st.markdown("<div class='centered'>", unsafe_allow_html=True)
st.title("🎓 StudBud")
st.subheader("AI-Powered Personalized Study Planner")
st.markdown("</div>", unsafe_allow_html=True)

# Main Landing Page
if not st.session_state.user_authenticated and st.session_state.auth_page == "main":
    # Set default auth form
    if 'auth_form' not in st.session_state:
        st.session_state.auth_form = 'login'

    # # Main title
    # st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>🎓 StudBud</h1>", unsafe_allow_html=True)
    # st.markdown("<h3 style='text-align: center; margin-bottom: 40px;'>AI-Powered Personalized Study Planner</h3>",
    #             unsafe_allow_html=True)

    # Form selection buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Login", use_container_width=True):
            st.session_state.auth_form = 'login'
    with col2:
        if st.button("📝 Signup", use_container_width=True):
            st.session_state.auth_form = 'signup'

    # In the Main Landing Page section
    # Replace the existing auth forms code with this

    # Auth forms
    auth_container = st.container()
    with auth_container:
        if st.session_state.auth_form == 'login':
            with st.form("login_form", clear_on_submit=True):
                st.subheader("Enter Login details")
                cols = st.columns(1)
                with cols[0]:
                    login_username = st.text_input("Username",
                                                   placeholder="Enter your username")
                    login_password = st.text_input("Password",
                                                   type="password",
                                                   placeholder="••••••••")

                    if st.form_submit_button("Login",
                                             use_container_width=True,
                                             type="primary"):
                        if authenticate_user(login_username, login_password):
                            st.session_state.user_authenticated = True
                            st.session_state.logged_in_user = login_username
                            st.rerun()
                        else:
                            st.error("Invalid credentials")

        else:
            with st.form("register_form", clear_on_submit=True):
                st.subheader("Create Account")
                cols = st.columns(1)
                with cols[0]:
                    reg_username = st.text_input("Choose Username",
                                                 placeholder="Minimum 6 characters")
                    reg_email = st.text_input("Email Address",
                                              placeholder="student@example.com")
                    reg_password = st.text_input("Create Password",
                                                 type="password",
                                                 help="Minimum 8 characters with mix of letters and numbers")
                    reg_confirm = st.text_input("Confirm Password",
                                                type="password")

                    if st.form_submit_button("Signup",
                                             use_container_width=True,
                                             type="primary"):
                        if not all([reg_username, reg_email, reg_password, reg_confirm]):
                            st.error("Please fill in all fields")
                        elif reg_password != reg_confirm:
                            st.error("Passwords do not match")
                        else:
                            success, message = register_user(reg_username, reg_email, reg_password, reg_confirm)
                            if success:
                                st.success(message)
                                st.session_state.auth_form = 'login'
                            else:
                                st.error(message)

    # Guest access
    st.markdown("---")
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    if st.button("🚀 Continue as Guest", key="guest_btn"):
        st.session_state.user_authenticated = True
        st.session_state.logged_in_user = "guest"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Add spacing for better UI
    st.markdown("<br><br>", unsafe_allow_html=True)

    # Styling improvements
    st.markdown("""
    <style>
        .stButton>button {
            font-size: 16px;
            font-weight: bold;
            padding: 10px;
        }
    </style>
    """, unsafe_allow_html=True)


# Authentication Pages
elif not st.session_state.user_authenticated:
    # Login Page
    if st.session_state.auth_page == "login":
        st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
        st.header("Login")

        login_username = st.text_input("Username")
        login_password = st.text_input("Password", type="password")

        if st.button("Sign In"):
            if not login_username or not login_password:
                st.error("Please fill in all fields")
            elif authenticate_user(login_username, login_password):
                st.session_state.user_authenticated = True
                st.session_state.logged_in_user = login_username
                st.rerun()
            else:
                st.error("Invalid credentials")

        if st.button("Back to Main"):
            st.session_state.auth_page = "main"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Signup Page
    elif st.session_state.auth_page == "signup":
        st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
        st.header("Register")

        reg_username = st.text_input("Username")
        reg_email = st.text_input("Email")
        reg_password = st.text_input("Password", type="password")
        reg_confirm = st.text_input("Confirm Password", type="password")

        if st.button("Create Account"):
            if not all([reg_username, reg_email, reg_password, reg_confirm]):
                st.error("Please fill in all fields")
            elif reg_password != reg_confirm:
                st.error("Passwords do not match")
            else:
                success, message = register_user(reg_username, reg_email, reg_password, reg_confirm)
                if success:
                    st.success(message)
                    st.session_state.auth_page = "login"
                    st.rerun()
                else:
                    st.error(message)

        if st.button("Back to Main"):
            st.session_state.auth_page = "main"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# Main Application
else:
    # Add this cleanup check first
    if not st.session_state.user_authenticated:
        st.session_state.study_plan = None
        st.session_state.selected_history_id = None

    # Rest of your existing code...
    # Logout functionality
    if st.session_state.logged_in_user == "guest":
        st.sidebar.header("Guest Mode")
        if st.sidebar.button("Return to Main Page"):
            st.session_state.user_authenticated = False
            st.session_state.logged_in_user = None
            st.rerun()
    else:
        st.sidebar.header(f"Welcome, {st.session_state.logged_in_user}")
        if st.sidebar.button("Logout"):
            # Clear all user-related session states
            st.session_state.update({
                "user_authenticated": False,
                "logged_in_user": None,
                "study_plan": None,
                "selected_history_id": None,
                "auth_page": "main"
            })
            st.rerun()

    with st.sidebar.expander("📚 Learning Preferences"):
        topic = st.text_input("Enter Topic (e.g., Calculus, World War II, Python Programming):")
        goals = st.text_input("Specific Goals (e.g., Improve calculus skills):")
        strengths = st.text_input("Strengths (e.g., Good at algebra):")
        weaknesses = st.text_input("Weaknesses (e.g., Weak in geometry):")
        preferences = st.text_input("Preferences (e.g., Videos, Practice Problems):")
        time = st.number_input("Available Study Time (hours/day):", min_value=1, max_value=24)

        if st.button("Generate Study Plan"):
            if topic:
                study_plan = generate_study_plan(topic, time, goals, strengths, weaknesses, preferences)
                st.session_state.study_plan = study_plan
                if st.session_state.logged_in_user != "guest":
                    save_study_plan(st.session_state.logged_in_user, {
                        "topic": topic,
                        "goals": goals,
                        "strengths": strengths,
                        "weaknesses": weaknesses,
                        "preferences": preferences,
                        "hours": time,
                        "plan": study_plan
                    })

    # Sidebar - Study History
    if st.session_state.user_authenticated and st.session_state.logged_in_user != "guest":
        st.sidebar.header("📜 Study History")

        if "logged_in_user" in st.session_state and st.session_state.logged_in_user:
            history = get_user_history(st.session_state.logged_in_user)

            # In the "Study History" section of your code, modify this part:

            # In the "Study History" section of your code, modify this part:

            if history:
                for entry in reversed(history):
                    item_container = st.sidebar.container()
                    col1, col2, col3 = item_container.columns([6, 1, 1])

                    with col1:
                        # Display topic instead of timestamp
                        topic = entry['plan'].get('topic', 'Unknown Topic')
                        st.markdown(f"📚 **Study plan for {topic}**")

                    with col2:
                        if st.button("👁️", key=f"view_{entry['timestamp']}"):
                            st.session_state.selected_history_id = entry["timestamp"]

                    with col3:
                        if st.button("🗑️", key=f"del_{entry['timestamp']}"):
                            delete_history_entry(st.session_state.logged_in_user, entry['timestamp'])
                            st.rerun()

                    item_container.markdown("---")
            else:
                st.sidebar.write("No history available.")

    # Main Content - Display Current Study Plan
    if st.session_state.study_plan:
        st.subheader("📅 Your Personalized Study Plan")
        st.write(st.session_state.study_plan)

    # Main Content - Display Selected History Plan
    # Main Content - Display Selected History Plan
    if st.session_state.get('selected_history_id'):
        history = get_user_history(st.session_state.logged_in_user)
        selected_entry = next(
            (entry for entry in reversed(history) if entry['timestamp'] == st.session_state.selected_history_id),
            None
        )

        if selected_entry:
            st.subheader(f"📚 Archived Plan - {selected_entry['timestamp']}")

            # Display key information using CORRECT KEYS
            with st.container():
                cols = st.columns([0.3, 0.7])
                with cols[0]:
                    st.write("**Topic:**")
                    st.write("**Hours/Day:**")
                    st.write("**Preferences:**")
                with cols[1]:
                    st.write(selected_entry['plan']['topic'])  # Changed from 'subjects'
                    st.write(selected_entry['plan']['hours'])
                    st.write(selected_entry['plan']['preferences'])

            st.markdown("---")
            st.subheader("Study Plan Details")
            st.write(selected_entry['plan']['plan'])  # The actual generated plan text

        # PDF Generation with Proper Bullet Points
        def create_pdf():
            try:
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer,
                                        pagesize=letter,
                                        rightMargin=40,
                                        leftMargin=40,
                                        topMargin=40,
                                        bottomMargin=40)

                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(
                    name='Bullet',
                    parent=styles['BodyText'],
                    leftIndent=20,
                    firstLineIndent=-10,
                    spaceAfter=10
                ))

                content = []

                # Title Section
                title = Paragraph("<b>StudBud Personalized Study Plan</b>", styles["Title"])
                content.append(title)
                content.append(Spacer(1, 16))

                # User Info
                user_info = Paragraph(
                    f"<b>Student:</b> {st.session_state.logged_in_user}<br/>"
                    f"<b>Generated on:</b> {datetime.datetime.now().strftime('%Y-%m-%d')}",
                    styles["Normal"]
                )
                content.append(user_info)
                content.append(Spacer(1, 24))

                # Process Study Plan Content
                raw_text = st.session_state.study_plan

                # Convert markdown bullets to proper formatting
                formatted_text = re.sub(r'(?m)^(\s*)[*\-+] ', r'\1• ', raw_text)

                # Split into logical sections
                sections = formatted_text.split('\n\n')

                for section in sections:
                    # Clean up whitespace
                    section = section.strip()
                    if not section:
                        continue

                    # Handle bullet points
                    if '•' in section:
                        lines = section.split('\n')
                        for line in lines:
                            if line.strip().startswith('•'):
                                p = Paragraph(line.replace('•', '&#8226;'), styles["Bullet"])
                            else:
                                p = Paragraph(line, styles["BodyText"])
                            content.append(p)
                            content.append(Spacer(1, 8))
                    else:
                        p = Paragraph(section, styles["BodyText"])
                        content.append(p)
                        content.append(Spacer(1, 12))

                doc.build(content)
                buffer.seek(0)
                return buffer
            except Exception as e:
                st.error(f"PDF generation error: {str(e)}")
                return None


        pdf_bytes = create_pdf()
        if pdf_bytes:
            st.download_button(
                label="📥 Download as PDF",
                data=pdf_bytes,
                file_name="studbud_plan.pdf",
                mime="application/pdf"
            )
#Styles
st.markdown("""
    <style>
        /* Main title styling */
        .main-title {
            text-align: center;
            font-size: 2.5rem !important;
            margin-bottom: 0.5rem !important;
            color: #2d3748;
        }

        /* Subtitle styling */
        .sub-title {
            text-align: center;
            font-size: 1.2rem !important;
            margin-bottom: 2rem !important;
            color: #4a5568;
        }

        /* Auth button container */
        .auth-buttons {
            margin: 2rem 0;
            display: flex;
            justify-content: center;
            gap: 1rem;
        }

        /* Form styling */
        .stTextInput>div>div>input {
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
        }

        /* Login button styling */
        .login-btn {
            background-color: #48bb78 !important;
            color: white !important;
            width: 100%;
            padding: 12px;
            border-radius: 6px;
            margin-top: 1rem;
        }

        /* Footer styling */
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: white;
            text-align: center;
            padding: 1rem;
            border-top: 1px solid #e2e8f0;
        }
         <style>
        .main-title-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            # justify-content: center;
            text-align: center;
            margin: 2rem 0;
        }
        
        .main-title {
            font-size: 2.5rem !important;
            color: #2d3748;
            margin-bottom: 0.5rem !important;
            width: 100%;
        }
        
        .sub-title {
            font-size: 1.2rem !important;
            color: #4a5568;
            width: 100%;
        }
               .history-card {
            width: 220px;
            height: 18px;
            padding: 12px;
            margin: 8px 0;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s;
        }
        .history-card:hover {
            background: #f1f3f5;
            transform: translateY(-1px);
        }
        .card-text {
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 160px;
        }
        .card-icons {
            display: flex;
            gap: 8px;
        }
        .card-icon {
            font-size: 14px !important;
            padding: 0 4px !important;
            min-width: 30px !important;
            height: 24px !important;
        }
    </style>
""", unsafe_allow_html=True)

# Footer
st.markdown("""
<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: white;
    text-align: center;
    padding: 10px;
}
</style>
<div class="footer">
    <p>Developed with ❤️ using Streamlit & Gemini AI | © 2024 StudBud</p>
</div>
""", unsafe_allow_html=True)