import streamlit as st
import pandas as pd
import os
import re
import io
from datetime import datetime
from docxtpl import DocxTemplate

# Supabase is optional
try:
    from supabase import create_client
except ImportError:
    create_client = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Automated Certificate Generator",
    page_icon="🎓",
    layout="centered"
)


# ============================================================
# CONSTANTS
# ============================================================

CSV_FILE = "students.csv"

CERTIFICATE_TEMPLATES = {
    "Bonafide Certificate": "bonafide_template.docx",
    "Internship Certificate": "internship_template.docx",
    "Character Certificate": "character_certificate.docx"
}

PORTAL_URL = "https://cuhstudents.streamlit.app/"

# NOTE:
# Production app mein password ko Streamlit Secrets mein rakhna better hai.
ADMIN_PASSWORD = "admin123"


# ============================================================
# CSV LOAD FUNCTION
# ============================================================

@st.cache_data
def load_csv_data():
    """
    students.csv ko safely load karta hai.

    CSV format:
    roll_no;"name";"father_name";"email";...
    """

    if not os.path.exists(CSV_FILE):
        return None

    try:
        # utf-8-sig BOM ko automatically remove karta hai
        df = pd.read_csv(
            CSV_FILE,
            sep=";",
            quotechar='"',
            encoding="utf-8-sig"
        )

        # ----------------------------------------------------
        # CLEAN COLUMN NAMES
        # ----------------------------------------------------

        df.columns = (
            df.columns
            .astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.replace('"', "", regex=False)
            .str.strip()
            .str.lower()
        )

        # Spaces ko underscore mein convert
        df.columns = (
            df.columns
            .str.replace(" ", "_", regex=False)
            .str.replace("-", "_", regex=False)
        )

        # ----------------------------------------------------
        # FIND ROLL NUMBER COLUMN
        # ----------------------------------------------------

        possible_roll_columns = [
            "roll_no",
            "roll_number",
            "rollno",
            "roll",
            "roll_no."
        ]

        found_roll_column = None

        for column in possible_roll_columns:
            if column in df.columns:
                found_roll_column = column
                break

        if found_roll_column is None:
            st.error(
                "❌ CSV mein Roll Number column nahi mila."
            )

            st.info(
                f"CSV ke available columns: "
                f"{df.columns.tolist()}"
            )

            return None

        # Standard naam
        if found_roll_column != "roll_no":
            df.rename(
                columns={found_roll_column: "roll_no"},
                inplace=True
            )

        # ----------------------------------------------------
        # CHECK REQUIRED COLUMNS
        # ----------------------------------------------------

        required_columns = [
            "roll_no",
            "name",
            "father_name"
        ]

        missing_columns = [
            col for col in required_columns
            if col not in df.columns
        ]

        if missing_columns:
            st.error(
                f"❌ CSV mein required column(s) missing hain: "
                f"{missing_columns}"
            )

            st.info(
                f"Available columns: {df.columns.tolist()}"
            )

            return None

        # ----------------------------------------------------
        # CLEAN IMPORTANT DATA
        # ----------------------------------------------------

        df["roll_no"] = (
            df["roll_no"]
            .astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.replace('"', "", regex=False)
            .str.strip()
        )

        df["name"] = (
            df["name"]
            .astype(str)
            .str.strip()
        )

        df["father_name"] = (
            df["father_name"]
            .astype(str)
            .str.strip()
        )

        return df

    except Exception as e:
        st.error(
            f"❌ CSV load karte waqt error aaya: {e}"
        )
        return None


# ============================================================
# FETCH STUDENT DATA
# ============================================================

def fetch_student_data(roll_no, df):
    """
    Roll number ke basis par student find karta hai.
    """

    if df is None:
        return None

    if df.empty:
        return None

    if "roll_no" not in df.columns:
        st.error(
            "❌ CSV mein 'roll_no' column nahi mila."
        )
        return None

    # User input clean
    search_roll = (
        str(roll_no)
        .strip()
        .replace('"', "")
    )

    # DataFrame roll numbers clean
    roll_series = (
        df["roll_no"]
        .astype(str)
        .str.strip()
        .str.replace('"', "", regex=False)
    )

    student = df[roll_series == search_roll]

    if not student.empty:

        name = str(
            student.iloc[0]["name"]
        ).strip()

        father_name = str(
            student.iloc[0]["father_name"]
        ).strip()

        return name, father_name, student

    return None


# ============================================================
# SUPABASE CLIENT
# ============================================================

@st.cache_resource
def get_supabase_client():
    """
    Supabase client create karta hai.

    Streamlit secrets expected:

    [supabase]
    url = "YOUR_SUPABASE_URL"
    key = "YOUR_SUPABASE_KEY"
    """

    if create_client is None:
        return None

    try:
        if "supabase" not in st.secrets:
            return None

        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]

        if not supabase_url or not supabase_key:
            return None

        return create_client(
            supabase_url,
            supabase_key
        )

    except Exception:
        return None


# ============================================================
# UPLOAD DOCUMENT TO SUPABASE
# ============================================================

def backup_to_supabase(
    file_bytes,
    filename,
    roll_number
):
    """
    Generated certificate ko Supabase Storage
    mein optional backup karta hai.

    Agar Supabase configured nahi hai,
    function silently skip karega.
    """

    try:

        supabase = get_supabase_client()

        if supabase is None:
            return False

        date_str = datetime.now().strftime("%Y-%m-%d")

        clean_roll = re.sub(
            r"[^a-zA-Z0-9_\-]",
            "_",
            str(roll_number)
        )

        cloud_path = (
            f"{date_str}/"
            f"{clean_roll}/"
            f"{filename}"
        )

        supabase.storage.from_(
            "certificates"
        ).upload(
            path=cloud_path,
            file=file_bytes,
            file_options={
                "content-type":
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document",
                "upsert": "true"
            }
        )

        return True

    except Exception:
        # Cloud backup fail hone par
        # certificate generation block nahi hoga
        return False


# ============================================================
# SESSION STATE
# ============================================================

if "student_found" not in st.session_state:
    st.session_state.student_found = False

if "s_name" not in st.session_state:
    st.session_state.s_name = ""

if "f_name" not in st.session_state:
    st.session_state.f_name = ""

if "full_data" not in st.session_state:
    st.session_state.full_data = None

if "fetched_roll" not in st.session_state:
    st.session_state.fetched_roll = ""

if "external_link_unlocked" not in st.session_state:
    st.session_state.external_link_unlocked = False


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⚡ Quick Actions")

st.sidebar.subheader("🌐 Student Portal")

if not st.session_state.external_link_unlocked:

    st.sidebar.info(
        "🔑 Student Portal link ko kholne "
        "ke liye admin password chahiye."
    )

    ext_pass = st.sidebar.text_input(
        "Admin Password",
        type="password",
        key="sidebar_ext_pass"
    )

    if st.sidebar.button(
        "🔓 Unlock Link",
        use_container_width=True
    ):

        if ext_pass == ADMIN_PASSWORD:

            st.session_state.external_link_unlocked = True

            st.rerun()

        else:

            st.sidebar.error(
                "❌ Galat Password!"
            )

else:

    st.sidebar.success(
        "🔓 Portal Link Unlocked"
    )

    st.sidebar.link_button(
        "🔗 Open CUH Student Portal",
        PORTAL_URL,
        use_container_width=True
    )

    if st.sidebar.button(
        "🔒 Re-lock Link",
        use_container_width=True
    ):

        st.session_state.external_link_unlocked = False

        st.rerun()


# ============================================================
# LOAD STUDENT DATABASE
# ============================================================

df_students = load_csv_data()


# ============================================================
# MAIN PAGE
# ============================================================

st.title("🎓 Automated Certificate Generator")

st.write(
    "Roll Number daliye aur certificate generate kijiye."
)


# ============================================================
# CSV STATUS
# ============================================================

if df_students is None:

    st.error(
        "⚠️ 'students.csv' file nahi mili "
        "ya CSV properly load nahi hui."
    )

    st.info(
        "Ensure karein ki students.csv "
        "app.py ke same folder mein hai."
    )

else:

    # Optional information
    st.success(
        f"✅ Student database loaded: "
        f"{len(df_students)} records"
    )


# ============================================================
# CERTIFICATE TYPE
# ============================================================

cert_type = st.selectbox(
    "Certificate Ka Type Select Karein",
    [
        "Bonafide Certificate",
        "Internship Certificate",
        "Character Certificate"
    ]
)


# ============================================================
# ROLL NUMBER INPUT
# ============================================================

roll_input = st.text_input(
    "Student Roll Number Darj Karein",
    placeholder="Example: 260606"
)


# ============================================================
# FETCH BUTTON
# ============================================================

if st.button(
    "🔍 Fetch Student Data",
    use_container_width=True
):

    # Reset old data
    st.session_state.student_found = False
    st.session_state.s_name = ""
    st.session_state.f_name = ""
    st.session_state.full_data = None

    if df_students is None:

        st.warning(
            "Pehle students.csv file properly load karein."
        )

    elif not roll_input.strip():

        st.warning(
            "⚠️ Roll Number darj karein."
        )

    else:

        student_info = fetch_student_data(
            roll_input.strip(),
            df_students
        )

        if student_info:

            st.session_state.student_found = True

            st.session_state.s_name = student_info[0]

            st.session_state.f_name = student_info[1]

            st.session_state.full_data = student_info[2]

            st.session_state.fetched_roll = (
                roll_input.strip()
            )

            st.success(
                "✅ Student data mil gaya!"
            )

        else:

            st.error(
                f"❌ Roll Number '{roll_input.strip()}' "
                "database mein nahi mila."
            )


# ============================================================
# STUDENT DETAILS + DOCUMENT GENERATION
# ============================================================

if st.session_state.student_found:

    st.markdown("---")

    st.subheader("👨‍🎓 Student Details")

    # Auto-filled student name
    st.text_input(
        "Student Name",
        value=st.session_state.s_name,
        disabled=True
    )

    # Auto-filled father name
    st.text_input(
        "Father's Name",
        value=st.session_state.f_name,
        disabled=True
    )

    # Roll number
    st.text_input(
        "Roll Number",
        value=st.session_state.fetched_roll,
        disabled=True
    )

    # ========================================================
    # SEMESTER
    # ========================================================

    semester = st.selectbox(
        "Semester Select Karein",
        [
            "1st Semester",
            "2nd Semester",
            "3rd Semester",
            "4th Semester",
            "5th Semester",
            "6th Semester",
            "7th Semester",
            "8th Semester"
        ]
    )

    # ========================================================
    # SELECT TEMPLATE
    # ========================================================

    template_file = CERTIFICATE_TEMPLATES[
        cert_type
    ]

    st.info(
        f"📄 Template: `{template_file}`"
    )

    # ========================================================
    # GENERATE DOCUMENT
    # ========================================================

    if st.button(
        "📄 Generate Document",
        use_container_width=True
    ):

        # ----------------------------------------------------
        # Validate Roll Number
        # ----------------------------------------------------

        if not st.session_state.fetched_roll:

            st.error(
                "❌ Roll Number required hai."
            )

        # ----------------------------------------------------
        # Validate Template
        # ----------------------------------------------------

        elif not os.path.exists(template_file):

            st.error(
                f"⚠️ Template file "
                f"'{template_file}' nahi mili."
            )

            st.info(
                "Template file ko app.py ke "
                "same folder mein rakhein."
            )

        else:

            try:

                with st.spinner(
                    "⏳ Certificate generate ho raha hai..."
                ):

                    # ------------------------------------------------
                    # ROLL NUMBER
                    # ------------------------------------------------

                    actual_roll = str(
                        st.session_state.full_data
                        .iloc[0]["roll_no"]
                    ).strip()

                    # ------------------------------------------------
                    # DOCX CONTEXT
                    # ------------------------------------------------

                    context = {
                        "sname":
                            st.session_state.s_name,

                        "sfname":
                            st.session_state.f_name,

                        "roll":
                            actual_roll,

                        "semester":
                            semester
                    }

                    # ------------------------------------------------
                    # SAFE FILE NAME
                    # ------------------------------------------------

                    clean_cert_type = re.sub(
                        r"[^a-zA-Z0-9_\-]",
                        "_",
                        cert_type
                    )

                    clean_roll = re.sub(
                        r"[^a-zA-Z0-9_\-]",
                        "_",
                        actual_roll
                    )

                    final_docx_name = (
                        f"{clean_cert_type}_"
                        f"{clean_roll}.docx"
                    )

                    # ------------------------------------------------
                    # LOAD TEMPLATE
                    # ------------------------------------------------

                    doc = DocxTemplate(
                        template_file
                    )

                    # ------------------------------------------------
                    # RENDER
                    # ------------------------------------------------

                    doc.render(context)

                    # ------------------------------------------------
                    # SAVE TO MEMORY
                    # ------------------------------------------------

                    bio = io.BytesIO()

                    doc.save(bio)

                    bio.seek(0)

                    document_bytes = bio.getvalue()

                # ====================================================
                # SUPABASE OPTIONAL BACKUP
                # ====================================================

                backup_success = backup_to_supabase(
                    document_bytes,
                    final_docx_name,
                    actual_roll
                )

                if backup_success:

                    st.success(
                        "☁️ Certificate ka cloud backup "
                        "successfully save ho gaya."
                    )

                # ====================================================
                # DOWNLOAD
                # ====================================================

                st.success(
                    "🎉 Certificate successfully generated!"
                )

                st.download_button(
                    label="📥 Download Certificate Now",
                    data=document_bytes,
                    file_name=final_docx_name,
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.wordprocessingml.document"
                    ),
                    use_container_width=True
                )

            except Exception as e:

                st.error(
                    "❌ Certificate generate karte waqt error aaya."
                )

                st.exception(e)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🎓 Automated Certificate Generator"
)
