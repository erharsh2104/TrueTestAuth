"""TrueTestAuth — Behavioural-auth exam + code-lab proctoring (Streamlit).

Architecture:
  • Login flow (animated gradient, role chooser, login/register forms)
  • Faculty dashboard: Overview · Exam Mgmt · Code Lab · Reports · Settings
  • Student dashboard: Courses → Course detail → Exam/Lab portals
  • Behavioural auth: declared Streamlit component (frontend/index.html)
      uses Streamlit.setComponentValue + postMessage so that sandboxed
      iframes can talk to Python without being blocked by the
      `allow-top-navigation` sandbox restriction.
  • Copy-paste blocking: preventDefault inside the same component.
  • Compilation: CppCompiler (Judge0 → Piston → local g++ fallback).
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import date, datetime, time as dtime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from compiler import CppCompiler, grade_submission
from data_manager import DEFAULT_STARTER_CODE, DataManager, exam_state, exam_window
from ml_model import AUTH_THRESHOLD, DEFAULT_MODEL_DIR, BehavioralAuthModel


# ── Constants ────────────────────────────────────────────────────────────────
PHRASE: str = "the quick brown fox jumps"
ENROLL_TARGET: int = 10
LOW_CONFIDENCE: float = 0.45
AMBER_CONFIDENCE: float = 0.65

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH: str = DEFAULT_MODEL_DIR
FRONTEND_DIR: str = os.path.join(ROOT_DIR, "frontend")


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TrueTestAuth",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── Global CSS ───────────────────────────────────────────────────────────────
GLOBAL_CSS: str = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ═══ Design tokens ═══════════════════════════════════════════════════════ */
:root {
    --bg: #0a0f1e;
    --bg-2: #0d1426;
    --surface: #111a30;
    --surface-2: #162039;
    --surface-3: #1c2845;
    --border: rgba(148,163,184,0.14);
    --border-strong: rgba(148,163,184,0.26);
    --text: #e8ecf6;
    --text-2: #aab4cb;
    --muted: #7c879f;
    --brand: #6366f1;
    --brand-2: #8b5cf6;
    --brand-soft: rgba(99,102,241,0.14);
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --cyan: #06b6d4;
    --r-sm: 8px; --r-md: 12px; --r-lg: 16px; --r-xl: 22px;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
    --shadow-md: 0 8px 24px rgba(0,0,0,0.35);
    --shadow-brand: 0 8px 22px rgba(99,102,241,0.32);
}

/* ═══ Base / Streamlit chrome ═════════════════════════════════════════════ */
html, body, .stApp, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: var(--text);
}
.stApp {
    background:
        radial-gradient(900px circle at 85% -10%, rgba(99,102,241,0.13), transparent 55%),
        radial-gradient(700px circle at -5% 25%, rgba(139,92,246,0.08), transparent 55%),
        var(--bg) !important;
}
#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stHeader"], section[data-testid="stSidebar"] { display: none !important; }
.main .block-container, div.block-container, [data-testid="stAppViewBlockContainer"] {
    padding: 0 !important; max-width: 100% !important; margin: 0 !important;
}
h1, h2, h3, h4 { font-family: 'Inter', sans-serif !important; letter-spacing: -0.02em; color: var(--text); }
p, li, label, span { font-family: 'Inter', sans-serif; }
a { color: #a5b4fc; text-decoration: none; }
a:hover { color: #c7d2fe; }
hr { border: 0; border-top: 1px solid var(--border); margin: 18px 0; }
code { font-family: 'JetBrains Mono', monospace !important; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(148,163,184,0.25); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,0.45); }

/* ═══ Buttons ═════════════════════════════════════════════════════════════ */
.stButton > button, .stDownloadButton > button, [data-testid^="stBaseButton"] {
    border-radius: var(--r-md) !important;
    font-weight: 600 !important; font-size: 13.5px !important; letter-spacing: 0.005em;
    min-height: 42px; transition: transform .16s ease, box-shadow .16s ease, background .16s ease, border-color .16s ease !important;
}
button[data-testid="stBaseButton-secondary"], .stDownloadButton > button {
    background: var(--surface-2) !important; color: var(--text) !important;
    border: 1px solid var(--border-strong) !important;
}
button[data-testid="stBaseButton-secondary"]:hover, .stDownloadButton > button:hover {
    border-color: var(--brand) !important; background: var(--surface-3) !important; transform: translateY(-1px);
}
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"],
button[data-testid="stBaseButton-secondaryFormSubmit"] {
    background: linear-gradient(135deg, var(--brand) 0%, var(--brand-2) 100%) !important;
    color: #fff !important; border: 0 !important; box-shadow: var(--shadow-brand);
}
button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    transform: translateY(-2px); box-shadow: 0 14px 30px rgba(99,102,241,0.45);
}
button:focus-visible { outline: 2px solid #a5b4fc !important; outline-offset: 2px; }

/* ═══ Inputs / forms ══════════════════════════════════════════════════════ */
[data-testid="stForm"] { border: 0 !important; padding: 0 !important; background: transparent !important; }
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input, .stTimeInput input,
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] {
    background: var(--surface-2) !important; border-color: var(--border-strong) !important;
    border-radius: var(--r-md) !important; color: var(--text) !important;
}
.stTextInput input, .stTextArea textarea, .stNumberInput input { padding: 11px 14px !important; font-size: 14px !important; }
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    border-color: var(--brand) !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.2) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--muted) !important; }
label, [data-testid="stWidgetLabel"] p { color: var(--text-2) !important; font-size: 13px !important; font-weight: 500 !important; }
[data-testid="stFileUploaderDropzone"] {
    background: var(--surface) !important; border: 1.5px dashed var(--border-strong) !important; border-radius: var(--r-lg) !important;
}
.stSlider [role="slider"] { background: var(--brand) !important; }

/* ═══ Tabs / expanders / tables / alerts ══════════════════════════════════ */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-md);
    padding: 4px; gap: 4px; width: fit-content;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 9px; padding: 8px 16px; height: auto; color: var(--text-2); font-weight: 500; font-size: 13.5px; background: transparent;
}
[data-testid="stTabs"] [aria-selected="true"] { background: var(--brand-soft) !important; color: #c7d2fe !important; font-weight: 600; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] { display: none; }
[data-testid="stTabs"] [data-baseweb="tab-panel"] { padding-top: 22px; }
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important; border-radius: var(--r-lg) !important;
    background: var(--surface) !important; overflow: hidden;
}
[data-testid="stExpander"] summary:hover { background: var(--surface-2); }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: var(--r-lg); overflow: hidden; }
[data-testid="stAlert"] { border-radius: var(--r-md) !important; border: 1px solid var(--border) !important; }
[data-testid="stProgress"] > div > div > div { background: linear-gradient(90deg, var(--brand), var(--brand-2)) !important; border-radius: 99px; }
.stSpinner > div { border-top-color: var(--brand) !important; }

/* Real bordered containers = cards */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { border-color: var(--border); }
div[data-testid="stVerticalBlockBorderWrapper"][class*="st-emotion-cache"] { border-radius: var(--r-lg); }
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface); border: 1px solid var(--border) !important; border-radius: var(--r-lg) !important;
    padding: 6px 8px; box-shadow: var(--shadow-sm);
}
[data-testid="stForm"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"] [data-testid="stVerticalBlockBorderWrapper"] { background: transparent; box-shadow: none; }

/* ═══ Page chrome: titles, headers ════════════════════════════════════════ */
.tp-title, .tp-title-dark { font-size: 28px; font-weight: 800; color: var(--text); margin: 0 0 6px; letter-spacing: -0.03em; }
.tp-sub, .tp-sub-dark { color: var(--muted); font-size: 14px; margin: 0 0 24px; line-height: 1.55; }
.page-header { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 26px; }
.page-header .icon-badge {
    width: 50px; height: 50px; border-radius: 15px; flex-shrink: 0; font-size: 23px;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, var(--brand), var(--brand-2)); box-shadow: var(--shadow-brand);
}
.page-header .ph-text h1 { margin: 2px 0 4px !important; padding: 0 !important; font-size: 26px !important; }
.page-header .ph-text p { margin: 0 !important; }
.card-eyebrow { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 700; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 14px; }
.card-eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--brand); }

/* ═══ HTML cards (self-contained markup) ══════════════════════════════════ */
.tp-card, .tp-card-dark {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
    padding: 18px 20px; margin-bottom: 14px; box-shadow: var(--shadow-sm); color: var(--text);
    transition: border-color .2s ease, box-shadow .2s ease;
}
.tp-card:hover, .tp-card-dark:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 26px; }
.metric-card, .metric-card-dark {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
    padding: 20px; position: relative; overflow: hidden; box-shadow: var(--shadow-sm); color: var(--text);
    transition: transform .2s ease, border-color .2s ease;
}
.metric-card:hover, .metric-card-dark:hover { transform: translateY(-2px); border-color: var(--border-strong); }
.metric-card::before, .metric-card-dark::before {
    content: ''; position: absolute; left: 0; right: 0; top: 0; height: 2px;
    background: linear-gradient(90deg, var(--brand), var(--brand-2)); opacity: .0; transition: opacity .2s;
}
.metric-card:hover::before, .metric-card-dark:hover::before { opacity: 1; }
.metric-card .m-top, .metric-card-dark .m-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.metric-card .label, .metric-card-dark .label { font-size: 11.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .07em; font-weight: 600; }
.metric-card .value, .metric-card-dark .value { font-size: 32px; font-weight: 800; color: var(--text); letter-spacing: -0.03em; line-height: 1; }
.metric-card .delta, .metric-card-dark .delta { font-size: 12px; color: #4ade80; margin-top: 8px; font-weight: 600; }
.m-icon { width: 36px; height: 36px; border-radius: 11px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.accent-indigo .m-icon { background: rgba(129,140,248,0.16); color: #a5b4fc; }
.accent-green  .m-icon { background: rgba(74,222,128,0.14);  color: #4ade80; }
.accent-amber  .m-icon { background: rgba(251,191,36,0.14);  color: #fbbf24; }
.accent-red    .m-icon { background: rgba(248,113,113,0.14); color: #f87171; }
.accent-cyan   .m-icon { background: rgba(34,211,238,0.14);  color: #67e8f9; }

.feed-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 1px solid var(--border); }
.feed-row:last-child { border-bottom: 0; }
.feed-row .fr-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.feed-row .fr-dot { width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 13px; }

.empty-pro { text-align: center; padding: 40px 24px; border: 1.5px dashed var(--border-strong); border-radius: var(--r-xl); background: rgba(99,102,241,0.04); }
.empty-pro .ep-icon { width: 58px; height: 58px; margin: 0 auto 14px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 25px; background: var(--brand-soft); }
.empty-pro h4 { margin: 0 0 5px; font-size: 15px; font-weight: 700; color: var(--text); }
.empty-pro p { margin: 0 auto; font-size: 12.5px; color: var(--muted); line-height: 1.6; max-width: 360px; }

.ring-wrap { display: flex; align-items: center; gap: 18px; justify-content: center; }
.ring { width: 92px; height: 92px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: conic-gradient(var(--rc, #6366f1) calc(var(--rp, 0) * 1%), rgba(148,163,184,0.16) 0); }
.ring .ring-inner { width: 70px; height: 70px; border-radius: 50%; background: var(--rb, var(--surface)); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; color: var(--text); }

/* ═══ Badges / status ═════════════════════════════════════════════════════ */
.badge { padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: 700; display: inline-block; letter-spacing: .05em; white-space: nowrap; }
.badge-verified, .badge-active, .badge-easy   { background: rgba(34,197,94,0.14);  color: #4ade80; border: 1px solid rgba(34,197,94,0.28); }
.badge-warning, .badge-medium                 { background: rgba(245,158,11,0.14); color: #fbbf24; border: 1px solid rgba(245,158,11,0.28); }
.badge-flagged, .badge-hard                   { background: rgba(239,68,68,0.14);  color: #f87171; border: 1px solid rgba(239,68,68,0.28); }
.badge-upcoming                               { background: var(--brand-soft);     color: #a5b4fc; border: 1px solid rgba(99,102,241,0.3); }
.badge-ended                                  { background: rgba(100,116,139,0.16); color: #94a3b8; border: 1px solid rgba(100,116,139,0.25); }
@keyframes auth-pulse { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.3); opacity: .7; } }
.auth-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; animation: auth-pulse 2s ease-in-out infinite; }
.auth-dot.green { background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,.55); }
.auth-dot.amber { background: #f59e0b; box-shadow: 0 0 8px rgba(245,158,11,.55); }
.auth-dot.red   { background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,.55); }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, var(--brand), var(--brand-2)); color: #fff; font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center; font-size: 13px; box-shadow: 0 2px 8px rgba(99,102,241,.35); flex-shrink: 0; }

/* ═══ Login ═══════════════════════════════════════════════════════════════ */
.login-bg { position: fixed; inset: 0; z-index: -2; background: linear-gradient(150deg, #060b19 0%, #0b1330 45%, #120a2e 80%, #060b19 100%); }
.login-bg::after { content: ''; position: fixed; inset: 0; z-index: -1;
    background-image: linear-gradient(rgba(99,102,241,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.045) 1px, transparent 1px);
    background-size: 52px 52px; mask-image: radial-gradient(ellipse at 50% 40%, #000 30%, transparent 75%); }
.orb { position: fixed; border-radius: 50%; filter: blur(95px); opacity: .32; z-index: -1; }
.orb-1 { width: 520px; height: 520px; background: radial-gradient(circle, #6366f1, #3730a3); top: -170px; left: -140px; animation: float1 16s ease-in-out infinite; }
.orb-2 { width: 420px; height: 420px; background: radial-gradient(circle, #8b5cf6, #6d28d9); bottom: -150px; right: -120px; animation: float2 20s ease-in-out infinite; }
.orb-3 { width: 320px; height: 320px; background: radial-gradient(circle, #06b6d4, #0e7490); top: 48%; right: 24%; animation: float3 26s ease-in-out infinite; }
@keyframes float1 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(55px,-35px) scale(1.06); } }
@keyframes float2 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-45px,45px) scale(.94); } }
@keyframes float3 { 0%,100% { transform: translate(0,0); } 50% { transform: translate(38px,28px); } }

.st-key-login_card {
    background: rgba(17,26,48,0.72); backdrop-filter: blur(28px); -webkit-backdrop-filter: blur(28px);
    border: 1px solid rgba(255,255,255,0.10); border-radius: 26px; padding: 36px 38px 30px;
    box-shadow: 0 40px 80px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.07); margin: 56px 0 40px;
}
.st-key-login_card h3 { font-size: 19px !important; font-weight: 700; margin: 4px 0 16px !important; }
.st-key-login_card .stButton > button, .st-key-login_card button[data-testid^="stBaseButton"] { min-height: 48px; width: 100%; }
.login-logo { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.login-logo svg { width: 36px; height: 36px; color: #818cf8; }
.login-logo span { color: #fff; font-size: 25px; font-weight: 800; letter-spacing: -0.03em; }
.login-tagline { color: var(--muted); font-size: 13px; margin-bottom: 22px; line-height: 1.5; }
.role-back { color: var(--muted); font-size: 13px; text-align: center; margin-top: 16px; }
.tiny-help { color: var(--muted); font-size: 12px; text-align: center; margin-top: 14px; }

.login-hero { padding: 84px 24px 40px 12px; max-width: 480px; margin-left: auto; }
.login-hero .eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px;
    background: var(--brand-soft); border: 1px solid rgba(99,102,241,0.3); color: #a5b4fc; font-size: 12px; font-weight: 600; margin-bottom: 22px; }
.login-hero h1 { color: #fff; font-size: 38px; font-weight: 800; line-height: 1.15; letter-spacing: -0.03em; margin: 0 0 16px; padding: 0; }
.login-hero h1 .grad { background: linear-gradient(135deg, #818cf8, #c084fc); -webkit-background-clip: text; background-clip: text; color: transparent; }
.login-hero p.lead { color: var(--text-2); font-size: 15px; line-height: 1.65; margin: 0 0 32px; }
.login-hero .feat-row { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 20px; }
.login-hero .feat-icon { width: 42px; height: 42px; border-radius: 12px; flex-shrink: 0; background: rgba(255,255,255,0.05); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 18px; }
.login-hero .feat-text b { color: #fff; font-size: 14px; display: block; margin-bottom: 2px; font-weight: 700; }
.login-hero .feat-text span { color: var(--muted); font-size: 13px; line-height: 1.55; display: block; }
.login-hero .stat-strip { display: flex; gap: 34px; margin-top: 30px; padding-top: 24px; border-top: 1px solid var(--border); }
.login-hero .stat b { display: block; color: #fff; font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }
.login-hero .stat span { color: var(--muted); font-size: 10.5px; text-transform: uppercase; letter-spacing: .07em; }
@media (max-width: 900px) { .login-hero { display: none; } }

/* ═══ Faculty shell ═══════════════════════════════════════════════════════ */
div[data-testid="stColumn"]:has(.st-key-fac_sidebar) { background: var(--bg-2); border-right: 1px solid var(--border); min-height: 100vh; }
.st-key-fac_sidebar { padding: 22px 14px 24px; position: sticky; top: 0; }
.st-key-fac_content { padding: 32px 44px 60px; }
.fs-brand { display: flex; align-items: center; gap: 10px; padding: 0 6px; }
.fs-brand svg { width: 26px; height: 26px; color: #818cf8; }
.fs-brand span { color: #fff; font-weight: 800; font-size: 17px; letter-spacing: -0.02em; }
.fs-user { display: flex; align-items: center; gap: 11px; margin: 18px 0 4px; padding: 12px; background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: var(--r-md); }
.fs-user .side-avatar { width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0; background: linear-gradient(135deg, var(--brand), var(--brand-2)); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 13px; }
.fs-user .who { color: var(--text); font-size: 13.5px; font-weight: 600; line-height: 1.25; }
.fs-user .course-pill { color: #a5b4fc; font-size: 11px; margin-top: 2px; font-weight: 500; }
.nav-label { font-size: 10.5px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); font-weight: 700; margin: 18px 0 8px 8px; }
.st-key-fac_sidebar .stButton > button { width: 100%; justify-content: flex-start !important; text-align: left; padding: 10px 14px !important; min-height: 42px; }
.st-key-fac_sidebar button[data-testid="stBaseButton-secondary"] { background: transparent !important; border: 1px solid transparent !important; color: var(--text-2) !important; }
.st-key-fac_sidebar button[data-testid="stBaseButton-secondary"]:hover { background: rgba(255,255,255,0.05) !important; color: #fff !important; transform: none; }
.st-key-fac_sidebar button[data-testid="stBaseButton-primary"] { background: var(--brand-soft) !important; color: #c7d2fe !important; border: 1px solid rgba(99,102,241,0.35) !important; box-shadow: none; }
.st-key-fac_sidebar button[data-testid="stBaseButton-primary"]:hover { transform: none; box-shadow: none; }
.st-key-fac_logout button { color: #fca5a5 !important; background: rgba(239,68,68,0.08) !important; border: 1px solid rgba(239,68,68,0.2) !important; justify-content: center !important; }
.st-key-fac_logout button:hover { background: rgba(239,68,68,0.16) !important; }

/* ═══ Student shell ═══════════════════════════════════════════════════════ */
.course-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
.course-card-dark { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-xl); padding: 22px; box-shadow: var(--shadow-sm); transition: transform .2s, border-color .2s, box-shadow .2s; }
.course-card-dark:hover { transform: translateY(-3px); border-color: rgba(99,102,241,0.4); box-shadow: var(--shadow-md); }
.course-card-dark .head { display: flex; gap: 14px; align-items: center; margin-bottom: 16px; }
.course-card-dark .avatar { width: 46px; height: 46px; font-size: 16px; border-radius: 14px; }
.course-card-dark .name { font-size: 12.5px; color: var(--muted); font-weight: 500; }
.course-card-dark .course { font-size: 16px; font-weight: 700; color: var(--text); margin-top: 2px; letter-spacing: -0.01em; }
.course-card-dark .stats { display: flex; gap: 12px; }
.course-card-dark .stats div { flex: 1; background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: var(--r-md); padding: 10px 12px; color: var(--muted); font-size: 12px; }
.course-card-dark .stats b { display: block; color: var(--text); font-size: 20px; font-weight: 800; }
.st-key-stu_content { padding: 28px 44px 60px; }

/* ═══ Exam / lab ══════════════════════════════════════════════════════════ */
.exam-timer { font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700; color: #c7d2fe; letter-spacing: .04em; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .5; } }
.exam-timer.warning { color: #f87171; animation: pulse 1.1s ease-in-out infinite; }
.qnav-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; }
.qnav-dot { aspect-ratio: 1/1; border-radius: 10px; background: rgba(255,255,255,0.05); color: var(--muted); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }
.qnav-dot.answered { background: rgba(34,197,94,0.14); color: #4ade80; border-color: rgba(34,197,94,0.3); }
.qnav-dot.flagged { background: rgba(239,68,68,0.14); color: #f87171; border-color: rgba(239,68,68,0.3); }
.terminal { background: #0a0e17; color: #3fb950; font-family: 'JetBrains Mono', monospace; font-size: 13px; padding: 16px; border-radius: var(--r-md); border: 1px solid var(--border); white-space: pre-wrap; line-height: 1.65; }
.tc-pass, .tc-fail { padding: 10px 14px; margin: 5px 0; border-radius: 0 var(--r-sm) var(--r-sm) 0; font-size: 13px; }
.tc-pass { background: rgba(34,197,94,0.09); border-left: 3px solid #22c55e; color: #4ade80; }
.tc-fail { background: rgba(239,68,68,0.09); border-left: 3px solid #ef4444; color: #f87171; }
@keyframes pop-in { 0% { transform: scale(.8); opacity: 0; } 70% { transform: scale(1.05); } 100% { transform: scale(1); opacity: 1; } }
.success-icon { animation: pop-in .5s cubic-bezier(.34,1.56,.64,1) forwards; }
.success-card { background: rgba(34,197,94,0.06); border: 1px solid rgba(34,197,94,0.22); border-radius: var(--r-xl); padding: 34px; text-align: center; }
.success-card h2 { color: #4ade80; font-size: 24px; font-weight: 800; margin: 14px 0 6px; }
.success-card p { color: var(--text-2); font-size: 14px; margin: 0; }
.tp-alert { padding: 14px 18px; border-radius: var(--r-md); margin-bottom: 16px; font-size: 13.5px; }
.tp-alert-info { background: var(--brand-soft); border: 1px solid rgba(99,102,241,0.25); color: #a5b4fc; }
.tp-alert-warn { background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.25); color: #fbbf24; }
.tp-alert-danger { background: rgba(239,68,68,0.10); border: 1px solid rgba(239,68,68,0.25); color: #f87171; }
.tp-alert-success { background: rgba(34,197,94,0.10); border: 1px solid rgba(34,197,94,0.25); color: #4ade80; }

/* ═══ Polish ══════════════════════════════════════════════════════════════ */
[data-testid="stMarkdownContainer"] a { text-decoration: none; }
.st-key-fac_content h3, .st-key-stu_content h3 { font-size: 18px !important; font-weight: 700; margin: 30px 0 14px !important; }
.st-key-fac_content h5, .st-key-stu_content h5 { font-size: 15px !important; font-weight: 700; margin: 22px 0 10px !important; color: var(--text-2); }
.tp-title, .tp-title-dark { font-size: 30px; }
.st-key-fac_sidebar button > div, .st-key-fac_sidebar button [data-testid="stMarkdownContainer"] { width: 100%; justify-content: flex-start !important; }
.st-key-fac_sidebar button [data-testid="stMarkdownContainer"] p { text-align: left; }
.st-key-fac_logout button > div { justify-content: center !important; }
.st-key-stu_content .stButton > button[data-testid="stBaseButton-secondary"] { min-height: 38px; }
.metric-grid + div, .metric-grid { margin-bottom: 26px; }
.empty-pro { margin: 4px 0; }

.course-card-dark { margin-bottom: 12px; }
.st-key-ht_expire { position: absolute; left: -9999px; height: 0; overflow: hidden; }
[data-testid="stVerticalBlockBorderWrapper"] .empty-pro { border: 0; background: transparent; padding: 28px 16px; }
.metric-grid + * { margin-top: 4px; }

/* ═══ Responsive ══════════════════════════════════════════════════════════ */
@media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } .st-key-fac_content, .st-key-stu_content { padding: 24px 20px 48px; } }
@media (max-width: 640px) { .metric-grid { grid-template-columns: 1fr; } }
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ── Reusable UI helpers ──────────────────────────────────────────────────────
def _page_header(icon: str, title: str, subtitle: str = "", dark: bool = False) -> None:
    """Render a consistent icon-badge + title + subtitle header for a page."""
    title_cls = "tp-title-dark" if dark else "tp-title"
    sub_cls = "tp-sub-dark" if dark else "tp-sub"
    sub_html = f'<p class="{sub_cls}">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="page-header">'
        f'<div class="icon-badge">{icon}</div>'
        f'<div class="ph-text">'
        f'<h1 class="{title_cls}">{title}</h1>'
        f'{sub_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _metric(icon: str, label: str, value: str, accent: str = "indigo",
            dark: bool = False, delta: str = "") -> str:
    """Return HTML for a single icon-accented metric card."""
    cls = "metric-card-dark" if dark else "metric-card"
    delta_html = f'<div class="delta">{delta}</div>' if delta else ""
    return (
        f'<div class="{cls} accent-{accent}">'
        f'<div class="m-top"><div class="label">{label}</div>'
        f'<div class="m-icon">{icon}</div></div>'
        f'<div class="value">{value}</div>{delta_html}</div>'
    )


def _empty(icon: str, title: str, subtitle: str = "", dark: bool = False) -> None:
    """Render a rich, illustrated empty-state card in place of st.info()."""
    cls = "empty-pro dark" if dark else "empty-pro"
    sub_html = f'<p>{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="{cls}"><div class="ep-icon">{icon}</div>'
        f'<h4>{title}</h4>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def _card(height: Optional[int] = None):
    """Bordered container styled as a surface card (real wrapper for widgets)."""
    if height:
        return st.container(border=True, height=height)
    return st.container(border=True)


def _ring(pct: float, label: str, color: str = "#5b5ef4", dark: bool = False) -> str:
    """Return HTML for a pure-CSS circular progress ring."""
    pct = max(0, min(100, pct))
    rb = "#111a30"
    text_color = "color:#e8ecf6;"
    label_color = "#8b95ab"
    return (
        f'<div class="ring-wrap">'
        f'<div class="ring" style="--rc:{color};--rp:{pct};--rb:{rb}">'
        f'<div class="ring-inner" style="{text_color}">{pct:.0f}%</div></div>'
        f'<div style="{text_color}"><div style="font-size:12.5px;font-weight:600;'
        f'color:{label_color}">{label}</div></div></div>'
    )


# ── Cached singletons ────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_data_manager() -> DataManager:
    """Return the process-wide DataManager."""
    return DataManager()


@st.cache_resource(show_spinner=False)
def get_compiler() -> CppCompiler:
    """Return the process-wide CppCompiler — prefer local g++ since Piston API is dead."""
    return CppCompiler(prefer_local=True)


def _model_version() -> float:
    """Newest mtime of the model files (cache key; changes after any save)."""
    mt = 0.0
    for name in ("profiles.json", "metadata.json"):
        try:
            mt = max(mt, os.path.getmtime(os.path.join(MODEL_PATH, name)))
        except OSError:
            pass
    return mt


@st.cache_resource(show_spinner=False, max_entries=2)
def _load_model_cached(version: float) -> BehavioralAuthModel:
    """Load the model once per on-disk version; backfill missing user profiles."""
    model = BehavioralAuthModel.load(MODEL_PATH)
    dm = get_data_manager()
    changed = False
    for user in dm.all_enrolled_users():
        if not model.has_profile(user) and model.set_profile(user, dm.get_samples(user)):
            changed = True
    if changed:
        model.save_profiles(MODEL_PATH)  # cheap; bumps the version so the cache refreshes
    return model


def load_model() -> BehavioralAuthModel:
    """Load (or construct empty) BehavioralAuthModel; reloads only after a save."""
    return _load_model_cached(_model_version())


def retrain_model() -> Optional[Dict[str, float]]:
    """Rebuild every enrolled student's profile and retrain the LSTM (needs >= 2 students)."""
    dm = get_data_manager()
    enrolled = dm.all_enrolled_users()
    if not enrolled:
        return None
    X: List[List[float]] = []
    y: List[str] = []
    for u in enrolled:
        for feats in dm.get_samples(u):
            X.append(feats)
            y.append(u)
    model = BehavioralAuthModel()
    metrics = model.fit(X, y)
    model.save(MODEL_PATH)
    return metrics


# ── Declared component ───────────────────────────────────────────────────────
_tp_widget = components.declare_component("tp_widget", path=FRONTEND_DIR)


def tp_widget(**kwargs: Any) -> Optional[Dict[str, Any]]:
    """Thin wrapper around the declared component."""
    return _tp_widget(default=None, **kwargs)


# ── Session state ────────────────────────────────────────────────────────────
def _init_state() -> None:
    """Set every session-state key the app relies on."""
    defaults: Dict[str, Any] = {
        "authenticated": False,
        "role": None,
        "username": None,
        "full_name": None,
        "course_name": None,
        "enrollment_no": None,
        "page": "login",
        "selected_course": None,
        "active_exam_id": None,
        "active_lab_id": None,
        "active_lab_problem_idx": 0,
        "exam_answers": {},
        "lab_code": "",
        "lab_last_result": None,
        "auth_log": [],
        "cp_log": [],
        "session_id": None,
        "consecutive_fails": 0,
        "exam_verified": False,
        "exam_start_time": None,
        "exam_deadline": None,
        "exam_submitted": False,
        # UI
        "_login_stage": "role",  # role | login | register
        "_login_role_picked": None,
        "_login_tab": "login",
        "_pending_page": None,
        "_processed_nonces": set(),
        "_login_error": None,
        "_signup_error": None,
        "_verify_attempts": 0,
        "_show_password": False,
        # Registration wizard
        "reg_step": 1,
        "reg_data": {},
        "reg_samples": [],
        "last_reg_ts": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


_init_state()


def _apply_pending_page() -> None:
    """Consume `_pending_page` before any widget is instantiated."""
    pending = st.session_state.pop("_pending_page", None)
    if pending:
        st.session_state.page = pending


def _goto(page: str) -> None:
    """Schedule a navigation that survives the next rerun."""
    st.session_state._pending_page = page
    st.rerun()


# ── Inline JS helpers ────────────────────────────────────────────────────────
def inject_animated_bg() -> None:
    """Inject the gradient + 3 floating orbs behind the login card."""
    st.markdown(
        '<div class="login-bg"></div>'
        '<div class="orb orb-1"></div>'
        '<div class="orb orb-2"></div>'
        '<div class="orb orb-3"></div>',
        unsafe_allow_html=True,
    )


SHIELD_SVG = """
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  <path d="M9 12l2 2 4-4"/>
</svg>
"""


# ── Payload dispatcher ───────────────────────────────────────────────────────
def _handle_payload(payload: Optional[Dict[str, Any]]) -> bool:
    """Route a single component payload to the matching handler."""
    if not payload or not isinstance(payload, dict):
        return False
    n = payload.get("nonce")
    if not n or n in st.session_state._processed_nonces:
        return False
    st.session_state._processed_nonces.add(n)
    kind = payload.get("kind")
    dm = get_data_manager()
    if kind == "enrollment_sample":
        _handle_enroll_sample(dm, payload)
    elif kind == "verify_phrase":
        _handle_verify_phrase(dm, payload)
    elif kind == "exam_continuous_check":
        _handle_exam_continuous(dm, payload)
    elif kind == "exam_cp_event":
        _handle_cp_event(dm, payload)
    elif kind == "exam_answer":
        _handle_exam_answer_update(dm, payload)
    elif kind == "lab_run":
        _handle_lab_run(dm, payload)
    elif kind == "lab_submit":
        _handle_lab_submit(dm, payload)
    elif kind == "lab_continuous_check":
        _handle_lab_continuous(dm, payload)
    elif kind == "lab_paste":
        _handle_lab_paste(dm, payload)
    elif kind == "login_verify":
        _handle_login_verify(dm, payload)
    elif kind == "reg_sample":
        _handle_reg_sample(dm, payload)
    elif kind == "lab_code_update":
        st.session_state.lab_code = payload.get("code", "")
        return False
    else:
        return False
    return True


def _handle_enroll_sample(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Persist one enrolment sample; retrain if we have enough."""
    feats = payload.get("features")
    user = payload.get("username") or st.session_state.username
    if not feats or not user:
        return
    count = dm.add_sample(user, feats)
    st.session_state["_enroll_count"] = count
    if count >= ENROLL_TARGET:
        retrain_model()


def _handle_verify_phrase(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Score a fixed-phrase verification sample (used by exam-entry gate)."""
    feats = payload.get("features")
    user = st.session_state.username
    if not feats or not user:
        return
    res = load_model().predict(feats, user)
    st.session_state["_verify_confidence"] = res["confidence"]
    if res["decision"]:
        st.session_state.exam_verified = True
        st.session_state._verify_attempts = 0
    else:
        st.session_state._verify_attempts += 1
        if st.session_state._verify_attempts >= 3:
            dm.log_auth_check(
                user,
                st.session_state.session_id or "verify",
                res["confidence"],
                "Blocked",
                engine="phrase_verify",
            )


def _handle_exam_continuous(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Log a continuous-auth check from the exam, possibly trigger re-verify."""
    feats = payload.get("features")
    user = st.session_state.username
    sess = st.session_state.session_id
    if not (feats and user and sess):
        return
    res = load_model().predict(feats, user, context="free")
    conf = res["confidence"]
    if conf >= AMBER_CONFIDENCE:
        status = "Verified"
        st.session_state.consecutive_fails = 0
    elif conf >= LOW_CONFIDENCE:
        status = "Warning"
        st.session_state.consecutive_fails = 0
    else:
        status = "Flagged"
        st.session_state.consecutive_fails += 1
    dm.log_auth_check(user, sess, conf, status)
    st.session_state.auth_log.append(
        {"timestamp": time.time(), "confidence": conf, "status": status}
    )
    if isinstance(payload.get("answers"), dict):  # each check also checkpoints answers
        _handle_exam_answer_update(dm, payload)


def _handle_cp_event(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Persist a copy-paste/keyboard-shortcut event from the exam UI."""
    user = st.session_state.username
    sess = st.session_state.session_id
    if not (user and sess):
        return
    event_type = payload.get("event_type", "paste")
    qid = payload.get("question_id", "")
    chars = int(payload.get("chars", 0))
    dm.log_cp_event(user, sess, event_type, qid, chars)
    st.session_state.cp_log.append(
        {
            "event_type": event_type,
            "question_id": qid,
            "chars": chars,
            "timestamp": time.time(),
        }
    )


def _handle_exam_answer_update(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Sync answers from the iframe into session_state and the database draft."""
    answers = payload.get("answers") or {}
    if not isinstance(answers, dict):
        return
    deadline = st.session_state.exam_deadline
    if deadline and time.time() > deadline + 2:  # late edits do not count
        return
    st.session_state.exam_answers.update({str(k): str(v) for k, v in answers.items()})
    eid, user = st.session_state.active_exam_id, st.session_state.username
    if eid and user:
        dm.update_draft_answers(user, eid, st.session_state.exam_answers)


def _handle_lab_run(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Compile + run lab code against the sample input only."""
    code = payload.get("code", "")
    stdin = payload.get("stdin", "")
    timeout = int(payload.get("time_limit", 3))
    res = get_compiler().compile_and_run(
        code, stdin=stdin, timeout=timeout,
        memory_mb=int(payload.get("memory_limit", 0) or 0),
    )
    res["kind"] = "run"
    st.session_state.lab_code = code
    st.session_state.lab_last_result = res


def _handle_lab_submit(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Grade lab code against all hidden tests + persist a submission."""
    code = payload.get("code", "")
    lab_id = st.session_state.active_lab_id
    user = st.session_state.username
    idx = st.session_state.active_lab_problem_idx
    if not (lab_id and user):
        return
    lab = dm.get_lab(lab_id)
    if not lab or idx >= len(lab["problems"]):
        return
    problem = lab["problems"][idx]
    timeout = int(problem.get("time_limit_s", 3))
    grading = grade_submission(
        get_compiler(), code, problem.get("test_cases", []), time_limit=timeout,
        memory_mb=int(problem.get("memory_limit_mb", 0) or 0),
    )
    dm.save_lab_submission(
        username=user,
        lab_id=lab_id,
        problem_id=problem["problem_id"],
        code=code,
        test_results=grading["results"],
        score=grading["score"],
        max_score=grading["max_score"],
        engine_used=grading["engine_used"],
        compile_error=grading["compile_error"],
    )
    st.session_state.lab_code = code
    st.session_state.lab_last_result = {
        "kind": "submit",
        "results": grading["results"],
        "score": grading["score"],
        "max_score": grading["max_score"],
        "passed": grading["passed"],
        "total": grading["total"],
        "compile_error": grading["compile_error"],
        "engine_used": grading["engine_used"],
    }


def _handle_lab_continuous(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Continuous-auth check during a lab session."""
    feats = payload.get("features")
    user = st.session_state.username
    sess = st.session_state.session_id or f"lab_{st.session_state.active_lab_id}"
    if not (feats and user):
        return
    res = load_model().predict(feats, user, context="free")
    conf = res["confidence"]
    if conf >= AMBER_CONFIDENCE:
        status = "Verified"
    elif conf >= LOW_CONFIDENCE:
        status = "Warning"
    else:
        status = "Flagged"
    dm.log_auth_check(user, sess, conf, status, engine="lab_continuous")
    st.session_state.auth_log.append(
        {"timestamp": time.time(), "confidence": conf, "status": status}
    )


def _handle_lab_paste(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Persist a paste event from the lab editor."""
    user = st.session_state.username
    sess = st.session_state.session_id or f"lab_{st.session_state.active_lab_id}"
    chars = int(payload.get("chars", 0))
    dm.log_cp_event(user, sess, "paste", payload.get("question_id", ""), chars)


# ── Login screen ─────────────────────────────────────────────────────────────
def show_login_page() -> None:
    """Animated landing page with hero panel, role chooser, login + register forms."""
    inject_animated_bg()

    # Hero (left) + auth card (right). Hero auto-hides on narrow screens via CSS.
    hero_col, _, card_col, _ = st.columns([1.15, 0.1, 1.25, 0.15])

    with hero_col:
        st.markdown(
            '<div class="login-hero">'
            '<div class="eyebrow">🛡️ AI-powered exam integrity</div>'
            '<h1>Prove it\'s really <span class="grad">you</span> — every time '
            'you sit an exam.</h1>'
            '<p class="lead">TrueTestAuth verifies identity continuously through keystroke '
            'dynamics, so exams and code labs stay honest — no extra hardware, no interruptions.</p>'
            '<div class="feat-row"><div class="feat-icon">⌨️</div>'
            '<div class="feat-text"><b>Keystroke biometrics</b>'
            '<span>Learns each student\'s typing rhythm to catch impersonation in real time.</span>'
            '</div></div>'
            '<div class="feat-row"><div class="feat-icon">🧪</div>'
            '<div class="feat-text"><b>Exams &amp; code labs, unified</b>'
            '<span>Run proctored exams and auto-graded coding labs from one dashboard.</span>'
            '</div></div>'
            '<div class="feat-row"><div class="feat-icon">📊</div>'
            '<div class="feat-text"><b>Actionable integrity reports</b>'
            '<span>Faculty get per-student confidence scores, flags, and exportable reports.</span>'
            '</div></div>'
            '<div class="stat-strip">'
            '<div class="stat"><b>13</b><span>Behavioral features</span></div>'
            '<div class="stat"><b>LSTM</b><span>Sequence model</span></div>'
            '<div class="stat"><b>&lt;1s</b><span>Verification time</span></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    with card_col:
        with st.container(key="login_card"):
            st.markdown(
                f'<div class="login-logo">{SHIELD_SVG}<span>TrueTestAuth</span></div>'
                f'<div class="login-tagline">Verified identity for every exam, '
                f"powered by keystroke dynamics</div>",
                unsafe_allow_html=True,
            )

            stage = st.session_state._login_stage
            if stage == "role":
                st.markdown("<h3>Choose your role</h3>", unsafe_allow_html=True)
                if st.button("🎓  Continue as Student", key="role_student", width='stretch'):
                    st.session_state._login_role_picked = "student"
                    st.session_state._login_stage = "form"
                    st.session_state._login_tab = "login"
                    st.rerun()
                if st.button("👨‍🏫  Continue as Faculty", key="role_faculty", width='stretch'):
                    st.session_state._login_role_picked = "faculty"
                    st.session_state._login_stage = "form"
                    st.session_state._login_tab = "login"
                    st.rerun()
                st.markdown(
                    '<div class="tiny-help">First time? Register after selecting your role</div>',
                    unsafe_allow_html=True,
                )
            elif stage == "verify_behavior":
                # Behavioral phrase verification for student login
                _render_login_verify_behavior()
            else:
                role = st.session_state._login_role_picked or "student"
                tab = st.session_state._login_tab
                reg_step = st.session_state.get("reg_step", 1)
                # Only hide heading during enrollment steps 2/3
                hide_heading = (tab == "register" and role == "student" and reg_step >= 2)
                if not hide_heading:
                    heading = "Sign in" if tab == "login" else "Create account"
                    st.markdown(
                        f"<h3>{heading} as <span style='color:#a5b4fc;text-transform:capitalize;'>"
                        f"{role}</span></h3>",
                        unsafe_allow_html=True,
                    )
                if tab == "login":
                    _render_login_form(role)
                else:
                    _render_register_form(role)
                # Toggle link + Change role (only during heading-visible stages)
                if not hide_heading:
                    if tab == "login":
                        toggle_text = "Don't have an account? <b>Register</b>"
                        toggle_tab = "register"
                    else:
                        toggle_text = "Already registered? <b>Login</b>"
                        toggle_tab = "login"
                    if st.button(
                        toggle_text.replace("<b>", "").replace("</b>", ""),
                        key="tab_toggle",
                        width='stretch'
                    ):
                        st.session_state._login_tab = toggle_tab
                        st.session_state.reg_step = 1
                        st.rerun()
                    st.markdown(
                        '<div class="role-back" style="text-align: center; margin-top: 15px;">'
                        '<a href="?back=1" style="color:rgba(255,255,255,0.5); text-decoration: none;">← Change role</a>'
                        "</div>",
                        unsafe_allow_html=True,
                    )
                if "back" in st.query_params:
                    st.query_params.clear()
                    st.session_state._login_stage = "role"
                    st.session_state._login_role_picked = None
                    st.session_state.reg_step = 1
                    st.rerun()


def _render_login_form(role: str) -> None:
    """Render login fields and handle submission."""
    dm = get_data_manager()
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="e.g. alice_cs")
        password = st.text_input("Password", type="password",
                                 placeholder="Your password")
        submitted = st.form_submit_button("Login", type="primary",
                                          width='stretch')
    if st.session_state._login_error:
        st.markdown(
            f"<div style='color:#fca5a5;font-size:13px;margin-top:6px;'>"
            f"{st.session_state._login_error}</div>",
            unsafe_allow_html=True,
        )
    if submitted:
        user = dm.login_user(username.strip(), password, role)
        if not user:
            st.session_state._login_error = "Wrong username, password, or role."
            st.rerun()
        st.session_state._login_error = None
        if role == "student":
            # Require behavioral verification for students
            st.session_state._pending_login = user
            st.session_state._login_stage = "verify_behavior"
            st.session_state._verify_login_attempts = 0
            st.session_state._verify_login_confidence = None
            st.rerun()
        else:
            st.session_state.authenticated = True
            st.session_state.role = role
            st.session_state.username = user["username"]
            st.session_state.full_name = user["full_name"]
            st.session_state.course_name = user.get("course_name")
            st.session_state.enrollment_no = user.get("enrollment_no")
            st.session_state.page = "overview"
            st.rerun()


def _complete_student_login(user: Dict[str, Any]) -> None:
    """Populate the session for a verified student and go to the courses page."""
    st.session_state.authenticated = True
    st.session_state.role = "student"
    st.session_state.username = user["username"]
    st.session_state.full_name = user.get("full_name", user["username"])
    st.session_state.course_name = user.get("course_name")
    st.session_state.enrollment_no = user.get("enrollment_no")
    st.session_state.page = "courses"
    st.session_state._pending_login = None


def _handle_login_verify(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Score the login phrase sample; log the student in on success."""
    user = st.session_state.get("_pending_login") or {}
    feats = payload.get("features")
    if not feats or not user:
        return
    model = load_model()
    if not model.is_trained:
        _complete_student_login(user)  # no model yet: nothing to verify against
        return
    conf = model.predict(feats, user["username"]).get("confidence", 0.0)
    st.session_state._verify_login_confidence = conf
    if conf >= AUTH_THRESHOLD:
        _complete_student_login(user)
    else:
        st.session_state._verify_login_attempts = (
            st.session_state.get("_verify_login_attempts", 0) + 1
        )


def _render_login_verify_behavior() -> None:
    """Verify student identity by typing the behavioral phrase before login."""
    user = st.session_state.get("_pending_login") or {}
    attempts = st.session_state.get("_verify_login_attempts", 0)

    if attempts >= 3:
        st.markdown("<div style='text-align:center;font-size:36px;margin:8px 0;'>🚫</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#fca5a5;text-align:center;font-size:15px;font-weight:600;margin-bottom:12px;'>Verification failed after 3 attempts</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:rgba(255,255,255,0.5);text-align:center;font-size:13px;margin-bottom:16px;'>Your typing pattern did not match. Please contact your faculty.</div>", unsafe_allow_html=True)
        if st.button("← Try different account", key="verify_back"):
            st.session_state._login_stage = "form"
            st.session_state._pending_login = None
            st.rerun()
        return

    st.markdown(f"<div style='color:white;font-size:18px;font-weight:700;margin-bottom:4px;'>Welcome back, {user.get('full_name','')}</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:13px;margin-bottom:16px;'>Type the phrase below to verify your identity</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);border-radius:12px;padding:14px 18px;text-align:center;color:#c7d2fe;font-size:18px;font-weight:600;letter-spacing:0.04em;margin-bottom:12px;'>{PHRASE}</div>", unsafe_allow_html=True)

    if attempts > 0:
        conf = st.session_state.get("_verify_login_confidence")
        if conf is not None:
            st.markdown(f"<div style='color:#fca5a5;font-size:13px;margin-bottom:8px;'>Confidence: {conf * 100:.0f}% — too low. {3 - attempts} attempts remaining.</div>", unsafe_allow_html=True)

    payload = tp_widget(
        widget_type="phrase_capture",
        phrase=PHRASE,
        kind="login_verify",
        button_label="Verify Identity",
        sent_text="Verifying…",
        key=f"login_verify_{user.get('username', '')}_{attempts}",
    )
    if _handle_payload(payload):
        st.rerun()

    if st.button("← Back to login", key="back_to_login"):
        st.session_state._login_stage = "form"
        st.session_state._pending_login = None
        st.rerun()


def _render_register_form(role: str) -> None:
    """Render register fields. Faculty: simple form. Student: 3-step wizard."""
    dm = get_data_manager()
    if role == "faculty":
        _render_faculty_register(dm)
        return
    # Student 3-step wizard
    step = st.session_state.get("reg_step", 1)
    if step == 1:
        _reg_step1(dm)
    elif step == 2:
        _reg_step2(dm)
    elif step == 3:
        _reg_step3(dm)


def _render_faculty_register(dm) -> None:
    with st.form("reg_form_fac", clear_on_submit=False):
        full_name = st.text_input("Full name")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        course_name = st.text_input("Course name", placeholder="CS301 - Data Structures")
        submitted = st.form_submit_button("Create Account", type="primary", width='stretch')
    if st.session_state._signup_error:
        st.markdown(f"<div style='color:#fca5a5;font-size:13px;margin-top:6px;'>{st.session_state._signup_error}</div>", unsafe_allow_html=True)
    if submitted:
        if not (full_name and username and password):
            st.session_state._signup_error = "All required fields must be filled."
            st.rerun()
        if password != confirm:
            st.session_state._signup_error = "Passwords do not match."
            st.rerun()
        if not course_name.strip():
            st.session_state._signup_error = "Course name is required for faculty."
            st.rerun()
        ok = dm.register_user(username=username.strip().lower(), password=password, full_name=full_name.strip(), role="faculty", course_name=course_name.strip())
        if not ok:
            st.session_state._signup_error = "Username already exists."
            st.rerun()
        st.session_state._signup_error = None
        st.session_state._login_tab = "login"
        st.success("Account created — please log in.")
        st.rerun()


def _reg_step1(dm) -> None:
    """Step 1: Account details for student."""
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:12px;margin-bottom:8px;'>Step 1 of 3 — Account Details</div>", unsafe_allow_html=True)
    with st.form("reg_step1_form", clear_on_submit=False):
        full_name = st.text_input("Full Name")
        username = st.text_input("Username")
        enrollment_no = st.text_input("Enrollment Number", placeholder="EN21CS001")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        st.caption("Your faculty will add you to their course after you register.")
        submitted = st.form_submit_button("Next →", type="primary", width='stretch')
    if st.session_state._signup_error:
        st.markdown(f"<div style='color:#fca5a5;font-size:13px;margin-top:6px;'>{st.session_state._signup_error}</div>", unsafe_allow_html=True)
    if submitted:
        uname = username.strip().lower()
        if not (full_name and uname and password and enrollment_no):
            st.session_state._signup_error = "All fields are required."
            st.rerun()
        if password != confirm:
            st.session_state._signup_error = "Passwords do not match."
            st.rerun()
        if dm.user_exists(uname):
            st.session_state._signup_error = "Username already taken."
            st.rerun()
        st.session_state._signup_error = None
        st.session_state.reg_data = {
            "full_name": full_name.strip(),
            "username": uname,
            "password": password,
            "enrollment_no": enrollment_no.strip(),
        }
        st.session_state.reg_step = 2
        st.session_state.reg_samples = []
        st.session_state["_reg_done"] = False
        st.rerun()


def _handle_reg_sample(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Store one enrolment sample (kept in the session until step 3 registers the user)."""
    feats = payload.get("features")
    if feats:
        st.session_state.setdefault("reg_samples", []).append(feats)


def _reg_step2(dm) -> None:
    """Step 2: Behavioural enrollment — type phrase 10 times."""
    sample_count = len(st.session_state.get("reg_samples", []))
    if sample_count >= ENROLL_TARGET:
        st.session_state.reg_step = 3
        st.rerun()
        return
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:12px;margin-bottom:8px;'>Step 2 of 3 — Teach the system your typing rhythm</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:rgba(255,255,255,0.45);font-size:13px;margin-bottom:12px;'>Type the phrase below exactly 10 times. This creates your unique behavioral fingerprint used to verify your identity during exams.</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);border-radius:12px;padding:14px 18px;text-align:center;color:#c7d2fe;font-size:18px;font-weight:600;letter-spacing:0.04em;margin-bottom:12px;'>{PHRASE}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:white;font-size:14px;font-weight:600;margin-bottom:6px;'>Sample {sample_count} of {ENROLL_TARGET}</div>", unsafe_allow_html=True)
    st.progress(sample_count / ENROLL_TARGET)

    payload = tp_widget(
        widget_type="phrase_capture",
        phrase=PHRASE,
        kind="reg_sample",
        button_label="Submit Sample",
        sent_text="✅ Sample captured!",
        key="reg_capture",
    )
    if _handle_payload(payload):
        st.rerun()

    if st.button("← Back", key="reg_back"):
        st.session_state.reg_step = 1
        st.rerun()


def _reg_step3(dm) -> None:
    """Step 3: Train profile + complete registration."""
    rd = st.session_state.reg_data
    samples = st.session_state.get("reg_samples", [])
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:12px;margin-bottom:8px;'>Step 3 of 3 — Finalizing</div>", unsafe_allow_html=True)
    # Streamlit re-runs this function on every interaction (including the final
    # "Enter" click); do the one-time registration + training exactly once.
    if not st.session_state.get("_reg_done"):
        with st.spinner("Training your behavioral profile..."):
            ok = dm.register_user(
                username=rd["username"],
                password=rd["password"],
                full_name=rd["full_name"],
                role="student",
                enrollment_no=rd.get("enrollment_no"),
            )
            if not ok:
                st.error("Username already exists.")
                st.session_state.reg_step = 1
                st.rerun()
                return
            dm.save_keystroke_samples(rd["username"], samples)
            st.session_state["_reg_train_result"] = retrain_model()
            st.session_state["_reg_done"] = True
    train_result = st.session_state.get("_reg_train_result")
    st.markdown("<div style='text-align:center;font-size:48px;margin:12px 0;'>✅</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:white;text-align:center;font-size:18px;font-weight:600;margin-bottom:8px;'>Profile created!</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:rgba(255,255,255,0.6);text-align:center;font-size:13px;margin-bottom:16px;'>Your behavioral fingerprint is ready.</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.06);border-radius:12px;padding:16px;margin-bottom:16px;'>"
        f"<div style='color:#94a3b8;font-size:12px;'>Username</div><div style='color:white;font-weight:600;'>{rd['username']}</div>"
        f"<div style='color:#94a3b8;font-size:12px;margin-top:8px;'>Course</div><div style='color:white;font-weight:600;'>Pending — your faculty will enroll you</div>"
        f"<div style='color:#94a3b8;font-size:12px;margin-top:8px;'>Samples collected</div><div style='color:white;font-weight:600;'>{len(samples)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if train_result is not None and "lstm_train_acc" not in train_result:
        st.info("Your typing profile is saved. The LSTM model trains once a second student enrolls.")
    if st.button("Enter TrueTestAuth →", type="primary", width='stretch', key="enter_tp"):
        st.session_state.authenticated = True
        st.session_state.role = "student"
        st.session_state.username = rd["username"]
        st.session_state.full_name = rd["full_name"]
        st.session_state.enrollment_no = rd.get("enrollment_no")
        st.session_state.page = "courses"
        st.session_state.reg_step = 1
        st.session_state.reg_data = {}
        st.session_state.reg_samples = []
        st.session_state["_reg_done"] = False
        st.rerun()


# ── Faculty layout ──────────────────────────────────────────────────────────
_FACULTY_NAV = [
    ("overview", "📊  Overview"),
    ("exams", "📝  Exam Management"),
    ("lab", "🧪  Code Lab"),
    ("students", "🎓  Students"),
    ("reports", "📋  Reports"),
    ("settings", "⚙️  Settings"),
]


def _initials(name: Optional[str], default: str = "U") -> str:
    """Up to two uppercase initials from a display name."""
    return "".join(x[0] for x in (name or default).split()[:2]).upper() or default


def _logout() -> None:
    """Clear the session and return to the login screen."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    _init_state()
    st.rerun()


def _faculty_layout(render_content) -> None:
    """Sidebar + content shell shared by every faculty page."""
    sb, content = st.columns([1, 4], gap="small")
    with sb:
        _render_faculty_sidebar_inner()
    with content:
        with st.container(key="fac_content"):
            render_content()


def _render_faculty_sidebar_inner() -> None:
    """Brand, profile card, nav buttons (active = primary) and logout."""
    page = st.session_state.page
    course = st.session_state.course_name or ""
    with st.container(key="fac_sidebar"):
        st.markdown(
            f'<div class="fs-brand">{SHIELD_SVG}<span>TrueTestAuth</span></div>'
            f'<div class="fs-user"><div class="side-avatar">{_initials(st.session_state.full_name, "F")}</div>'
            f'<div><div class="who">{st.session_state.full_name}</div>'
            f'<div class="course-pill">{course}</div></div></div>'
            f'<div class="nav-label">Main menu</div>',
            unsafe_allow_html=True,
        )
        for key, label in _FACULTY_NAV:
            if st.button(
                label, key=f"nav_{key}", width="stretch",
                type="primary" if page == key else "secondary",
            ):
                _goto(key)
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        with st.container(key="fac_logout"):
            if st.button("⏻  Logout", key="nav_logout", width="stretch"):
                _logout()


# ── Faculty: Overview ───────────────────────────────────────────────────────
def show_faculty_overview() -> None:
    """Top-level metric cards + recent activity + integrity alerts."""
    def _content():
        dm = get_data_manager()
        students = dm.get_faculty_students(st.session_state.username)
        exams = dm.get_exams(faculty_username=st.session_state.username)
        labs = dm.get_labs(faculty_username=st.session_state.username)
        flagged = dm.get_flagged_recent(faculty_username=st.session_state.username)
        recent = dm.get_recent_submissions(faculty_username=st.session_state.username, limit=8)

        _titles = {"dr.", "dr", "prof.", "prof", "mr.", "mrs.", "ms."}
        _parts = [w for w in (st.session_state.full_name or "there").split() if w.lower() not in _titles]
        first_name = _parts[0] if _parts else "there"
        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        _page_header(
            "📊",
            f"{greeting}, {first_name}",
            f"Here's what's happening in {st.session_state.course_name or 'your course'} today.",
        )

        active_exam_ct = len([e for e in exams if e.get("status") != "ended"])
        flag_accent = "red" if flagged else "green"
        st.markdown(
            '<div class="metric-grid">'
            + _metric("🎓", "Students enrolled", str(len(students)), "indigo")
            + _metric("📝", "Active exams", str(active_exam_ct), "cyan")
            + _metric("🧪", "Active labs", str(len(labs)), "amber")
            + _metric("🚩", "Flagged sessions (24h)", str(len(flagged)), flag_accent)
            + "</div>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            with _card(height=330):
                st.markdown(
                    '<div class="card-eyebrow"><span class="dot"></span>Recent activity</div>',
                    unsafe_allow_html=True,
                )
                if not recent:
                    _empty("📭", "No activity yet",
                           "Submissions and check-ins will show up here as students take exams and labs.")
                else:
                    rows = ""
                    for r in recent:
                        ts = pd.to_datetime(r["timestamp"], unit="s").strftime("%d %b · %H:%M")
                        icon = "📝" if r["kind"] == "exam" else "🧪"
                        rows += (
                            "<div class='feed-row'><div class='fr-left'>"
                            f"<div class='fr-dot' style='background:rgba(91,94,244,0.10)'>{icon}</div>"
                            "<div><span style='color:var(--text);font-weight:600;font-size:13.5px'>"
                            f"{r.get('student_name', r['username'])}</span>"
                            f"<span style='color:#94a3b8;font-size:12px;margin-left:8px'>{r['kind']}</span></div>"
                            "</div>"
                            f"<span style='color:#94a3b8;font-size:12px;white-space:nowrap'>{ts}</span></div>"
                        )
                    st.markdown(rows, unsafe_allow_html=True)
        with c2:
            with _card(height=330):
                st.markdown(
                    '<div class="card-eyebrow"><span class="dot" style="background:#ef4444"></span>'
                    'Integrity alerts <span style="color:#94a3b8;font-weight:500;text-transform:none;'
                    'letter-spacing:normal">(24h)</span></div>',
                    unsafe_allow_html=True,
                )
                if not flagged:
                    _empty("✅", "All clear", "No integrity flags in the last 24 hours.")
                else:
                    rows = ""
                    for f in flagged:
                        ts = pd.to_datetime(f["timestamp"], unit="s").strftime("%H:%M")
                        rows += (
                            "<div class='feed-row'><div class='fr-left'>"
                            "<div class='fr-dot' style='background:rgba(239,68,68,0.10)'>🚩</div>"
                            "<div><span style='color:var(--text);font-weight:600;font-size:13.5px'>"
                            f"{f.get('student_name', f['username'])}</span></div></div>"
                            f"<span style='color:#94a3b8;font-size:12px;white-space:nowrap'>"
                            f"conf {f['confidence']*100:.0f}% · {ts}</span></div>"
                        )
                    st.markdown(rows, unsafe_allow_html=True)

        if not students and not exams and not labs:
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            with _card():
                st.markdown(
                    '<div class="card-eyebrow"><span class="dot"></span>Getting started</div>'
                    '<div style="display:flex;gap:18px;flex-wrap:wrap;">'
                    '<div style="flex:1;min-width:200px;">'
                    '<div style="font-size:13.5px;font-weight:700;color:var(--text);margin-bottom:4px;">'
                    '① Create your first exam</div>'
                    '<div style="font-size:12.5px;color:#94a3b8;line-height:1.6;">Head to '
                    '<b>Exam Management</b> and add questions with a time limit.</div></div>'
                    '<div style="flex:1;min-width:200px;">'
                    '<div style="font-size:13.5px;font-weight:700;color:var(--text);margin-bottom:4px;">'
                    '② Set up a code lab</div>'
                    '<div style="font-size:12.5px;color:#94a3b8;line-height:1.6;">Add C++ problems with '
                    'test cases under <b>Code Lab</b>.</div></div>'
                    '<div style="flex:1;min-width:200px;">'
                    '<div style="font-size:13.5px;font-weight:700;color:var(--text);margin-bottom:4px;">'
                    '③ Enroll your students</div>'
                    '<div style="font-size:12.5px;color:#94a3b8;line-height:1.6;">Open <b>Students</b> '
                    'and pick from the registered students to add them to your course.</div></div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

    _faculty_layout(_content)


# ── Faculty: Exam Management ────────────────────────────────────────────────
def show_faculty_exams() -> None:
    """Three-tab exam-management page (Create / Active / Submissions)."""
    def _content():
        _page_header("📝", "Exam Management", "Create, monitor, and review exam submissions.")
        t1, t2, t3 = st.tabs(["➕ Create exam", "📂 Active exams", "🗂 Submissions"])
        with t1:
            _faculty_create_exam_form()
        with t2:
            _faculty_active_exams()
        with t3:
            _faculty_exam_submissions()

    _faculty_layout(_content)


def _faculty_create_exam_form() -> None:
    """Compose an exam (questions + PDF parse) and persist it.

    Deliberately NOT inside st.form: a form only reruns on submit, so choosing
    "MCQ" would not reveal the option fields until after saving. Plain widgets
    rerun on every change, so the option inputs appear immediately.
    """
    dm = get_data_manager()
    if "_exam_q_count" not in st.session_state:
        st.session_state._exam_q_count = 5
    g = st.session_state.get("_exam_form_gen", 0)  # bumped after saving to clear the form
    saved = st.session_state.pop("_exam_saved_msg", None)
    if saved:
        st.success(saved)

    cc1, cc2, _ = st.columns([1, 1, 4])
    with cc1:
        if st.button("➕ Add question", key="add_q"):
            st.session_state._exam_q_count += 1
    with cc2:
        if st.button("➖ Remove last", key="del_q"):
            if st.session_state._exam_q_count > 1:
                st.session_state._exam_q_count -= 1

    pdf_file = st.file_uploader(
        "Or upload a PDF question paper to extract text", type=["pdf"]
    )
    pdf_text = ""
    if pdf_file is not None:
        pdf_text = _extract_pdf_text(pdf_file)
        st.text_area("Extracted PDF text (review)", value=pdf_text, height=200, key="_pdf_text")

    c1, c2 = st.columns([2, 1])
    with c1:
        title = st.text_input("Exam title", placeholder="Mid-Sem — Data Structures",
                              key=f"ex_title_{g}")
        subject = st.text_input(
            "Subject / course", value=st.session_state.course_name or "", key=f"ex_subj_{g}"
        )
        instructions = st.text_area(
            "Instructions", height=80, placeholder="Read carefully…", key=f"ex_instr_{g}"
        )
    with c2:
        edate = st.date_input("Opens on", value=date.today(), key=f"ex_date_{g}")
        etime = st.time_input("Opens at", value=dtime(10, 0), key=f"ex_time_{g}")
        duration = st.slider("Duration (minutes)", 30, 180, 60, key=f"ex_dur_{g}")
        window = st.number_input(
            "Stays open for (min, 0 = same as duration)", 0, 10080, 0, key=f"ex_win_{g}",
            help="How long students can start the exam after it opens.",
        )

    st.markdown(f"##### Questions ({st.session_state._exam_q_count})")
    questions: List[Dict[str, Any]] = []
    for i in range(st.session_state._exam_q_count):
        with st.expander(f"Question {i + 1}", expanded=(i == 0)):
            qa, qb = st.columns([3, 1])
            with qa:
                qtype = st.selectbox(
                    "Type", ["Descriptive", "MCQ"], key=f"qt_{g}_{i}"
                )
                qtext_default = pdf_text if (i == 0 and pdf_text) else ""
                qtext = st.text_area(
                    f"Question text {i + 1}",
                    value=qtext_default,
                    height=100,
                    key=f"qtext_{g}_{i}",
                )
            with qb:
                marks = st.number_input(
                    "Marks", min_value=1, max_value=50, value=10, step=1, key=f"qm_{g}_{i}"
                )
            if qtype == "MCQ":
                options = [
                    st.text_input(f"Option {L}", key=f"o{k}_{g}_{i}")
                    for k, L in enumerate("ABCD")
                ]
                correct = st.radio(
                    "Correct option", ["A", "B", "C", "D"], horizontal=True,
                    key=f"corr_{g}_{i}",
                )
            else:
                options, correct = [], ""
            questions.append(
                {
                    "q_id": f"q{i + 1}",
                    "type": qtype,
                    "text": qtext,
                    "marks": int(marks),
                    "options": [o.strip() for o in options],
                    "correct": correct,
                }
            )

    if st.button("💾  Save exam", width="stretch", key=f"ex_save_{g}"):
        filled = [q for q in questions if q["text"].strip()]
        bad_mcq = next(
            (q["q_id"] for q in filled if q["type"] == "MCQ"
             and (any(not o for o in q["options"])
                  or len({o.lower() for o in q["options"]}) != 4)),
            None,
        )
        if not title.strip():
            st.error("Title is required.")
        elif not filled:
            st.error("Add at least one question.")
        elif bad_mcq:
            st.error(f"{bad_mcq.upper()}: an MCQ needs four different, non-empty options.")
        else:
            eid = dm.create_exam(
                faculty_username=st.session_state.username,
                title=title.strip(),
                subject=subject.strip(),
                date=str(edate),
                start_time=etime.strftime("%H:%M"),
                duration_mins=int(duration),
                instructions=instructions,
                questions=filled,
                window_mins=int(window) or None,
            )
            st.session_state._exam_form_gen = g + 1
            st.session_state._exam_q_count = 5
            st.session_state._exam_saved_msg = f"Saved exam id={eid}."
            st.rerun()


def _faculty_active_exams() -> None:
    """Card grid of all exams owned by this faculty."""
    dm = get_data_manager()
    exams = dm.get_exams(faculty_username=st.session_state.username)
    if not exams:
        _empty("📂", "No exams created yet",
               "Switch to the \u201cCreate exam\u201d tab to build your first proctored exam.")
        return
    for e in exams:
        state = exam_state(e)
        sts_cls = {"upcoming": "badge-upcoming", "open": "badge-active",
                   "closed": "badge-ended"}[state]
        opens, closes = exam_window(e)
        window_txt = (
            f"opens {datetime.fromtimestamp(opens):%d %b %H:%M}, "
            f"closes {datetime.fromtimestamp(closes):%d %b %H:%M}"
            if closes != float("inf") else "always open"
        )
        st.markdown(
            f'<div class="tp-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:14px;">'
            f'<div style="display:flex;align-items:center;gap:14px;min-width:0;">'
            f'<div class="m-icon" style="background:rgba(91,94,244,0.10);color:#4f46e5;'
            f'width:42px;height:42px;border-radius:12px;font-size:18px;flex-shrink:0;'
            f'display:flex;align-items:center;justify-content:center;">📝</div>'
            f'<div style="min-width:0;">'
            f'<b style="font-size:15.5px; color:var(--text);">{e["title"]}</b>'
            f'<div style="color:#94a3b8;font-size:12.5px;margin-top:3px;">'
            f'{e["subject"]} · {e["date"]} {e.get("start_time","")} · '
            f'{e["duration_mins"]} min · {len(e["questions"])} questions</div>'
            f'<div style="color:#94a3b8;font-size:12px;margin-top:2px;">{window_txt}</div>'
            f'</div></div>'
            f'<span class="badge {sts_cls}" style="flex-shrink:0;">{state.upper()}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("🗓 Reschedule", expanded=False):
            with st.form(f"resched_{e['exam_id']}"):
                r1, r2, r3 = st.columns(3)
                try:
                    d0 = datetime.strptime(e["date"], "%Y-%m-%d").date()
                    t0 = datetime.strptime(e.get("start_time") or "10:00", "%H:%M").time()
                except (ValueError, TypeError):
                    d0, t0 = date.today(), dtime(10, 0)
                nd = r1.date_input("Date", value=d0)
                nt = r2.time_input("Start time", value=t0)
                nw = r3.number_input("Stays open (min, 0 = same as duration)", 0, 10080,
                                     value=int(e.get("window_mins") or 0))
                if st.form_submit_button("Save schedule"):
                    dm.update_exam(e["exam_id"], {
                        "date": str(nd), "start_time": nt.strftime("%H:%M"),
                        "window_mins": int(nw) or None,
                    })
                    st.rerun()


def _faculty_exam_submissions() -> None:
    """Submissions browser per-exam with drill-down expansion."""
    dm = get_data_manager()
    exams = dm.get_exams(faculty_username=st.session_state.username)
    if not exams:
        _empty("🗂", "No exams to review yet", "Create an exam first, then submissions will appear here.")
        return
    eid_map = {e["exam_id"]: e["title"] for e in exams}
    eid = st.selectbox(
        "Pick an exam",
        options=list(eid_map.keys()),
        format_func=lambda k: eid_map[k],
    )
    _finalize_expired(dm, exam_id=eid)  # submit attempts whose time ran out
    subs = dm.get_exam_submissions(exam_id=eid)
    eid_exam = dm.get_exam(eid)
    if not subs:
        _empty("📭", "No submissions yet", "Once students complete this exam, their submissions will show up here.")
        return
    mcq_total = sum(int(q.get("marks", 0)) for q in eid_exam["questions"] if q.get("type") == "MCQ")
    rows = []
    for s in subs:
        u = dm.get_user(s["username"]) or {}
        auth_log = dm.get_auth_log(s["username"], s["session_id"])
        cp_log = dm.get_cp_log(s["username"], s["session_id"])
        avg_conf = (
            sum(a["confidence"] for a in auth_log) / len(auth_log) if auth_log else 0.0
        )
        integrity = dm.calculate_integrity_score(avg_conf, len(cp_log))
        rows.append(
            {
                "Student": u.get("full_name", s["username"]),
                "Enrollment": u.get("enrollment_no", ""),
                "Submitted": pd.to_datetime(s["timestamp"], unit="s").strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "Status": integrity["grade"],
                "Integrity": f"{integrity['integrity_score']:.0f}%",
                "Score": f"{s.get('score', 0)}/{mcq_total}" if mcq_total else s.get("score", ""),
                "_username": s["username"],
                "_session_id": s["session_id"],
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(
        df.drop(columns=["_username", "_session_id"]),
        width='stretch',
        hide_index=True,
    )
    st.download_button(
        "📥 Download CSV",
        data=df.drop(columns=["_username", "_session_id"]).to_csv(index=False).encode(),
        file_name=f"submissions_{eid}.csv",
        mime="text/csv",
    )

    st.markdown("##### Drill into a submission")
    pick = st.selectbox(
        "Student",
        options=list(range(len(rows))),
        format_func=lambda i: rows[i]["Student"],
    )
    row = rows[pick]
    sub = next(
        s
        for s in subs
        if s["username"] == row["_username"] and s["session_id"] == row["_session_id"]
    )
    exam = dm.get_exam(eid)
    auth_log = dm.get_auth_log(row["_username"], row["_session_id"])
    cp_log = dm.get_cp_log(row["_username"], row["_session_id"])

    st.markdown(f"**Answers** — {row['Student']}")
    for q in exam["questions"]:
        with st.expander(f"Q{q['q_id'][1:]}. {q['text'][:80]}…", expanded=False):
            ans = sub.get("answers", {}).get(q["q_id"], "")
            if q.get("type") == "MCQ":
                right = (ans or "").upper()[:1] == (q.get("correct") or "").upper()[:1] and bool(ans)
                st.write(
                    f"{'✅' if right else '❌'} Chosen: **{ans or '—'}** · "
                    f"Correct: **{q.get('correct', '?')}** · "
                    f"{q.get('marks', 0) if right else 0}/{q.get('marks', 0)} marks"
                )
            else:
                st.write(ans or "_(blank)_")

    if auth_log:
        st.markdown("**Behavioural auth timeline**")
        df_a = pd.DataFrame(auth_log)
        df_a["time"] = pd.to_datetime(df_a["timestamp"], unit="s")
        st.line_chart(df_a.set_index("time")[["confidence"]], height=180)

    if cp_log:
        st.markdown("**Copy-paste events**")
        df_c = pd.DataFrame(cp_log)
        df_c["time"] = pd.to_datetime(df_c["timestamp"], unit="s").dt.strftime(
            "%H:%M:%S"
        )
        st.dataframe(
            df_c[["time", "event_type", "question_id", "chars"]],
            width='stretch',
            hide_index=True,
        )


def _extract_pdf_text(file_obj) -> str:
    """Extract plain text from an uploaded PDF using pdfplumber."""
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(file_obj) as pdf:
            return "\n\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as exc:
        return f"[Could not parse PDF: {exc}]"


# ── Faculty: Lab Management ─────────────────────────────────────────────────
def show_faculty_lab() -> None:
    """Three-tab Code-Lab page (Create / Active / Submissions)."""
    def _content():
        _page_header("🧪", "Code Lab", "Author C++ problems with auto-graded test cases.")
        t1, t2, t3 = st.tabs(
            ["➕ Create lab", "📂 Active labs", "🗂 Lab submissions"]
        )
        with t1:
            _faculty_create_lab_form()
        with t2:
            _faculty_active_labs()
        with t3:
            _faculty_lab_submissions()

    _faculty_layout(_content)


def _faculty_create_lab_form() -> None:
    """Form for composing a multi-problem lab."""
    dm = get_data_manager()
    if "_lab_problems" not in st.session_state:
        st.session_state._lab_problems = [_blank_problem(0)]

    cc1, cc2, _ = st.columns([1, 1, 4])
    with cc1:
        if st.button("➕ Add problem", key="add_prob"):
            st.session_state._lab_problems.append(
                _blank_problem(len(st.session_state._lab_problems))
            )
    with cc2:
        if st.button("➖ Remove last", key="del_prob"):
            if len(st.session_state._lab_problems) > 1:
                st.session_state._lab_problems.pop()

    with st.form("create_lab_form", clear_on_submit=False):
        c1, c2 = st.columns([2, 1])
        with c1:
            title = st.text_input("Lab title", placeholder="Lab 1 — Basic C++")
            description = st.text_area("Description (markdown OK)", height=80)
        with c2:
            ddate = st.date_input("Deadline date", value=date.today())
            dtime_v = st.time_input("Deadline time", value=dtime(23, 59))

        for i, _ in enumerate(st.session_state._lab_problems):
            with st.expander(f"Problem {i + 1}", expanded=(i == 0)):
                _render_problem_block(i)

        ok = st.form_submit_button("💾  Save lab", width='stretch')
        if ok:
            problems_payload: List[Dict[str, Any]] = []
            for i in range(len(st.session_state._lab_problems)):
                p = _read_problem_block(i)
                if p["title"].strip() and p["test_cases"]:
                    problems_payload.append(p)
            if not title.strip() or not problems_payload:
                st.error("Lab title and at least one valid problem are required.")
            else:
                lid = dm.create_lab(
                    faculty_username=st.session_state.username,
                    title=title.strip(),
                    course=st.session_state.course_name or "",
                    deadline=f"{ddate} {dtime_v}",
                    description=description,
                    problems=problems_payload,
                )
                st.session_state._lab_problems = [_blank_problem(0)]
                st.success(f"Saved lab id={lid}.")


def _blank_problem(idx: int) -> Dict[str, Any]:
    """Return a fresh problem template used by the create-lab form."""
    return {
        "id": idx,
        "title": "",
        "difficulty": "Easy",
        "statement": "",
        "time_limit": 3,
        "memory_limit": 64,
        "samples": [{"input": "", "expected": ""}],
        "tests": [{"input": "", "expected": "", "points": 10}],
    }


def _render_problem_block(i: int) -> None:
    """Render the per-problem fields of the create-lab form."""
    p = st.session_state._lab_problems[i]
    a, b = st.columns([3, 1])
    with a:
        st.text_input(f"Problem title {i + 1}", value=p["title"], key=f"pt_{i}")
    with b:
        st.selectbox(
            "Difficulty",
            ["Easy", "Medium", "Hard"],
            index=["Easy", "Medium", "Hard"].index(p["difficulty"]),
            key=f"pd_{i}",
        )
    st.text_area(
        f"Statement {i + 1} (markdown OK)",
        value=p["statement"],
        height=100,
        key=f"ps_{i}",
    )
    c1, c2 = st.columns(2)
    with c1:
        st.slider("Time limit (s)", 1, 10, p["time_limit"], key=f"tl_{i}")
    with c2:
        st.slider("Memory (MB)", 16, 256, p["memory_limit"], key=f"ml_{i}")

    st.markdown("**Sample test (visible to student)**")
    sa, sb = st.columns(2)
    with sa:
        st.text_area(
            f"Sample input {i + 1}",
            value=p["samples"][0]["input"],
            height=70,
            key=f"si_{i}",
        )
    with sb:
        st.text_area(
            f"Sample output {i + 1}",
            value=p["samples"][0]["expected"],
            height=70,
            key=f"so_{i}",
        )

    st.markdown("**Hidden tests**")
    n_tests = max(1, len(p["tests"]))
    n_tests = st.number_input(
        f"How many hidden tests? (problem {i + 1})",
        min_value=1,
        max_value=10,
        value=n_tests,
        step=1,
        key=f"ntests_{i}",
    )
    while len(p["tests"]) < n_tests:
        p["tests"].append({"input": "", "expected": "", "points": 10})
    while len(p["tests"]) > n_tests:
        p["tests"].pop()
    for j in range(n_tests):
        cc = st.columns([3, 3, 1])
        with cc[0]:
            st.text_area(
                f"Hidden input {j + 1} (P{i + 1})",
                value=p["tests"][j]["input"],
                height=60,
                key=f"hi_{i}_{j}",
            )
        with cc[1]:
            st.text_area(
                f"Hidden expected {j + 1} (P{i + 1})",
                value=p["tests"][j]["expected"],
                height=60,
                key=f"he_{i}_{j}",
            )
        with cc[2]:
            st.number_input(
                f"Pts {j + 1}",
                min_value=0,
                max_value=50,
                value=p["tests"][j]["points"],
                step=1,
                key=f"hp_{i}_{j}",
            )


def _read_problem_block(i: int) -> Dict[str, Any]:
    """Re-read the per-problem widget values into a dict for save_lab."""
    n_tests = int(st.session_state.get(f"ntests_{i}", 1))
    tests = []
    for j in range(n_tests):
        tin = st.session_state.get(f"hi_{i}_{j}", "")
        tout = st.session_state.get(f"he_{i}_{j}", "")
        pts = int(st.session_state.get(f"hp_{i}_{j}", 10))
        if tin.strip() or tout.strip():
            tests.append({"input": tin, "expected_output": tout, "points": pts})
    return {
        "problem_id": f"prob_{uuid.uuid4().hex[:8]}",
        "title": st.session_state.get(f"pt_{i}", ""),
        "difficulty": st.session_state.get(f"pd_{i}", "Easy"),
        "statement": st.session_state.get(f"ps_{i}", ""),
        "time_limit_s": int(st.session_state.get(f"tl_{i}", 3)),
        "memory_limit_mb": int(st.session_state.get(f"ml_{i}", 64)),
        "samples": [
            {
                "input": st.session_state.get(f"si_{i}", ""),
                "expected_output": st.session_state.get(f"so_{i}", ""),
            }
        ],
        "test_cases": tests,
        "starter_code": DEFAULT_STARTER_CODE,
        "total_points": sum(t["points"] for t in tests),
    }


def _faculty_active_labs() -> None:
    """Card list of all labs by this faculty."""
    dm = get_data_manager()
    labs = dm.get_labs(faculty_username=st.session_state.username)
    if not labs:
        _empty("🧪", "No labs created yet", "Add your first coding lab with problems and test cases below.")
        return
    for lab in labs:
        st.markdown(
            f'<div class="tp-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:14px;">'
            f'<div style="display:flex;align-items:center;gap:14px;min-width:0;">'
            f'<div class="m-icon" style="background:rgba(6,182,212,0.10);color:#0e7490;'
            f'width:42px;height:42px;border-radius:12px;font-size:18px;flex-shrink:0;'
            f'display:flex;align-items:center;justify-content:center;">🧪</div>'
            f'<div style="min-width:0;">'
            f'<b style="font-size:15.5px; color:var(--text);">{lab["title"]}</b>'
            f'<div style="color:#94a3b8;font-size:12.5px;margin-top:3px;">'
            f'{lab.get("course","")} · deadline {lab.get("deadline","")}</div>'
            f'<div style="color:#94a3b8;font-size:12.5px;margin-top:2px;">'
            f'{len(lab.get("problems", []))} problems · '
            f'{sum(p["total_points"] for p in lab.get("problems", []))} pts total</div>'
            f'</div></div>'
            f'<span class="badge badge-active" style="flex-shrink:0;">ACTIVE</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


def _faculty_lab_submissions() -> None:
    """Submissions table per-lab with drill-down."""
    dm = get_data_manager()
    labs = dm.get_labs(faculty_username=st.session_state.username)
    if not labs:
        _empty("🗂", "No labs to review yet", "Create a lab first, then submissions will appear here.")
        return
    lid_map = {lab["lab_id"]: lab["title"] for lab in labs}
    lid = st.selectbox(
        "Pick a lab",
        options=list(lid_map.keys()),
        format_func=lambda k: lid_map[k],
    )
    lab = dm.get_lab(lid)
    rows = []
    for prob in lab.get("problems", []):
        for s in dm.get_lab_submissions(lab_id=lid, problem_id=prob["problem_id"]):
            u = dm.get_user(s["username"]) or {}
            auth = dm.get_auth_log(s["username"], f"lab_{lid}")
            cp = dm.get_cp_log(s["username"], f"lab_{lid}")
            rows.append(
                {
                    "Student": u.get("full_name", s["username"]),
                    "Problem": prob["title"],
                    "Score": f"{s['score']}/{s['max_score']}",
                    "Tests": f"{s['passed']}/{s['total']}",
                    "Attempts": s.get("attempts", 1),
                    "Submitted": pd.to_datetime(s["timestamp"], unit="s").strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "Auth flags": sum(1 for a in auth if a.get("status") == "Flagged"),
                    "Paste events": len(cp),
                    "_username": s["username"],
                    "_problem_id": prob["problem_id"],
                }
            )
    if not rows:
        _empty("📭", "No submissions yet", "Student lab submissions will appear here once they start solving.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(
        df.drop(columns=["_username", "_problem_id"]),
        width='stretch',
        hide_index=True,
    )
    st.markdown("##### Drill into a lab submission")
    pick = st.selectbox(
        "Submission",
        options=list(range(len(rows))),
        format_func=lambda i: f"{rows[i]['Student']} — {rows[i]['Problem']}",
    )
    row = rows[pick]
    sub = dm.get_best_lab_submission(row["_username"], row["_problem_id"])
    if not sub:
        return
    if sub.get("compile_error"):
        st.error("Compilation failed.")
        st.code(sub["compile_error"], language="text")
    st.markdown("**Submitted code**")
    st.code(sub.get("code", ""), language="cpp")
    st.markdown("**Per-test-case results**")
    for k, r in enumerate(sub.get("results", [])):
        cls = "tc-pass" if r.get("status") == "pass" else "tc-fail"
        body = (
            f"<b>Test {k + 1}</b> — "
            f"{'✅ pass' if r.get('status') == 'pass' else '❌ fail'} "
            f"({r.get('awarded',0)}/{r.get('points',0)} pts) · "
            f"{r.get('time_ms',0)} ms"
        )
        if r.get("status") != "pass":
            body += (
                f"<div style='color:var(--text-2);margin-top:0.25rem;'>"
                f"<b>Got:</b> <code>{r.get('got','')}</code> &nbsp;"
                f"<b>Expected:</b> <code>{r.get('expected','')}</code></div>"
            )
        st.markdown(f"<div class='{cls}'>{body}</div>", unsafe_allow_html=True)
    auth_log = dm.get_auth_log(row["_username"], f"lab_{lid}")
    if auth_log:
        df_a = pd.DataFrame(auth_log)
        df_a["time"] = pd.to_datetime(df_a["timestamp"], unit="s")
        st.line_chart(df_a.set_index("time")[["confidence"]], height=180)


# ── Faculty: Reports ────────────────────────────────────────────────────────
def show_faculty_reports() -> None:
    """Per-student integrity + academic-performance dashboard."""
    def _content():
        dm = get_data_manager()
        _page_header("📋", "Reports", "Per-student integrity and academic summary.")
        students = dm.get_faculty_students(st.session_state.username)
        if not students:
            _empty("📋", "No students enrolled yet",
                   "Once you enroll students (Students page), their reports will appear here.")
            return
        sopt = {s["username"]: s.get("full_name", s["username"]) for s in students}
        sel = st.selectbox(
            "Select student",
            options=list(sopt.keys()),
            format_func=lambda u: sopt[u],
        )

        st.markdown("### Behavioural authentication report")
        summary = dm.get_student_auth_summary(sel)

        rc1, rc2 = st.columns([1, 3])
        with rc1:
            with _card():
                avg_pct = summary["avg_conf"] * 100
                ring_color = "#16a34a" if avg_pct >= 65 else "#d97706" if avg_pct >= 45 else "#dc2626"
                st.markdown(_ring(avg_pct, "Avg confidence", ring_color), unsafe_allow_html=True)
        with rc2:
            st.markdown(
                '<div class="metric-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:0;">'
                + _metric("📉", "Min confidence", f"{summary['min_conf']*100:.1f}%", "cyan")
                + _metric("✅", "Total checks", str(summary["total_checks"]), "indigo")
                + _metric("🚩", "Flags", str(summary["flag_count"]), "red" if summary["flag_count"] else "green")
                + "</div>",
                unsafe_allow_html=True,
            )

        all_logs = summary["entries"]
        if all_logs:
            df = pd.DataFrame(all_logs)
            df["time"] = pd.to_datetime(df["timestamp"], unit="s")
            st.line_chart(df.set_index("time")[["confidence"]], height=220)
        else:
            _empty("📈", "No confidence readings yet", "This student hasn't taken an authenticated exam yet.")

        st.markdown("### Per-exam summary")
        per_exam = dm.get_per_exam_summary(sel)
        if per_exam:
            st.dataframe(pd.DataFrame(per_exam), width='stretch', hide_index=True)
        else:
            _empty("🗒️", "No exam data yet", "Per-exam breakdown appears once this student submits an exam.")

        st.markdown("### Academic performance")
        rows = dm.get_academic_history(sel)
        if rows:
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
            st.download_button(
                "📥 Download full report (CSV)",
                data=pd.DataFrame(rows).to_csv(index=False).encode(),
                file_name=f"report_{sel}.csv",
                mime="text/csv",
            )
        else:
            _empty("🎓", "No academic history yet", "Grades and coursework history will show up here.")

    _faculty_layout(_content)


# ── Faculty: Students (enrol registered students into the course) ──────────
def show_faculty_students() -> None:
    """Faculty choose which registered students join their course."""
    def _content():
        dm = get_data_manager()
        me = st.session_state.username
        _page_header(
            "🎓", "Students",
            f"Choose which registered students join {st.session_state.course_name or 'your course'}. "
            "Enrolled students see your exams, quizzes and labs.",
        )
        flash = st.session_state.pop("_students_msg", None)
        if flash:
            st.success(flash)

        pool = dm.get_unenrolled_students(me)
        enrolled = dm.get_faculty_students(me)

        st.markdown(f"### Registered students not in your course ({len(pool)})")
        if not pool:
            _empty("✅", "No one waiting",
                   "Every registered student is already enrolled. New sign-ups appear here.")
        else:
            by_user = {s["username"]: s for s in pool}
            picked = st.multiselect(
                "Select students to enroll (type to search by name, username or enrollment no.)",
                options=list(by_user),
                format_func=lambda u: (
                    f"{by_user[u].get('full_name') or u} · {by_user[u].get('enrollment_no') or '—'}"
                    f" · @{u}"
                ),
                key="enroll_pick",
            )
            b1, b2, _ = st.columns([1.2, 1.2, 4])
            if b1.button("➕ Enroll selected", type="primary", disabled=not picked,
                         key="enroll_sel"):
                for u in picked:
                    dm.enroll_student(u, me)
                st.session_state.pop("enroll_pick", None)
                st.session_state._students_msg = f"Enrolled {len(picked)} student(s)."
                st.rerun()
            if b2.button(f"➕ Enroll all ({len(pool)})", key="enroll_all"):
                for s in pool:
                    dm.enroll_student(s["username"], me)
                st.session_state.pop("enroll_pick", None)
                st.session_state._students_msg = f"Enrolled {len(pool)} student(s)."
                st.rerun()

        st.markdown(f"### Enrolled in your course ({len(enrolled)})")
        if not enrolled:
            _empty("🎓", "No students enrolled yet",
                   "Pick students from the list above to add them to your course.")
        for s in enrolled:
            c1, c2 = st.columns([6, 1])
            with c1:
                st.markdown(
                    "<div class='feed-row'><div class='fr-left'>"
                    f"<div class='avatar' style='width:32px;height:32px;font-size:12px;'>"
                    f"{_initials(s.get('full_name'), 'S')}</div>"
                    f"<span><b style='color:var(--text);'>{s.get('full_name') or s['username']}</b> "
                    f"<span style='color:#94a3b8;font-size:12.5px;'>· {s.get('enrollment_no') or '—'}"
                    f" · @{s['username']}</span></span></div></div>",
                    unsafe_allow_html=True,
                )
            if c2.button("Remove", key=f"unenroll_{s['username']}"):
                dm.unenroll_student(s["username"], me)
                st.session_state._students_msg = (
                    f"Removed {s.get('full_name') or s['username']} from your course."
                )
                st.rerun()

    _faculty_layout(_content)


# ── Faculty: Settings ───────────────────────────────────────────────────────
def show_faculty_settings() -> None:
    """Settings: change course name + view enrolled students."""
    def _content():
        dm = get_data_manager()
        _page_header("⚙️", "Settings", "Update your course and view enrolled students.")

        sc1, sc2 = st.columns([1.1, 1])
        with sc1:
            with _card():
                st.markdown(
                    '<div class="card-eyebrow"><span class="dot"></span>Course details</div>',
                    unsafe_allow_html=True,
                )
                with st.form("settings_form"):
                    new_course = st.text_input("Course name", value=st.session_state.course_name or "")
                    ok = st.form_submit_button("Update course")
                    if ok:
                        dm.update_user(st.session_state.username, {"course_name": new_course.strip()})
                        st.session_state.course_name = new_course.strip()
                        st.success("Course updated.")
                        st.rerun()
        with sc2:
            with _card():
                st.markdown(
                    '<div class="card-eyebrow"><span class="dot"></span>Account</div>',
                    unsafe_allow_html=True,
                )
                initials = _initials(st.session_state.full_name, "F")
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;">'
                    f'<div class="avatar" style="width:44px;height:44px;font-size:15px;">{initials}</div>'
                    f'<div><div style="font-weight:700;font-size:14.5px;color:var(--text);">'
                    f'{st.session_state.full_name}</div>'
                    f'<div style="font-size:12.5px;color:#94a3b8;">@{st.session_state.username} · Faculty</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        with _card():
            st.markdown(
                '<div class="card-eyebrow"><span class="dot"></span>Enrolled students</div>',
                unsafe_allow_html=True,
            )
            students = dm.get_faculty_students(st.session_state.username)
            if not students:
                _empty("🎓", "No students enrolled yet",
                       "Go to the Students page to enroll registered students.")
            else:
                for s in students:
                    initials = "".join(x[0] for x in (s.get("full_name", "S")).split()[:2]).upper()
                    st.markdown(
                        "<div class='feed-row'><div class='fr-left'>"
                        f"<div class='avatar' style='width:32px;height:32px;font-size:12px;'>{initials}</div>"
                        f"<span><b style='color:var(--text);'>{s.get('full_name', s['username'])}</b> "
                        f"<span style='color:#94a3b8;font-size:12.5px;'>· {s.get('enrollment_no','')}</span></span>"
                        "</div>"
                        f"<span class='badge badge-easy'>{s['username']}</span></div>",
                        unsafe_allow_html=True,
                    )
    _faculty_layout(_content)


# ── Student layout ──────────────────────────────────────────────────────────
from ui_components import render_student_navbar as _ui_student_navbar


def _student_layout(render) -> None:
    """Sticky navbar + padded content container with a logout action."""
    _ui_student_navbar()
    with st.container(key="stu_content"):
        _, logout_col = st.columns([9, 1])
        with logout_col:
            if st.button("Logout", key="stu_logout_top", width="stretch"):
                _logout()
        render()


# ── Student: Courses ─────────────────────────────────────────────────────────
def show_student_courses() -> None:
    """List of faculty-courses this student is enrolled in."""
    def _content():
        dm = get_data_manager()
        _page_header("🎓", "Your Courses", "Pick a course to see its exams and labs.", dark=True)
        courses = dm.get_student_courses(st.session_state.username)
        if not courses:
            _empty("🎓", "No courses yet",
                   "Your faculty enrolls students into their course. Once they add you, "
                   "it will show up here.", dark=True)
            return
        cols = st.columns(3, gap="medium")
        for i, fac in enumerate(courses):
            initials = _initials(fac.get("full_name", "F"), "F")
            n_exams = len(dm.get_exams(faculty_username=fac["username"]))
            n_labs = len(dm.get_labs(faculty_username=fac["username"]))
            with cols[i % 3]:
                st.markdown(
                    f'<div class="course-card-dark">'
                    f'<div class="head">'
                    f'<span class="avatar">{initials}</span>'
                    f'<div><div class="name">{fac.get("full_name","Faculty")}</div>'
                    f'<div class="course">{fac.get("course_name","Course")}</div></div>'
                    f'</div>'
                    f'<div class="stats">'
                    f'<div><b>{n_exams}</b>Exams</div>'
                    f'<div><b>{n_labs}</b>Labs</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Open course →",
                    key=f"open_{fac['username']}",
                    width='stretch',
                    type="primary",
                ):
                    st.session_state.selected_course = fac["username"]
                    _goto("course_detail")
    _student_layout(_content)


def show_student_course_detail() -> None:
    """A course's two tabs: Exams + Labs."""
    def _content():
        dm = get_data_manager()
        fac = dm.get_user(st.session_state.selected_course or "") or {}
        # Enrolment can be revoked at any time; never show a course the student has left.
        if not fac or not dm.is_enrolled(st.session_state.username, fac["username"]):
            _goto("courses")
            return
        st.markdown(
            f'<a href="?back=1" style="color:#a5b4fc;font-size:13px;">← Home</a>'
            f'<h1 class="tp-title-dark" style="margin-top:4px;">'
            f'{fac.get("course_name","Course")}</h1>'
            f'<p class="tp-sub-dark">Faculty: {fac.get("full_name","")}</p>',
            unsafe_allow_html=True,
        )
        if "back" in st.query_params:
            st.query_params.clear()
            _goto("courses")
        t1, t2 = st.tabs(["📝 Exams", "🧪 Labs"])
        with t1:
            _finalize_expired(dm, username=st.session_state.username)
            exam_list = dm.get_exams(faculty_username=fac["username"])
            if not exam_list:
                _empty("📝", "No exams yet", "Your instructor hasn't published any exams for this course.", dark=True)
            for e in exam_list:
                sub = dm.get_exam_submission(st.session_state.username, e["exam_id"])
                draft = None if sub else dm.get_draft(st.session_state.username, e["exam_id"])
                state = exam_state(e)
                opens, closes = exam_window(e)
                if sub:
                    status, badge = "Submitted", "badge-active"
                elif draft:
                    status, badge = "In progress", "badge-warning"
                elif state == "open":
                    status, badge = "Open", "badge-active"
                elif state == "upcoming":
                    status, badge = "Upcoming", "badge-upcoming"
                else:
                    status, badge = "Closed", "badge-ended"
                st.markdown(
                    f'<div class="tp-card-dark">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
                    f'<div style="display:flex;align-items:center;gap:12px;min-width:0;">'
                    f'<div class="m-icon" style="background:rgba(91,94,244,0.14);color:#a5b4fc;'
                    f'width:38px;height:38px;border-radius:11px;font-size:16px;flex-shrink:0;'
                    f'display:flex;align-items:center;justify-content:center;">📝</div>'
                    f'<div><b style="color:white;">{e["title"]}</b>'
                    f'<div style="color:#94a3b8;font-size:12px;margin-top:3px;">'
                    f'{e["date"]} {e.get("start_time","")} · '
                    f'{e["duration_mins"]} min · {len(e["questions"])} questions</div></div></div>'
                    f'<span class="badge {badge}" style="flex-shrink:0;">{status.upper()}</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                fmt = "%d %b %H:%M"
                if draft:
                    if st.button(f"Resume exam: {e['title']}", key=f"resume_{e['exam_id']}", type="primary"):
                        st.session_state.active_exam_id = e["exam_id"]
                        st.session_state.exam_answers = dict(draft["answers"])
                        st.session_state.session_id = draft["session_id"]
                        st.session_state.exam_start_time = draft["started_at"]
                        st.session_state.exam_deadline = draft["deadline"]
                        st.session_state.auth_log = dm.get_auth_log(
                            st.session_state.username, draft["session_id"])
                        st.session_state.cp_log = dm.get_cp_log(
                            st.session_state.username, draft["session_id"])
                        st.session_state.consecutive_fails = 0
                        st.session_state.exam_verified = True  # identity was verified at login
                        st.session_state.exam_submitted = False
                        _goto("exam_portal")
                elif not sub and state == "open":
                    st.caption(f"Open until {datetime.fromtimestamp(closes).strftime(fmt)} · "
                               f"you get {e['duration_mins']} min once you start.")
                    if st.button(f"Start exam: {e['title']}", key=f"start_{e['exam_id']}", type="primary"):
                        st.session_state.active_exam_id = e["exam_id"]
                        st.session_state.exam_answers = {}
                        st.session_state.auth_log = []
                        st.session_state.cp_log = []
                        st.session_state.session_id = uuid.uuid4().hex
                        st.session_state.consecutive_fails = 0
                        st.session_state.exam_verified = False
                        st.session_state._verify_attempts = 0
                        st.session_state.exam_submitted = False
                        st.session_state.exam_deadline = None
                        _goto("exam_verify")
                elif not sub and state == "upcoming":
                    st.caption(f"🔒 Opens {datetime.fromtimestamp(opens).strftime(fmt)}.")
                elif not sub:
                    st.caption("⛔ This exam is closed and no submission was recorded.")
                else:
                    if st.button(f"View submission ({e['title']})", key=f"view_{e['exam_id']}"):
                        st.session_state.active_exam_id = e["exam_id"]
                        _goto("submitted")
        with t2:
            lab_list = dm.get_labs(faculty_username=fac["username"])
            if not lab_list:
                _empty("🧪", "No labs yet", "Your instructor hasn't published any coding labs for this course.", dark=True)
            for lab in lab_list:
                st.markdown(
                    f'<div class="tp-card-dark">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
                    f'<div style="display:flex;align-items:center;gap:12px;min-width:0;">'
                    f'<div class="m-icon" style="background:rgba(34,211,238,0.14);color:#67e8f9;'
                    f'width:38px;height:38px;border-radius:11px;font-size:16px;flex-shrink:0;'
                    f'display:flex;align-items:center;justify-content:center;">🧪</div>'
                    f'<div><b style="color:white;">{lab["title"]}</b>'
                    f'<div style="color:#94a3b8;font-size:12px;margin-top:3px;">'
                    f'deadline {lab.get("deadline","")} · '
                    f'{len(lab.get("problems",[]))} problems</div></div></div>'
                    f'<span class="badge badge-active" style="flex-shrink:0;">OPEN</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"Start lab: {lab['title']}", key=f"sl_{lab['lab_id']}", type="primary"):
                    st.session_state.active_lab_id = lab["lab_id"]
                    st.session_state.active_lab_problem_idx = 0
                    st.session_state.lab_code = (
                        lab["problems"][0].get("starter_code") or DEFAULT_STARTER_CODE
                    )
                    st.session_state.lab_last_result = None
                    st.session_state.session_id = f"lab_{lab['lab_id']}"
                    _goto("lab_portal")
    _student_layout(_content)


# ── Student: Exam verification gate ─────────────────────────────────────────
def show_exam_verification() -> None:
    """Block access to the exam until phrase verification confidence ≥ 45 %."""
    def _content():
        dm = get_data_manager()
        exam = dm.get_exam(st.session_state.active_exam_id) or {}
        st.markdown(
            f'<h1 class="tp-title">Identity Verification</h1>'
            f'<p class="tp-sub">{exam.get("title","Exam")} — please type the '
            f'phrase below to confirm your typing pattern.</p>',
            unsafe_allow_html=True,
        )
        if exam and exam_state(exam) != "open":
            st.error("This exam is not open right now.")
            if st.button("← Back to course"):
                _goto("course_detail")
            return
        if st.session_state._verify_attempts >= 3:
            st.error(
                "Verification failed 3 times. The faculty has been notified. "
                "You cannot start the exam from this device."
            )
            if st.button("← Back to course"):
                _goto("course_detail")
            return
        payload = tp_widget(
            widget_type="challenge",
            phrase=PHRASE,
            username=st.session_state.username,
            key=f"verify_{st.session_state.session_id}_{st.session_state._verify_attempts}",
        )
        if payload:
            payload["kind"] = "verify_phrase"
            if _handle_payload(payload):
                st.rerun()
        conf = st.session_state.get("_verify_confidence")
        if conf is not None:
            pct = conf * 100
            color = "#22c55e" if pct >= 65 else ("#f59e0b" if pct >= 45 else "#ef4444")
            st.markdown(
                f"<div class='tp-card'>"
                f"<div style='display:flex;justify-content:space-between;'>"
                f"<span>Confidence</span><b style='color:{color};'>{pct:.1f}%</b></div>"
                f"<div style='height:10px;background:rgba(148,163,184,0.18);border-radius:99px;'>"
                f"<div style='height:100%;width:{pct:.1f}%;background:{color};"
                f"border-radius:99px;'></div></div></div>",
                unsafe_allow_html=True,
            )
        if st.session_state.exam_verified:
            st.success("Verification passed.")
            if st.button("Enter Exam →", type="primary"):
                now = time.time()
                _, closes = exam_window(exam)
                if now >= closes:
                    st.error("The exam window has just closed.")
                    return
                # The attempt ends after `duration` or when the window closes, whichever is first.
                deadline = min(now + exam["duration_mins"] * 60, closes)
                dm.start_draft(st.session_state.username, exam["exam_id"],
                               st.session_state.session_id, now, deadline)
                draft = dm.get_draft(st.session_state.username, exam["exam_id"])
                st.session_state.exam_start_time = draft["started_at"]
                st.session_state.exam_deadline = draft["deadline"]
                st.session_state.session_id = draft["session_id"]
                _goto("exam_portal")
        elif st.session_state._verify_attempts > 0:
            st.warning(
                f"Try again — {3 - st.session_state._verify_attempts} attempts remaining."
            )
    _student_layout(_content)


# ── Student: Exam portal ────────────────────────────────────────────────────
def show_exam_portal() -> None:
    """Live exam UI — questions on the left, status sidebar on the right."""
    def _content():
        dm = get_data_manager()
        exam = dm.get_exam(st.session_state.active_exam_id) or {}
        if not exam:
            st.error("Exam not found.")
            return
        if st.session_state.exam_submitted:
            _goto("submitted")
            return
        # Server-side clock is authoritative; the browser only displays a countdown.
        total = exam["duration_mins"] * 60
        deadline = st.session_state.exam_deadline or (
            (st.session_state.exam_start_time or time.time()) + total
        )
        remaining = max(0, int(deadline - time.time()))
        mm, ss = divmod(remaining, 60)
        warn = "warning" if remaining < 5 * 60 else ""
        # Client-side countdown: no page reload (a reload would start a new
        # Streamlit session and wipe login + answers). On expiry it clicks the
        # hidden trigger so Python re-runs and auto-submits.
        countdown_js = f"""
        <script>
        (function(){{
          var end = Date.now() + {remaining} * 1000;
          function pad(n){{ return (n < 10 ? '0' : '') + n; }}
          function tick(){{
            var doc = window.parent.document;
            var el = doc.querySelector('.exam-timer');
            var left = Math.max(0, Math.round((end - Date.now()) / 1000));
            if (el) {{
              el.textContent = pad(Math.floor(left / 60)) + ':' + pad(left % 60);
              if (left < 300) el.classList.add('warning');
            }}
            if (left <= 0) {{
              clearInterval(h);
              doc.querySelectorAll('button').forEach(function(b){{
                if (b.innerText.includes('HiddenTrigger_Expire')) b.click();
              }});
            }}
          }}
          var h = setInterval(tick, 1000);
          tick();
        }})();
        </script>
        """
        components.html(countdown_js, height=0)
        st.button("HiddenTrigger_Expire", key="ht_expire")
        last_conf = (
            st.session_state.auth_log[-1]["confidence"]
            if st.session_state.auth_log
            else None
        )
        dot_cls = (
            "green" if last_conf is None or last_conf >= 0.65
            else ("amber" if last_conf >= 0.45 else "red")
        )
        st.markdown(
            f'<div class="tp-card" style="display:flex;justify-content:space-between;'
            f'align-items:center;">'
            f'<b>{exam["title"]}</b>'
            f'<span class="exam-timer {warn}">{mm:02d}:{ss:02d}</span>'
            f'<span><span class="auth-dot {dot_cls}"></span> '
            f'{("conf " + f"{last_conf*100:.0f}%") if last_conf is not None else "monitoring…"}'
            f'</span></div>',
            unsafe_allow_html=True,
        )
        if remaining <= 0:
            _do_exam_submit(dm, exam)
            return

        left, right = st.columns([13, 7])
        with left:
            payload = tp_widget(
                widget_type="exam_session",
                exam_title=exam["title"],
                # Never send the answer key to the browser.
                questions=[
                    {k: v for k, v in q.items() if k not in ("correct", "explanation", "slide")}
                    for q in exam["questions"]
                ],
                duration_ms=total * 1000,
                started_at_ms=int((st.session_state.exam_start_time or time.time()) * 1000),
                initial_answers=st.session_state.exam_answers,
                check_interval_ms=30_000,
                last_confidence=last_conf,
                key=f"exam_session_{st.session_state.session_id}",
            )
            if _handle_payload(payload):
                st.rerun()
            st.write("")
            if st.button("⏸ Pause / Submit Exam", type="primary",
                         width='stretch'):
                if st.session_state.get("_confirm_submit"):
                    _do_exam_submit(dm, exam)
                else:
                    st.session_state._confirm_submit = True
                    st.warning("Click again to confirm submission.")

        with right:
            answered_ids = {
                qid for qid, val in st.session_state.exam_answers.items() if val
            }
            dots_html = []
            for q in exam["questions"]:
                cls = "answered" if q["q_id"] in answered_ids else ""
                dots_html.append(
                    f'<div class="qnav-dot {cls}">{q["q_id"][1:]}</div>'
                )
            st.markdown(
                f'<div class="tp-card"><b>Question navigator</b>'
                f'<div class="qnav-grid" style="margin-top:0.6rem;">'
                f'{"".join(dots_html)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            pct = (last_conf or 1.0) * 100
            color = "#22c55e" if pct >= 65 else ("#f59e0b" if pct >= 45 else "#ef4444")
            status_text = "Verified" if pct >= 65 else ("Low confidence" if pct >= 45 else "Alert!")
            circumference = 2 * 3.14159 * 45
            offset = circumference - (pct / 100) * circumference
            gauge_html = f"""
            <div class="tp-card">
            <b>Auth Confidence</b>
            <div style="text-align:center;padding:12px">
              <svg width="120" height="120" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="45" fill="none" stroke="rgba(148,163,184,0.2)" stroke-width="8"/>
                <circle cx="60" cy="60" r="45" fill="none" stroke="{color}" stroke-width="8"
                  stroke-linecap="round" stroke-dasharray="{circumference}"
                  stroke-dashoffset="{offset}" transform="rotate(-90 60 60)"
                  style="transition:stroke-dashoffset 0.8s ease,stroke 0.4s ease"/>
                <text x="60" y="55" text-anchor="middle" font-size="20" font-weight="600"
                  fill="{color}" font-family="Inter,sans-serif">{pct:.0f}%</text>
                <text x="60" y="73" text-anchor="middle" font-size="11" fill="#8b95ab"
                  font-family="Inter,sans-serif">{status_text}</text>
              </svg>
              <div style="font-size:12px;color:#8b95ab;margin-top:4px">
                Check {len(st.session_state.auth_log)} · Next in ~30s
              </div>
            </div>
            </div>
            """
            st.markdown(gauge_html, unsafe_allow_html=True)
            if st.session_state.auth_log:
                with _card():
                    st.markdown("**Recent checks**")
                    for a in st.session_state.auth_log[-5:][::-1]:
                        ts = time.strftime("%H:%M:%S", time.localtime(a["timestamp"]))
                        c = a["confidence"] * 100
                        icon = "🟢" if c >= 65 else ("🟡" if c >= 45 else "🔴")
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;padding:4px 0;'>"
                            f"<span>{icon} {ts}</span>"
                            f"<span style='font-weight:600;color:{('#22c55e' if c >= 65 else '#f59e0b' if c >= 45 else '#ef4444')}'>{c:.0f}%</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
        if st.session_state.consecutive_fails >= 2:
            st.warning("Suspicious typing detected — re-verify on next check.")

    _student_layout(_content)


def _do_exam_submit(dm: DataManager, exam: Dict[str, Any]) -> None:
    """Persist the exam submission, integrity score and auth/cp logs."""
    user = st.session_state.username
    # A background finalisation (deadline passed) may already have saved it.
    if dm.get_exam_submission(user, exam["exam_id"]) is None:
        _save_submission(
            dm, exam, user, st.session_state.session_id, st.session_state.exam_answers,
            st.session_state.auth_log, st.session_state.cp_log,
        )
    dm.delete_draft(user, exam["exam_id"])
    st.session_state.exam_submitted = True
    _goto("submitted")


def _save_submission(
    dm: DataManager, exam: Dict[str, Any], user: str, session_id: str,
    answers: Dict[str, str], auth_log: List[Dict], cp_log: List[Dict],
) -> None:
    """Grade MCQs, compute integrity and store the final submission."""
    avg_conf = (
        sum(a["confidence"] for a in auth_log) / len(auth_log) if auth_log else 0.0
    )
    dm.save_exam_submission(
        username=user,
        exam_id=exam["exam_id"],
        session_id=session_id,
        answers=answers,
        auth_log=auth_log,
        cp_log=cp_log,
        score=_auto_grade_mcq(exam, answers),
        integrity=dm.calculate_integrity_score(avg_conf, len(cp_log)),
    )


def _finalize_expired(
    dm: DataManager, username: Optional[str] = None, exam_id: Optional[str] = None
) -> None:
    """Submit every attempt whose time ran out (student left or lost connection)."""
    for d in dm.get_expired_drafts(username=username, exam_id=exam_id):
        exam = dm.get_exam(d["exam_id"])
        if exam and dm.get_exam_submission(d["username"], d["exam_id"]) is None:
            _save_submission(
                dm, exam, d["username"], d["session_id"], d["answers"],
                dm.get_auth_log(d["username"], d["session_id"]),
                dm.get_cp_log(d["username"], d["session_id"]),
            )
        dm.delete_draft(d["username"], d["exam_id"])


def _auto_grade_mcq(exam: Dict[str, Any], answers: Dict[str, str]) -> int:
    """Auto-mark MCQ answers; descriptive remain manual."""
    score = 0
    for q in exam.get("questions", []):
        if q.get("type") == "MCQ":
            chosen = (answers.get(q["q_id"], "") or "").strip().upper()[:1]
            if chosen and chosen == (q.get("correct") or "").upper()[:1]:
                score += int(q.get("marks", 0))
    return score


# ── Student: Lab portal ─────────────────────────────────────────────────────
def show_lab_portal() -> None:
    """Code-lab portal — split panel with problem + dark editor."""
    def _content():
        dm = get_data_manager()
        lab = dm.get_lab(st.session_state.active_lab_id) or {}
        if not lab.get("problems"):
            st.error("Lab not found.")
            return
        idx = st.session_state.active_lab_problem_idx
        problem = lab["problems"][idx]

        st.markdown(
            '<a href="?back=1" style="color:#a5b4fc;font-size:13px;">← Back to course</a>',
            unsafe_allow_html=True,
        )
        if "back" in st.query_params:
            st.query_params.clear()
            _goto("course_detail")
        # Problem nav
        nav = st.columns(len(lab["problems"]))
        for i, p in enumerate(lab["problems"]):
            with nav[i]:
                lbl = f"P{i + 1}: {p['title']}"
                if st.button(
                    f"{'● ' if i == idx else ''}{lbl}",
                    key=f"prob_{i}",
                    width='stretch',
                ):
                    st.session_state.active_lab_problem_idx = i
                    st.session_state.lab_code = (
                        lab["problems"][i].get("starter_code") or DEFAULT_STARTER_CODE
                    )
                    st.session_state.lab_last_result = None
                    st.rerun()

        left, right = st.columns([1, 1])
        with left:
            diff_cls = problem["difficulty"].lower()
            st.markdown(
                f'<div class="tp-card-dark">'
                f'<h2 style="margin:0; color:white;">{problem["title"]} '
                f'<span class="badge badge-{diff_cls}">{problem["difficulty"]}</span></h2>'
                f'<div style="color:#94a3b8;font-size:12px;margin-top:4px;">'
                f'⏱ {problem.get("time_limit_s",3)}s · 🧠 {problem.get("memory_limit_mb",64)} MB '
                f'· 💯 {problem.get("total_points",0)} pts</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(problem.get("statement", ""))
            sample = (problem.get("samples") or [{}])[0]
            if sample.get("input"):
                st.caption("Sample input")
                st.code(sample["input"], language="text")
            if sample.get("expected_output"):
                st.caption("Sample output")
                st.code(sample["expected_output"], language="text")
            history = get_data_manager().get_lab_submissions(
                username=st.session_state.username,
                problem_id=problem["problem_id"],
            )
            if history:
                st.markdown("##### Past attempts")
                for h in history[:5]:
                    ts = pd.to_datetime(h["timestamp"], unit="s").strftime("%H:%M:%S")
                    pct = (
                        int(100 * h["score"] / h["max_score"])
                        if h.get("max_score") else 0
                    )
                    cls = "verified" if pct == 100 else ("warning" if pct > 0 else "flagged")
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;'>"
                        f"<span>{ts} · {h['score']}/{h['max_score']}</span>"
                        f"<span class='badge badge-{cls}'>{pct}%</span></div>",
                        unsafe_allow_html=True,
                    )

        with right:
            payload = tp_widget(
                widget_type="lab_session",
                problem_id=problem["problem_id"],
                problem_title=problem["title"],
                language="C++17",
                starter_code=problem.get("starter_code") or DEFAULT_STARTER_CODE,
                code=st.session_state.lab_code or problem.get("starter_code") or DEFAULT_STARTER_CODE,
                time_limit=int(problem.get("time_limit_s", 3)),
                memory_limit=int(problem.get("memory_limit_mb", 0) or 0),
                last_result=st.session_state.lab_last_result,
                last_stdin=(problem.get("samples") or [{}])[0].get("input", ""),
                last_confidence=(
                    st.session_state.auth_log[-1]["confidence"]
                    if st.session_state.auth_log else None
                ),
                check_interval_ms=30_000,
                key=f"lab_session_{problem['problem_id']}",
            )
            if _handle_payload(payload):
                st.rerun()

    _student_layout(_content)


# ── Student: Submission success ──────────────────────────────────────────────
def show_submission_success() -> None:
    """Post-submission summary screen with integrity breakdown."""
    def _content():
        dm = get_data_manager()
        exam = dm.get_exam(st.session_state.active_exam_id) or {}
        sub = dm.get_exam_submission(st.session_state.username, exam.get("exam_id", ""))
        if not sub:
            _empty("📭", "No submission found", "We couldn't find a submission for this exam yet.", dark=True)
            if st.button("← Back to courses"):
                _goto("courses")
            return
        integrity = sub.get("integrity") or {"integrity_score": 0, "grade": "N/A"}
        avg_conf = sub.get("avg_conf", 0)
        st.markdown(
            f'<div class="success-card">'
            f'<div class="success-icon" style="font-size:48px">✅</div>'
            f'<h2>Submission received!</h2>'
            f'<p>{exam.get("title","Exam")}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        score = integrity["integrity_score"]
        score_accent = "green" if score >= 70 else "amber" if score >= 40 else "red"
        mcqs = [q for q in exam.get("questions", []) if q.get("type") == "MCQ"]
        mcq_total = sum(int(q.get("marks", 0)) for q in mcqs)
        c = st.columns(4 if mcqs else 3)
        if mcqs:
            c.pop(0).markdown(
                _metric("🎯", "Your Score", f"{sub.get('score', 0)}/{mcq_total}", "green", dark=True),
                unsafe_allow_html=True,
            )
        c[0].markdown(
            _metric("🛡️", "Integrity Score", f"{score:.0f}%", score_accent, dark=True, delta=integrity["grade"]),
            unsafe_allow_html=True,
        )
        c[1].markdown(
            _metric("🔐", "Avg Auth Confidence", f"{avg_conf*100:.0f}%", "indigo", dark=True),
            unsafe_allow_html=True,
        )
        c[2].markdown(
            _metric("📋", "Paste Events", str(sub.get('cp_count', 0)), "cyan", dark=True),
            unsafe_allow_html=True,
        )
        if mcqs:
            st.markdown("##### Question results")
            for i, q in enumerate(mcqs, 1):
                chosen = (sub.get("answers", {}).get(q["q_id"], "") or "").upper()[:1]
                right = bool(chosen) and chosen == (q.get("correct") or "").upper()[:1]
                st.markdown(
                    f"<div class='{'tc-pass' if right else 'tc-fail'}'>Q{i} — "
                    f"{'✅ correct' if right else ('❌ wrong' if chosen else '➖ not answered')}"
                    f" · {q.get('marks', 0) if right else 0}/{q.get('marks', 0)} marks</div>",
                    unsafe_allow_html=True,
                )
        if st.button("← Back to courses"):
            _goto("courses")
    _student_layout(_content)


# ── Main router ──────────────────────────────────────────────────────────────
def main() -> None:
    """Entry point — apply pending nav, then dispatch by role + page."""
    _apply_pending_page()
    if not st.session_state.authenticated:
        show_login_page()
        return
    role = st.session_state.role
    page = st.session_state.page
    if role == "faculty":
        if page == "overview":   show_faculty_overview()
        elif page == "exams":    show_faculty_exams()
        elif page == "lab":     show_faculty_lab()
        elif page == "students": show_faculty_students()
        elif page == "reports":  show_faculty_reports()
        elif page == "settings": show_faculty_settings()
        else:                    show_faculty_overview()
    else:
        if page == "courses":      show_student_courses()
        elif page == "course_detail": show_student_course_detail()
        elif page == "exam_verify":   show_exam_verification()
        elif page == "exam_portal":   show_exam_portal()
        elif page == "lab_portal":    show_lab_portal()
        elif page == "submitted":     show_submission_success()
        else:                          show_student_courses()


if __name__ == "__main__":
    main()
