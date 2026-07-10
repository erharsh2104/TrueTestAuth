import streamlit as st
from datetime import datetime

def inject_global_css():
    st.markdown("""
    <style>
    /* ── STREAMLIT CHROME REMOVAL ── */
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    header { visibility: hidden !important; }
    [data-testid="stToolbar"] { display: none !important; }
    .stDeployButton { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    /* ── REMOVE ALL DEFAULT PADDING ── */
    .main .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        max-width: 100% !important;
    }

    /* ── REMOVE STREAMLIT DEFAULT SIDEBAR ── */
    section[data-testid="stSidebar"] {
        display: none !important;
    }

    /* ── FULL HEIGHT APP ── */
    html, body, [data-testid="stAppViewContainer"] {
        height: 100% !important;
        overflow: hidden !important;
    }
    [data-testid="stAppViewContainer"] {
        display: flex !important;
        flex-direction: column !important;
    }

    /* ── FONT ── */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    html, body, * {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        box-sizing: border-box !important;
    }

    /* ── STREAMLIT ELEMENT RESETS ── */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 13.5px !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }
    .stTextInput > div > div > input {
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        font-size: 14px !important;
        padding: 10px 14px !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #5b5ef4 !important;
        box-shadow: 0 0 0 3px rgba(91,94,244,0.12) !important;
        outline: none !important;
    }
    .stSelectbox > div > div {
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
    }
    .stTextArea > div > div > textarea {
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        font-size: 14px !important;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #5b5ef4, #7c3aed) !important;
        border-radius: 99px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: #0f172a !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: #f1f5f9 !important;
        border-radius: 12px !important;
        padding: 4px !important;
        gap: 4px !important;
        border: none !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 13.5px !important;
        padding: 8px 18px !important;
        color: #64748b !important;
        background: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #5b5ef4 !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
    }
    div[data-testid="stVerticalBlock"] { gap: 0 !important; }
    div[data-testid="stHorizontalBlock"] { gap: 0 !important; align-items: stretch !important; }
    </style>
    """, unsafe_allow_html=True)


def show_login_page_layout(role_callback, form_callback):
    # Step 1: inject page-specific CSS
    st.markdown("""
    <style>
    /* Make body truly full height with no scroll */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 55%, #24243e 100%) !important;
        overflow: hidden !important;
    }
    /* Animated background orbs */
    .tp-orb {
        position: fixed; border-radius: 50%;
        filter: blur(72px); opacity: 0.4; z-index: 0; pointer-events: none;
    }
    .tp-orb-1 {
        width: 520px; height: 520px; background: #6366f1;
        top: -160px; left: -120px;
        animation: orbFloat1 9s ease-in-out infinite;
    }
    .tp-orb-2 {
        width: 420px; height: 420px; background: #8b5cf6;
        bottom: -120px; right: -80px;
        animation: orbFloat2 11s ease-in-out infinite;
    }
    .tp-orb-3 {
        width: 280px; height: 280px; background: #06b6d4;
        top: 45%; left: 55%;
        animation: orbFloat3 13s ease-in-out infinite;
    }
    @keyframes orbFloat1 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(35px,-25px)} }
    @keyframes orbFloat2 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-25px,35px)} }
    @keyframes orbFloat3 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(25px,20px)} }

    /* Center wrapper */
    .tp-login-wrapper {
        position: fixed; inset: 0; z-index: 1;
        display: flex; align-items: center; justify-content: center;
        padding: 20px;
    }
    /* Card */
    .tp-login-card {
        width: 100%; max-width: 420px;
        background: rgba(255,255,255,0.08);
        backdrop-filter: blur(28px);
        -webkit-backdrop-filter: blur(28px);
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 24px;
        padding: 44px 40px;
        box-shadow: 0 32px 72px rgba(0,0,0,0.55);
        position: relative; z-index: 2;
    }
    /* Override Streamlit inputs for dark login card */
    .tp-login-card .stTextInput > div > div > input {
        background: rgba(255,255,255,0.09) !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
    }
    .tp-login-card .stTextInput > div > div > input::placeholder { color: rgba(255,255,255,0.4) !important; }
    .tp-login-card .stTextInput > div > div > input:focus {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.25) !important;
        background: rgba(255,255,255,0.13) !important;
    }
    .tp-login-card label, .tp-login-card .stSelectbox label {
        color: rgba(255,255,255,0.75) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
    }
    .tp-login-card .stSelectbox > div > div {
        background: rgba(255,255,255,0.09) !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        color: white !important;
        border-radius: 12px !important;
    }
    /* Primary button inside card */
    .tp-login-card .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important; font-weight: 600 !important;
        height: 50px !important; width: 100% !important;
        font-size: 15px !important; border-radius: 12px !important;
        box-shadow: 0 4px 16px rgba(99,102,241,0.4) !important;
        margin-top: 8px !important;
    }
    .tp-login-card .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 28px rgba(99,102,241,0.55) !important;
    }
    </style>

    <!-- Background orbs -->
    <div class="tp-orb tp-orb-1"></div>
    <div class="tp-orb tp-orb-2"></div>
    <div class="tp-orb tp-orb-3"></div>
    """, unsafe_allow_html=True)

    # The actual card — use a centered column trick
    _, card_col, _ = st.columns([1, 1.4, 1])

    with card_col:
        st.markdown("""
        <div class="tp-login-card">
        <div style="text-align:center;margin-bottom:28px">
          <svg width="52" height="52" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M24 3L7 9.5v13.8C7 33.2 14.6 43 24 45.5 33.4 43 41 33.2 41 23.3V9.5L24 3z" fill="#6366f1"/>
            <path d="M17 24l5 5 9-10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div style="color:white;font-size:26px;font-weight:700;margin-top:10px;letter-spacing:-0.3px">TrueTestAuth</div>
          <div style="color:rgba(255,255,255,0.42);font-size:12.5px;margin-top:5px;line-height:1.5">
            Behavioural exam integrity<br>powered by keystroke dynamics
          </div>
        </div>
        </div>
        """, unsafe_allow_html=True)

        if not st.session_state.get('login_role'):
            role_callback()
        else:
            form_callback()


def render_faculty_layout(content_fn):
    """Wraps any faculty page content with the sidebar + main area layout."""
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background: #f8fafc !important;
    }
    /* Left column = sidebar */
    div[data-testid="stHorizontalBlock"] > div:first-child {
        background: #0f172a !important;
        min-height: 100vh !important;
        padding: 0 !important;
        position: sticky !important;
        top: 0 !important;
    }
    /* Sidebar buttons */
    div[data-testid="stHorizontalBlock"] > div:first-child .stButton > button {
        background: transparent !important;
        color: #94a3b8 !important;
        text-align: left !important;
        width: 100% !important;
        height: 44px !important;
        border-radius: 8px !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        border: none !important;
        padding: 0 12px !important;
        justify-content: flex-start !important;
    }
    div[data-testid="stHorizontalBlock"] > div:first-child .stButton > button:hover {
        background: rgba(255,255,255,0.07) !important;
        color: white !important;
    }
    /* Right column = content area */
    div[data-testid="stHorizontalBlock"] > div:last-child {
        background: #f8fafc !important;
        padding: 28px 32px !important;
        min-height: 100vh !important;
        overflow-y: auto !important;
    }
    </style>
    """, unsafe_allow_html=True)

    sidebar_col, content_col = st.columns([1, 4.5])

    with sidebar_col:
        st.markdown("""
        <div style="padding:24px 16px 20px;border-bottom:1px solid rgba(255,255,255,0.08)">
          <div style="display:flex;align-items:center;gap:8px">
            <svg width="26" height="26" viewBox="0 0 48 48" fill="none">
              <path d="M24 3L7 9.5v13.8C7 33.2 14.6 43 24 45.5 33.4 43 41 33.2 41 23.3V9.5L24 3z" fill="#6366f1"/>
              <path d="M17 24l5 5 9-10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span style="color:white;font-weight:600;font-size:15px">TrueTestAuth</span>
          </div>
          <div style="margin-top:14px">
            <div style="color:white;font-size:13px;font-weight:500">{name}</div>
            <div style="background:rgba(99,102,241,0.25);color:#a5b4fc;font-size:11px;
              padding:2px 8px;border-radius:99px;display:inline-block;margin-top:4px">{course}</div>
          </div>
        </div>
        """.format(
            name=st.session_state.get('full_name','Faculty'),
            course=st.session_state.get('course_name','')
        ), unsafe_allow_html=True)

        st.markdown("<div style='padding:8px 8px'>", unsafe_allow_html=True)

        nav = [('overview','📊  Overview'), ('exams','📝  Exams'),
               ('lab','🧪  Code Lab'), ('reports','📋  Reports')]
        for page_id, label in nav:
            is_active = st.session_state.get('page') == page_id
            if is_active:
                st.markdown(f"""
                <div style="background:rgba(99,102,241,0.18);border-left:3px solid #6366f1;
                  color:#a5b4fc;padding:10px 12px;border-radius:0 8px 8px 0;
                  font-size:14px;font-weight:500;margin-bottom:2px">{label}</div>
                """, unsafe_allow_html=True)
            else:
                if st.button(label, key=f"nav_{page_id}", use_container_width=True):
                    st.session_state.page = page_id
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
        if st.button("🚪  Logout", key="faculty_logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    with content_col:
        content_fn()


def render_student_navbar():
    """Fixed top navbar for student pages."""
    first_name = st.session_state.get('full_name','Student').split()[0]
    initials = ''.join(w[0].upper() for w in st.session_state.get('full_name','S').split()[:2])
    hour = datetime.now().hour
    greeting = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'
    enroll = st.session_state.get('enrollment_no','')

    st.markdown(f"""
    <div style="
      background:rgba(12,18,32,0.97);
      padding:14px 36px;
      border-bottom:1px solid rgba(255,255,255,0.07);
      box-shadow:0 1px 16px rgba(0,0,0,0.35);
      display:flex; align-items:center; justify-content:space-between;
      position:sticky; top:0; z-index:100;
      backdrop-filter:blur(12px);
    ">
      <div style="display:flex;align-items:center;gap:12px">
        <svg width="28" height="28" viewBox="0 0 48 48" fill="none">
          <path d="M24 3L7 9.5v13.8C7 33.2 14.6 43 24 45.5 33.4 43 41 33.2 41 23.3V9.5L24 3z" fill="#5b5ef4"/>
          <path d="M17 24l5 5 9-10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="font-weight:800;font-size:16px;color:white;letter-spacing:-0.02em">TrueTestAuth</span>
      </div>
      <div style="color:#64748b;font-size:13.5px">
        {greeting}, <span style="color:white;font-weight:600">{first_name}</span>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        {f'<span style="background:rgba(91,94,244,0.15);color:#a5b4fc;font-size:11px;font-weight:700;padding:4px 12px;border-radius:99px;border:1px solid rgba(91,94,244,0.25)">{enroll}</span>' if enroll else ''}
        <div style="width:36px;height:36px;border-radius:50%;
          background:linear-gradient(135deg,#5b5ef4,#7c3aed);
          color:white;font-weight:700;font-size:13px;display:flex;align-items:center;
          justify-content:center;box-shadow:0 2px 8px rgba(91,94,244,0.35)">{initials}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_student_layout(content_fn):
    """Navbar + content wrapper for all student pages."""
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #0c1220 !important; }
    div[data-testid="stVerticalBlock"] > div { padding: 0 !important; }
    </style>
    """, unsafe_allow_html=True)
    render_student_navbar()
    _, content, _ = st.columns([0.05, 11, 0.05])
    with content:
        st.markdown("<div style='padding:32px 0'>", unsafe_allow_html=True)
        content_fn()
        st.markdown("</div>", unsafe_allow_html=True)


def metric_card(value, label, icon, color="#5b5ef4", bg="#eef2ff"):
    """Render a single metric card."""
    return f"""
    <div style="background:white;border-radius:16px;padding:22px 24px;
      border:1px solid #edf2f7;box-shadow:0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04);
      height:100%;position:relative;overflow:hidden;
      transition:box-shadow 0.22s ease,transform 0.22s ease;">
      <div style="position:absolute;top:0;left:0;right:0;height:3px;
        background:linear-gradient(90deg,{color},{color}aa);opacity:0.7"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
        <div style="font-size:11px;color:#64748b;font-weight:700;text-transform:uppercase;
          letter-spacing:0.07em">{label}</div>
        <div style="width:38px;height:38px;border-radius:12px;background:{bg};
          display:flex;align-items:center;justify-content:center;font-size:18px;
          box-shadow:0 2px 6px rgba(0,0,0,0.06)">{icon}</div>
      </div>
      <div style="font-size:32px;font-weight:800;color:#0f172a;letter-spacing:-0.03em;
        line-height:1">{value}</div>
    </div>
    """


def course_card(faculty_name, course_name, initials, exam_count, lab_count, color="#5b5ef4"):
    """Render a course card for student dashboard."""
    return f"""
    <div style="background:rgba(255,255,255,0.05);border-radius:20px;padding:0;
      border:1px solid rgba(255,255,255,0.08);
      box-shadow:0 2px 10px rgba(0,0,0,0.2);
      overflow:hidden;cursor:pointer;height:100%;
      transition:box-shadow 0.22s ease,transform 0.22s ease,border-color 0.22s ease;">
      <div style="height:3px;background:linear-gradient(90deg,{color},{color}88)"></div>
      <div style="padding:22px">
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px">
          <div style="width:46px;height:46px;border-radius:14px;
            background:linear-gradient(135deg,{color},{color}bb);
            color:white;font-weight:800;font-size:17px;
            display:flex;align-items:center;justify-content:center;
            box-shadow:0 4px 12px rgba(0,0,0,0.25)">{initials}</div>
          <div>
            <div style="font-weight:700;font-size:15px;color:white;letter-spacing:-0.01em">{faculty_name}</div>
            <div style="font-size:12.5px;color:#64748b;margin-top:2px;font-weight:500">{course_name}</div>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <span style="background:rgba(91,94,244,0.15);color:#a5b4fc;font-size:11px;font-weight:700;
            padding:4px 12px;border-radius:99px;border:1px solid rgba(91,94,244,0.25)">📝 {exam_count} Exams</span>
          <span style="background:rgba(34,197,94,0.12);color:#4ade80;font-size:11px;font-weight:700;
            padding:4px 12px;border-radius:99px;border:1px solid rgba(34,197,94,0.2)">🧪 {lab_count} Labs</span>
        </div>
      </div>
    </div>
    """


def section_header(title, subtitle="", action_label="", action_key=""):
    """Consistent section header above content blocks."""
    sub_html = f'<p style="font-size:13.5px;color:#64748b;margin:4px 0 0;line-height:1.5">{subtitle}</p>' if subtitle else ''
    st.markdown(f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;
      margin-bottom:18px;margin-top:10px;padding-bottom:14px;
      border-bottom:1px solid rgba(255,255,255,0.06)">
      <div>
        <h2 style="font-size:19px;font-weight:800;color:white;margin:0;letter-spacing:-0.02em">{title}</h2>
        {sub_html}
      </div>
    </div>
    """, unsafe_allow_html=True)


def status_badge(text, status):
    """status: verified | warning | flagged | active | ended | easy | medium | hard"""
    colors = {
        'verified': ('rgba(34,197,94,0.15)', '#4ade80', 'rgba(34,197,94,0.25)'),
        'warning':  ('rgba(245,158,11,0.15)', '#fbbf24', 'rgba(245,158,11,0.25)'),
        'flagged':  ('rgba(239,68,68,0.15)', '#f87171', 'rgba(239,68,68,0.25)'),
        'active':   ('rgba(34,197,94,0.15)', '#4ade80', 'rgba(34,197,94,0.25)'),
        'ended':    ('rgba(100,116,139,0.15)', '#94a3b8', 'rgba(100,116,139,0.2)'),
        'easy':     ('rgba(34,197,94,0.15)', '#4ade80', 'rgba(34,197,94,0.2)'),
        'medium':   ('rgba(245,158,11,0.15)', '#fbbf24', 'rgba(245,158,11,0.2)'),
        'hard':     ('rgba(239,68,68,0.15)', '#f87171', 'rgba(239,68,68,0.2)'),
    }
    bg, fg, border = colors.get(status.lower(), ('rgba(100,116,139,0.15)', '#94a3b8', 'rgba(100,116,139,0.2)'))
    return f"""<span style="background:{bg};color:{fg};border:1px solid {border};
      font-size:11.5px;font-weight:700;padding:4px 12px;border-radius:99px;
      display:inline-block;letter-spacing:0.04em">{text}</span>"""


def render_metrics_row(metrics):
    """metrics = list of (value, label, icon, color, bg) tuples."""
    cols = st.columns(len(metrics))
    for col, (value, label, icon, color, bg) in zip(cols, metrics):
        with col:
            st.markdown(metric_card(value, label, icon, color, bg),
              unsafe_allow_html=True)


def render_exam_portal_layout(header_data, q_fn, auth_fn):
    st.markdown("""
    <style>
    /* Exam portal overrides */
    [data-testid="stAppViewContainer"] { background: #0c1220 !important; overflow: hidden !important; }
    .main .block-container { padding: 0 !important; height: 100vh !important; overflow: hidden !important; }
    /* Left question panel scrolls, right auth panel fixed */
    .exam-questions-panel {
        height: calc(100vh - 64px); overflow-y: auto; padding: 26px 30px;
        background: #0c1220;
        scrollbar-width: thin; scrollbar-color: rgba(148,163,184,0.2) transparent;
    }
    .exam-auth-panel {
        height: calc(100vh - 64px); overflow-y: auto; padding: 22px 20px;
        background: rgba(255,255,255,0.03);
        border-left: 1px solid rgba(255,255,255,0.06);
    }
    /* Question card */
    .exam-q-card {
        background: rgba(255,255,255,0.05); border-radius: 16px; padding: 22px 24px;
        border: 1px solid rgba(255,255,255,0.08); margin-bottom: 16px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: border-color 0.2s;
    }
    .exam-q-card:hover { border-color: rgba(91,94,244,0.3); }
    /* Answer textarea override for exam */
    .exam-questions-panel .stTextArea > div > div > textarea {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important; font-size: 14px !important;
        line-height: 1.7 !important; color: white !important;
        min-height: 120px !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    .exam-questions-panel .stTextArea > div > div > textarea:focus {
        border-color: rgba(91,94,244,0.6) !important;
        box-shadow: 0 0 0 3px rgba(91,94,244,0.15) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Sticky exam header
    st.markdown(f"""
    <div style="background:rgba(15,23,42,0.96);padding:14px 28px;display:flex;
      align-items:center;justify-content:space-between;
      border-bottom:1px solid rgba(255,255,255,0.07);
      backdrop-filter:blur(12px);
      box-shadow:0 2px 16px rgba(0,0,0,0.4)">
      <div style="color:white;font-weight:700;font-size:15px;letter-spacing:-0.01em">{header_data.get('title','Exam')}</div>
      <div id="exam-countdown" style="font-family:'JetBrains Mono',monospace;
        font-size:22px;font-weight:700;color:#a5b4fc;letter-spacing:0.05em">{header_data.get('timer', '00:00')}</div>
      <div style="display:flex;align-items:center;gap:8px">
        <div id="auth-dot" style="width:9px;height:9px;border-radius:50%;
          background:{header_data.get('auth_color', '#22c55e')};
          box-shadow:0 0 8px {header_data.get('auth_color','#22c55e')}88;
          animation:authpulse 2s infinite"></div>
        <span style="color:#64748b;font-size:13px;font-weight:500">Monitoring active</span>
      </div>
    </div>
    <style>
    @keyframes authpulse {{0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:0.6;transform:scale(1.3)}}}}
    </style>
    """, unsafe_allow_html=True)

    # Split layout: questions (60%) + auth panel (40%)
    q_col, auth_col = st.columns([3, 2])

    with q_col:
        st.markdown('<div class="exam-questions-panel">', unsafe_allow_html=True)
        q_fn()
        st.markdown('</div>', unsafe_allow_html=True)

    with auth_col:
        st.markdown('<div class="exam-auth-panel">', unsafe_allow_html=True)
        auth_fn()
        st.markdown('</div>', unsafe_allow_html=True)


def render_step_indicator(current_step, steps):
    """Render step progress indicator inside registration card."""
    dots = ""
    for i, label in enumerate(steps, 1):
        if i < current_step:
            dot_style = "background:#5b5ef4;color:white;border:2px solid #5b5ef4;box-shadow:0 0 0 4px rgba(91,94,244,0.2)"
            label_style = "color:#a5b4fc;font-weight:600"
            num = "✓"
        elif i == current_step:
            dot_style = "background:rgba(91,94,244,0.15);color:#818cf8;border:2px solid #818cf8;box-shadow:0 0 0 4px rgba(91,94,244,0.15)"
            label_style = "color:white;font-weight:700"
            num = str(i)
        else:
            dot_style = "background:rgba(255,255,255,0.04);color:#475569;border:2px solid rgba(255,255,255,0.1)"
            label_style = "color:#475569;font-weight:500"
            num = str(i)

        dots += f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;flex:0 0 auto">
          <div style="{dot_style};width:32px;height:32px;border-radius:50%;
            display:flex;align-items:center;justify-content:center;
            font-size:12px;font-weight:700;transition:all 0.3s;z-index:1">{num}</div>
          <span style="{label_style};font-size:11px;white-space:nowrap">{label}</span>
        </div>
        """
        if i < len(steps):
            line_bg = "#5b5ef4" if i < current_step else "rgba(255,255,255,0.08)"
            dots += f"<div style='flex:1;height:2px;background:{line_bg};margin-top:15px;transition:background 0.4s;min-width:20px'></div>"

    st.markdown(f"""
    <div style="display:flex;align-items:flex-start;gap:4px;margin-bottom:28px;padding:0 4px">
      {dots}
    </div>
    """, unsafe_allow_html=True)


def spacer(h=16):
    """Add vertical space without blank lines."""
    st.markdown(f"<div style='height:{h}px'></div>", unsafe_allow_html=True)


def divider():
    """Styled divider line."""
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:20px 0'>",
      unsafe_allow_html=True)
