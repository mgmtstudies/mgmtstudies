import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
from docxtpl import DocxTemplate
from supabase import create_client
import io


# CSV FILE SE DATA LOAD KARNE KA FUNCTION (OPTIMIZED FOR YOUR CSV)
@st.cache_data
def load_csv_data():
    file_path = 'students.csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, sep=';', quotechar='"', encoding='utf-8')
        df.columns = df.columns.str.strip().str.replace('"', '')
        if 'roll_no' in df.columns:
            df['roll_no'] = df['roll_no'].astype(str).str.replace('"', '').str.strip()
        return df
    return None

def fetch_student_data(roll_no, df):
    if df is not None and not df.empty:
        student = df[df['roll_no'] == roll_no]
        if not student.empty:
            name = str(student.iloc[0]['name']).strip()
            fname = str(student.iloc[0]['father_name']).strip()
            return name, fname, student
    return None

# Session States Management
if 'student_found' not in st.session_state:
    st.session_state.student_found = False
    st.session_state.s_name = ""
    st.session_state.f_name = ""
    st.session_state.full_data = None

if 'external_link_unlocked' not in st.session_state:
    st.session_state.external_link_unlocked = False

# ====================================================================
# QUICK SIDEBAR REDIRECT (Without Page Navigation)
# ====================================================================
st.sidebar.title("Quick Actions")
st.sidebar.subheader("🌐 Quick Redirect")

# EXTERNAL URL WITH PASSWORD PROTECTION LOGIC
if not st.session_state.external_link_unlocked:
    st.sidebar.info("🔑 Student Portal link ko kholne ke liye password chahiye.")
    ext_pass = st.sidebar.text_input("Admin Password", type="password", key="sidebar_ext_pass")
    
    if st.sidebar.button("Unlock Link", use_container_width=True):
        if ext_pass == "admin123":
            st.session_state.external_link_unlocked = True
            st.rerun()
        else:
            st.sidebar.error("Galat Password!")
else:
    st.sidebar.success("🔓 Link Unlocked")
    st.sidebar.link_button(
        "🔗 Open CUH Student Portal", 
        "https://cuhstudents.streamlit.app/", 
        use_container_width=True
    )
    if st.sidebar.button("🔒 Re-lock Link", use_container_width=True):
        st.session_state.external_link_unlocked = False
        st.rerun()

df_students = load_csv_data()

# ====================================================================
# MAIN PAGE: GENERATE CERTIFICATE
# ====================================================================
st.title("🎓 Automated Certificate Generator")
st.write("Roll Number daliye aur certificate generate kijiye.")

if df_students is None:
    st.error("⚠️ 'students.csv' file nahi mili!")

cert_type = st.selectbox(
    "Certificate Ka Type Select Karein",
    ["Bonafide Certificate", "Internship Certificate", "Character Certificate"]
)

roll_input = st.text_input("Student Roll Number Darj Karein")

if st.button("Fetch Student Data"):
    if df_students is None:
        st.warning("Pehle CSV/Database file upload karein.")
    elif roll_input:
        student_info = fetch_student_data(roll_input.strip(), df_students)

        if student_info:
            st.session_state.student_found = True
            st.session_state.s_name = student_info[0]
            st.session_state.f_name = student_info[1]
            st.session_state.full_data = student_info[2]
            st.success("Student data mil gaya! Niche Scroll Kare")
        else:
            st.session_state.student_found = False
            st.error("Roll Number database me nahi mila!")
    else:
        st.warning("Roll Number darj karein.")

if st.session_state.student_found:
    st.markdown("---")

    st.text_input("Student Name(Auto Fill-No Need to fill)", value=st.session_state.s_name, disabled=True)
    st.text_input("Father's Name(Auto Fill-No Need to fill)", value=st.session_state.f_name, disabled=True)

    semester = st.selectbox(
        "Semester Select Karein",
        [
            "1st Semester", "2nd Semester", "3rd Semester", "4th Semester",
            "5th Semester", "6th Semester", "7th Semester", "8th Semester"
        ]
    )

    if cert_type == "Bonafide Certificate":
        template_file = "bonafide_template.docx"
    elif cert_type == "Internship Certificate":
        template_file = "internship_template.docx"
    elif cert_type == "Character Certificate":
        template_file = "character_certificate.docx"

    if st.button("Generate Document"):
        if not roll_input:
            st.error("❌ Action Blocked: Roll Number entered hona zaroori hai.")
        else:
            if os.path.exists(template_file):
                with st.spinner("Processing document..."):
                    
                    context = {
                        "sname": st.session_state.s_name,
                        "sfname": st.session_state.f_name,
                        "roll": str(st.session_state.full_data.iloc[0]['roll_no']),
                        "semester": semester
                    }

                    clean_cert_type = re.sub(r'[^a-zA-Z0-9_\-]', '_', cert_type)
                    clean_roll_input = re.sub(r'[^a-zA-Z0-9_\-]', '_', roll_input)
                    final_docx_name = f"{clean_cert_type}_{clean_roll_input}.docx"
                    
                    # Generate Document in Memory
                    doc = DocxTemplate(template_file)
                    doc.render(context)
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    # Optional: Backup to Supabase Cloud
                    try:
                        date_str = datetime.now().strftime('%Y-%m-%d')
                        base_cloud_path = f"{date_str}/{clean_roll_input}"
                        cloud_docx_path = f"{base_cloud_path}/{final_docx_name}"
                        
                        supabase.storage.from_("certificates").upload(
                            path=cloud_docx_path,
                            file=bio.getvalue(),
                            file_options={
                                "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "x-upsert": "true"
                            }
                        )
                    except Exception as e:
                        pass # Ignore cloud errors to ensure download still works
                    
                    # Direct Download Button
                    st.download_button(
                        label="📥 Download Certificate Now",
                        data=bio.getvalue(),
                        file_name=final_docx_name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            else:
                st.error(f"⚠️ Template file '{template_file}' nahi mili!")
