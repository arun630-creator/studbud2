from datetime import datetime

import streamlit as st
import google.generativeai as genai
import pdfkit
import os
from io import BytesIO
import bcrypt
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
import re

# Configure Gemini API
genai.configure(api_key="AIzaSyBCNZBnzqNUkmfKLRbOrA9wOw1VaOzQ86Q")  # Replace with your API key

# Configure PDFKit (Update path to your wkhtmltopdf installation)
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'  # Windows example
pdf_config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

USER_CREDENTIALS_FILE = "users.json"


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


# Study Plan Generation
def generate_study_plan(subjects, hours_per_day, preferences):
    prompt = f"""
    Create a detailed study plan for: {', '.join(subjects)}.
    Available hours per day: {hours_per_day}
    Preferences: {preferences}
    Include daily schedule, weekly goals, and revision strategy.
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
st.markdown("""
<style>
    .centered {
        text-align: center;
        margin-bottom: 2rem;
    }
    .big-font {
        font-size: 1.5rem !important;
        margin-top: 2rem !important;
    }
    .auth-box {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        border: 1px solid #ddd;
        border-radius: 10px;
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
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Sign Up", use_container_width=True):
            st.session_state.auth_page = "signup"
            st.rerun()

        if st.button("Login", use_container_width=True):
            st.session_state.auth_page = "login"
            st.rerun()

    # Guest Access Button
    st.markdown("<div class='centered big-font'>", unsafe_allow_html=True)
    if st.button("Continue as Guest", key="guest_btn"):
        st.session_state.user_authenticated = True
        st.session_state.logged_in_user = "guest"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

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
            st.session_state.user_authenticated = False
            st.session_state.logged_in_user = None
            st.rerun()

    # Study Plan Configuration
    with st.sidebar.expander("📚 Study Preferences"):
        subjects = st.multiselect(
            "Select Subjects",
            ["Mathematics", "Physics", "Chemistry", "Biology",
             "History", "Literature", "Computer Science", "Foreign Languages"]
        )
        hours = st.slider("Daily Study Hours", 1, 12, 3)
        preferences = st.text_area("Learning Preferences",
                                   "Morning study sessions, Visual learning, Weekly reviews")

        if st.button("Generate Study Plan"):
            if subjects:
                study_plan = generate_study_plan(subjects, hours, preferences)
                st.session_state.study_plan = study_plan
                if st.session_state.logged_in_user != "guest":
                    save_study_plan(st.session_state.logged_in_user, {
                        "subjects": subjects,
                        "hours": hours,
                        "preferences": preferences,
                        "plan": study_plan
                    })
    # Sidebar - Study History
    if st.session_state.user_authenticated and st.session_state.logged_in_user != "guest":
        st.sidebar.header("📜 Study History")

        history = get_user_history(st.session_state.logged_in_user)

        if history:
            # Store clicked state in session
            if 'selected_history_id' not in st.session_state:
                st.session_state.selected_history_id = None

            for i, entry in enumerate(reversed(history)):
                entry_id = entry['timestamp']  # Use timestamp as unique ID

                # Create clickable button to load the history item
                if st.sidebar.button(
                        f"📌 Plan {len(history) - i} - {entry['timestamp']}",
                        key=f"hist_{entry_id}",
                        use_container_width=True
                ):
                    st.session_state.selected_history_id = entry_id  # Store the selected history item

            st.sidebar.markdown("---")

            # Button to clear the selected history view
            if st.sidebar.button("Clear History View"):
                st.session_state.selected_history_id = None
        else:
            st.sidebar.write("No history available.")

    # Main Content - Display Current Study Plan
    if st.session_state.study_plan:
        st.subheader("📅 Your Personalized Study Plan")
        st.write(st.session_state.study_plan)

    # Main Content - Display Selected History Plan
    if st.session_state.get('selected_history_id'):
        history = get_user_history(st.session_state.logged_in_user)

        # Find the selected history entry
        selected_entry = next(
            (entry for entry in reversed(history) if entry['timestamp'] == st.session_state.selected_history_id),
            None
        )

        if selected_entry:  # Ensure the entry exists before displaying
            st.subheader(f"📚 Archived Plan - {selected_entry['timestamp']}")

            # Display key information in columns
            with st.container():
                cols = st.columns([0.2, 0.8])
                with cols[0]:
                    st.write("**Subjects:**")
                    st.write("**Hours/Day:**")
                    st.write("**Preferences:**")
                with cols[1]:
                    st.write(", ".join(selected_entry['plan']['subjects']))
                    st.write(selected_entry['plan']['hours'])
                    st.write(selected_entry['plan']['preferences'])

            st.markdown("---")
            st.subheader("Study Plan Details")
            st.write(selected_entry['plan']['plan'])

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
# Footer
st.markdown("---")
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