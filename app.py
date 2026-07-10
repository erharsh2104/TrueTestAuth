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

import base64
import io
import json
import os
import time
import uuid
from datetime import date, datetime, time as dtime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from compiler import CppCompiler, grade_submission
from data_manager import DEFAULT_STARTER_CODE, DataManager
from ml_model import AUTH_THRESHOLD, BehavioralAuthModel


# ── Constants ────────────────────────────────────────────────────────────────
PHRASE: str = "the quick brown fox jumps"
ENROLL_TARGET: int = 10
LOW_CONFIDENCE: float = 0.45
AMBER_CONFIDENCE: float = 0.65

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH: str = os.path.join(ROOT_DIR, "models", "behavioral_auth_model.pkl")
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
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Hide ALL Streamlit default chrome & Remove padding ────────────────────── */
#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stHeader"],
[data-testid="stRunningMan"],
.stHeader,
.stDeployButton,
.reportview-container .main footer,
div[data-testid="stToolbar"] { display: none !important; visibility: hidden !important; height: 0 !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* Kill massive top spacing */
.main .block-container,
div.block-container,
[data-testid="stAppViewBlockContainer"],
.stAppViewBlockContainer { 
    padding-top: 1rem !important; 
    padding-bottom: 0 !important; 
    padding-left: 0 !important; 
    padding-right: 0 !important; 
    margin-top: 0 !important;
    max-width: 100% !important; 
}
/* Kill any remaining top chrome/padding */
.stApp > header { display: none !important; height: 0 !important; }
.stApp { margin-top: 0 !important; padding-top: 0 !important; }
[data-testid="stAppViewContainer"] { margin-top: 0 !important; padding-top: 0 !important; }
/* Hide the Streamlit top connection status bar */
.stApp > div:first-child:not([data-testid="stAppViewContainer"]) {
    display: none !important; height: 0 !important; overflow: hidden !important;
}
/* Force hide any fixed-position Streamlit elements at top */
.stApp > div[style*="position: fixed"],
.stApp > div[class*="StatusWidget"] { display: none !important; }

/* CSS custom properties for design tokens */
:root {
    --brand: #5b5ef4;
    --brand-dark: #4338ca;
    --brand-light: #eef2ff;
    --brand-glow: rgba(91,94,244,0.35);
    --surface: #ffffff;
    --surface-2: #f8fafc;
    --surface-3: #f1f5f9;
    --border: #e2e8f0;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --navy: #0c1220;
    --navy-2: #111827;
    --navy-3: #1e293b;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    --shadow-lg: 0 10px 30px rgba(0,0,0,0.1), 0 4px 8px rgba(0,0,0,0.05);
    --shadow-brand: 0 8px 24px rgba(91,94,244,0.3);
}

/* Fix font without breaking Streamlit material icons */
html, body, .stApp { 
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important; 
}

/* ── Login screen ──────────────────────────────────────────────────────── */
.login-bg {
    position: fixed;
    inset: 0;
    background: linear-gradient(150deg, #060d1f 0%, #0d1535 40%, #12092e 75%, #060d1f 100%);
    z-index: -2;
    overflow: hidden;
}
/* Subtle grid overlay */
.login-bg::after {
    content: '';
    position: fixed;
    inset: 0;
    background-image: 
        linear-gradient(rgba(91,94,244,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(91,94,244,0.04) 1px, transparent 1px);
    background-size: 48px 48px;
    z-index: -1;
}
.orb {
    position: fixed;
    border-radius: 50%;
    filter: blur(90px);
    opacity: 0.35;
    z-index: -1;
}
.orb-1 { width: 500px; height: 500px; background: radial-gradient(circle, #5b5ef4 0%, #3730a3 100%);
         top: -160px; left: -140px;
         animation: float1 16s ease-in-out infinite; }
.orb-2 { width: 400px; height: 400px; background: radial-gradient(circle, #8b5cf6 0%, #6d28d9 100%);
         bottom: -140px; right: -120px;
         animation: float2 20s ease-in-out infinite; }
.orb-3 { width: 320px; height: 320px; background: radial-gradient(circle, #06b6d4 0%, #0e7490 100%);
         top: 45%; right: 22%;
         animation: float3 26s ease-in-out infinite; }
@keyframes float1 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(55px,-35px) scale(1.06)} }
@keyframes float2 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(-45px,45px) scale(0.94)} }
@keyframes float3 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(38px,28px)} }

.login-shell { min-height: 100vh; display: flex; align-items: flex-start; justify-content: center;
               padding: 30px 1rem 2rem 1rem; }
.login-card { width: 490px; max-width: calc(100vw - 2rem);
              background: rgba(255,255,255,0.055);
              backdrop-filter: blur(32px);
              -webkit-backdrop-filter: blur(32px);
              border: 1px solid rgba(255,255,255,0.10);
              border-radius: 28px;
              padding: 38px 40px;
              box-shadow: 0 40px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08); }

/* Remove ugly form border inside login card */
.login-card [data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
    background: none !important;
    box-shadow: none !important;
}
.login-card [data-testid="stFormSubmitButton"] button {
    width: 100% !important;
    height: 52px !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    letter-spacing: 0.01em !important;
    background: linear-gradient(135deg, #5b5ef4 0%, #7c3aed 100%) !important;
    color: white !important;
    border: none !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
    margin-top: 10px !important;
    box-shadow: 0 6px 20px rgba(91,94,244,0.4) !important;
}
.login-card [data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 14px 32px rgba(91,94,244,0.5) !important;
}

.login-logo { display: flex; align-items: center; gap: 14px; margin-bottom: 8px; }
.login-logo svg { width: 36px; height: 36px; color: #818cf8; }
.login-logo span { color: white; font-size: 26px; font-weight: 800; letter-spacing: -0.03em; }
.login-tagline { color: rgba(255,255,255,0.45); font-size: 12.5px; margin-bottom: 28px; letter-spacing: 0.01em; }
.login-card h3 { color: white; font-weight: 700; font-size: 18px; margin: 0 0 18px 0; letter-spacing: -0.01em; }
.login-card label { color: rgba(255,255,255,0.70) !important; font-size: 13px !important; font-weight: 500 !important; }
.login-card .stTextInput > div > div > input,
.login-card .stTextInput input {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.13) !important;
    border-radius: 12px !important;
    color: white !important;
    padding: 13px 16px !important;
    font-size: 14px !important;
    transition: border-color 0.2s, background 0.2s, box-shadow 0.2s !important;
}
.login-card .stTextInput > div > div > input:focus,
.login-card .stTextInput input:focus {
    background: rgba(255,255,255,0.10) !important;
    border-color: rgba(91,94,244,0.7) !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.18) !important;
}
.login-card .stTextInput > div > div > input::placeholder { color: rgba(255,255,255,0.3) !important; }
.login-card [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.13) !important;
    border-radius: 12px !important;
    color: white !important;
    transition: border-color 0.2s !important;
}
.role-pill-tabs { display: flex; gap: 8px; background: rgba(255,255,255,0.05);
                  padding: 4px; border-radius: 16px; margin-bottom: 18px; }
.role-back { color: rgba(255,255,255,0.5); font-size: 13px; text-align: center; margin-top: 18px; }
.tiny-help { color: rgba(255,255,255,0.38); font-size: 12px; text-align: center;
             margin-top: 14px; line-height: 1.6; }

/* Buttons (login screen variant) ─────────────────────────────────────── */
.login-card .stButton > button {
    width: 100% !important;
    height: 52px !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    letter-spacing: 0.01em !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.2s ease !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    background: linear-gradient(135deg, #5b5ef4 0%, #7c3aed 100%) !important;
    color: white !important;
    box-shadow: 0 4px 14px rgba(91,94,244,0.35) !important;
}
.login-card .stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 30px rgba(91,94,244,0.48) !important;
}
.login-card .stButton[data-variant="ghost"] > button,
.login-card .stButton.ghost > button {
    background: rgba(255,255,255,0.06) !important;
    color: rgba(255,255,255,0.8) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    box-shadow: none !important;
}

/* Faculty layout ───────────────────────────────────────────────────────── */
.faculty-shell { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; background: #f1f5f9; }
div[data-testid="column"]:has(.faculty-sidebar) {
    background: #0c1220;
    min-height: 100vh;
    border-right: 1px solid #1a2540;
}
.faculty-sidebar { padding: 24px 16px;
                   color: #e2e8f0; position: sticky; top: 0; }
.faculty-sidebar .brand { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.faculty-sidebar .brand svg { color: #818cf8; width: 26px; height: 26px; }
.faculty-sidebar .brand span { color: white; font-weight: 800; font-size: 17px; letter-spacing: -0.02em; }
.faculty-sidebar .who { color: #e2e8f0; font-size: 13.5px; font-weight: 600; margin-top: 14px; }
.faculty-sidebar .course-pill { display: inline-block; background: rgba(91,94,244,0.2);
                                color: #a5b4fc; padding: 4px 10px; border-radius: 999px;
                                font-size: 11px; margin-top: 6px; font-weight: 500;
                                border: 1px solid rgba(91,94,244,0.25); }
.faculty-sidebar hr { border: 0; border-top: 1px solid rgba(255,255,255,0.06); margin: 18px 0; }
.faculty-content { padding: 32px 40px; background: #f1f5f9; min-height: 100vh; }

.tp-title { font-size: 28px; font-weight: 800; color: #0f172a; margin: 0 0 6px 0; letter-spacing: -0.03em; }
.tp-sub   { color: #64748b; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }
.tp-title-dark { font-size: 28px; font-weight: 800; color: white; margin: 0 0 6px 0; letter-spacing: -0.03em; }
.tp-sub-dark { font-size: 14px; color: #94a3b8; margin: 0; line-height: 1.5; }

/* Metric cards ─────────────────────────────────────────────────────────── */
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }
.metric-card { background: white; border-radius: var(--radius-lg); padding: 22px;
               border: 1px solid #edf2f7; box-shadow: var(--shadow-sm);
               transition: box-shadow 0.22s ease, transform 0.22s ease; position: relative; overflow: hidden; }
.metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
                        background: linear-gradient(90deg, #5b5ef4, #7c3aed); opacity: 0; transition: opacity 0.22s; }
.metric-card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.metric-card:hover::before { opacity: 1; }
.metric-card .label { font-size: 11.5px; color: #64748b; text-transform: uppercase;
                      letter-spacing: 0.07em; margin-bottom: 8px; font-weight: 600; }
.metric-card .value { font-size: 32px; font-weight: 800; color: #0f172a; letter-spacing: -0.03em; line-height: 1; }
.metric-card .delta { font-size: 12px; color: #16a34a; margin-top: 6px; font-weight: 500; }

.metric-card-dark { background: rgba(255,255,255,0.04); border-radius: var(--radius-lg); padding: 22px;
               border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 2px 8px rgba(0,0,0,0.2);
               transition: box-shadow 0.22s ease, transform 0.22s ease; color: white;
               position: relative; overflow: hidden; }
.metric-card-dark::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
                        background: linear-gradient(90deg, #5b5ef4, #818cf8); opacity: 0; transition: opacity 0.22s; }
.metric-card-dark:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.3); transform: translateY(-2px); }
.metric-card-dark:hover::before { opacity: 1; }
.metric-card-dark .label { font-size: 11.5px; color: #64748b; text-transform: uppercase;
                      letter-spacing: 0.07em; margin-bottom: 8px; font-weight: 600; }
.metric-card-dark .value { font-size: 32px; font-weight: 800; color: white; letter-spacing: -0.03em; line-height: 1; }
.metric-card-dark .delta { font-size: 12px; color: #4ade80; margin-top: 6px; font-weight: 500; }

.tp-card { background: white; border: 1px solid #edf2f7; border-radius: var(--radius-lg);
           padding: 22px; box-shadow: var(--shadow-sm); margin-bottom: 16px;
           transition: box-shadow 0.2s ease; }
.tp-card:hover { box-shadow: var(--shadow-md); }
.tp-card-dark { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
                border-radius: var(--radius-lg);
                padding: 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); margin-bottom: 16px; color: white;
                transition: box-shadow 0.2s ease; }
.tp-card-dark:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.3); }

/* Sidebar nav buttons ───────────────────────────────────────────────────── */
.faculty-sidebar-wrapper .stButton > button, div[data-testid="column"]:has(.faculty-sidebar) .stButton > button {
    width: 100% !important;
    text-align: left !important;
    background: transparent !important;
    color: #94a3b8 !important;
    border: 0 !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 10px 10px 0 !important;
    padding: 11px 14px !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    margin-bottom: 2px !important;
    height: auto !important;
    transition: background 0.15s, color 0.15s !important;
}
.faculty-sidebar-wrapper .stButton > button:hover, div[data-testid="column"]:has(.faculty-sidebar) .stButton > button:hover {
    background: rgba(255,255,255,0.06) !important; color: white !important;
    border-left: 3px solid rgba(129,140,248,0.4) !important;
}
.faculty-sidebar-wrapper .stButton.active > button, div[data-testid="column"]:has(.faculty-sidebar) .stButton.active > button {
    background: rgba(91,94,244,0.15) !important;
    color: #a5b4fc !important;
    border-left: 3px solid #5b5ef4 !important;
    font-weight: 600 !important;
}
.faculty-sidebar-wrapper .logout .stButton > button, div[data-testid="column"]:has(.faculty-sidebar) .logout .stButton > button {
    background: rgba(239,68,68,0.08) !important;
    color: #fca5a5 !important;
    border-radius: 10px !important;
    text-align: center !important;
    border-left: 3px solid transparent !important;
}
.faculty-sidebar-wrapper .logout .stButton > button:hover, div[data-testid="column"]:has(.faculty-sidebar) .logout .stButton > button:hover {
    background: rgba(239,68,68,0.15) !important;
    color: #f87171 !important;
}

/* Student navbar ────────────────────────────────────────────────────────── */
.student-shell { background: #0c1220; min-height: 100vh; }
.student-shell ~ div,
.student-shell + div { background: #0c1220 !important; }
.student-navbar { background: rgba(15,23,42,0.95); border-bottom: 1px solid rgba(255,255,255,0.07);
                  padding: 14px 36px; display: flex; align-items: center; justify-content: space-between;
                  position: sticky; top: 0; z-index: 100;
                  backdrop-filter: blur(12px);
                  box-shadow: 0 1px 12px rgba(0,0,0,0.3); }
.student-navbar .brand { display: flex; align-items: center; gap: 10px; }
.student-navbar .brand svg { width: 28px; height: 28px; color: #6366f1; }
.student-navbar .brand b { font-weight: 800; font-size: 17px; color: white; letter-spacing: -0.02em; }
.student-navbar .greet { color: #64748b; font-size: 14px; }
.student-navbar .enroll-pill { background: rgba(91,94,244,0.15); color: #a5b4fc; padding: 4px 10px;
                               border-radius: 999px; font-size: 11px; margin-left: 8px; font-weight: 600;
                               border: 1px solid rgba(91,94,244,0.25); }
.avatar { width: 36px; height: 36px; border-radius: 50%;
          background: linear-gradient(135deg, #5b5ef4, #7c3aed);
          color: white; font-weight: 700; display: inline-flex; align-items: center;
          justify-content: center; font-size: 13px; box-shadow: 0 2px 8px rgba(91,94,244,0.35); }
.student-content { padding: 32px 40px; }

/* Course cards ──────────────────────────────────────────────────────────── */
.course-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 20px; }
.course-card { background: rgba(255,255,255,0.05); border-radius: var(--radius-xl); padding: 24px;
               border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 2px 10px rgba(0,0,0,0.2);
               transition: box-shadow 0.22s ease, transform 0.22s ease, border-color 0.22s ease; cursor: pointer; }
.course-card:hover { box-shadow: 0 12px 36px rgba(0,0,0,0.35); transform: translateY(-3px);
                     border-color: rgba(91,94,244,0.35); }
.course-card .head { display: flex; gap: 14px; align-items: center; margin-bottom: 14px; }
.course-card .head .avatar { width: 46px; height: 46px; font-size: 17px; border-radius: 14px; }
.course-card .name { font-size: 13px; color: #64748b; font-weight: 500; }
.course-card .course { font-size: 16px; font-weight: 700; color: white; margin-top: 2px; letter-spacing: -0.01em; }
.course-card .stats { display: flex; gap: 10px; margin-top: 16px; }
.course-card .stats b { color: white; font-size: 14px; display: block; font-weight: 700; }
.course-card-dark { background: rgba(255,255,255,0.04); border-radius: var(--radius-xl); padding: 24px;
               border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 2px 10px rgba(0,0,0,0.2);
               transition: box-shadow 0.22s ease, transform 0.22s ease, border-color 0.22s ease; cursor: pointer; }
.course-card-dark:hover { box-shadow: 0 12px 36px rgba(0,0,0,0.35); transform: translateY(-3px);
                     border-color: rgba(91,94,244,0.3); }

/* Status badges ─────────────────────────────────────────────────────────── */
.badge { padding: 4px 12px; border-radius: 99px; font-size: 11.5px; font-weight: 700;
         display: inline-block; letter-spacing: 0.04em; }
.badge-verified  { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
.badge-warning   { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.25); }
.badge-flagged   { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.25); }
.badge-easy      { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.2); }
.badge-medium    { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.2); }
.badge-hard      { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.2); }
.badge-upcoming  { background: rgba(91,94,244,0.15); color: #a5b4fc; border: 1px solid rgba(91,94,244,0.25); }
.badge-active    { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
.badge-ended     { background: rgba(100,116,139,0.15); color: #94a3b8; border: 1px solid rgba(100,116,139,0.2); }

/* Auth dot ──────────────────────────────────────────────────────────────── */
@keyframes auth-pulse { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.3);opacity:0.7} }
.auth-dot { width:10px; height:10px; border-radius:50%; display:inline-block; animation: auth-pulse 2s ease-in-out infinite; }
.auth-dot.green  { background: #22c55e; }
.auth-dot.amber  { background: #f59e0b; }
.auth-dot.red    { background: #ef4444; }

/* Exam timer ─────────────────────────────────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.55} }
.exam-timer { font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700;
              color: #1e293b; }
.exam-timer.warning { color: #ef4444; animation: pulse 1.1s ease-in-out infinite; }

/* Q-navigator dots ───────────────────────────────────────────────────────── */
.qnav-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
.qnav-dot { aspect-ratio: 1/1; border-radius: 8px; background: #e2e8f0; color: #64748b;
            display: flex; align-items: center; justify-content: center; font-size: 12px;
            font-weight: 600; }
.qnav-dot.answered { background: #dcfce7; color: #166534; }
.qnav-dot.flagged  { background: #fee2e2; color: #991b1b; }

/* Conf gauge ─────────────────────────────────────────────────────────────── */
.conf-gauge { position: relative; width: 160px; height: 160px; margin: 0 auto; }
.conf-gauge .num { position: absolute; inset: 0; display: flex; align-items: center;
                   justify-content: center; font-size: 28px; font-weight: 800; color: #1e1b4b; }

/* Auth dot ──────────────────────────────────────────────────────────────── */
@keyframes auth-pulse { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.3);opacity:0.7} }
.auth-dot { width:10px; height:10px; border-radius:50%; display:inline-block; animation: auth-pulse 2s ease-in-out infinite; }
.auth-dot.green  { background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.5); }
.auth-dot.amber  { background: #f59e0b; box-shadow: 0 0 8px rgba(245,158,11,0.5); }
.auth-dot.red    { background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,0.5); }

/* Exam timer ─────────────────────────────────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
.exam-timer { font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 700;
              color: #1e293b; letter-spacing: 0.05em; }
.exam-timer.warning { color: #ef4444; animation: pulse 1s ease-in-out infinite; }

/* Q-navigator dots ───────────────────────────────────────────────────────── */
.qnav-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; }
.qnav-dot { aspect-ratio: 1/1; border-radius: 10px; background: rgba(255,255,255,0.06);
            color: #64748b; border: 1px solid rgba(255,255,255,0.08);
            display: flex; align-items: center; justify-content: center; font-size: 12px;
            font-weight: 600; transition: background 0.15s, color 0.15s; }
.qnav-dot.answered { background: rgba(34,197,94,0.15); color: #4ade80;
                     border-color: rgba(34,197,94,0.25); }
.qnav-dot.flagged  { background: rgba(239,68,68,0.15); color: #f87171;
                     border-color: rgba(239,68,68,0.25); }

/* Conf gauge ─────────────────────────────────────────────────────────────── */
.conf-gauge { position: relative; width: 160px; height: 160px; margin: 0 auto; }
.conf-gauge .num { position: absolute; inset: 0; display: flex; align-items: center;
                   justify-content: center; font-size: 30px; font-weight: 800; color: white; }

/* Faculty primary buttons ───────────────────────────────────────────────── */
.faculty-content .stButton > button {
    background: linear-gradient(135deg, #5b5ef4 0%, #7c3aed 100%);
    color: white; border: 0; border-radius: var(--radius-md);
    padding: 10px 20px; font-weight: 600; font-size: 13.5px; letter-spacing: 0.01em;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    box-shadow: 0 2px 8px rgba(91,94,244,0.25);
}
.faculty-content .stButton > button:hover {
    transform: translateY(-2px); box-shadow: 0 10px 24px rgba(91,94,244,0.4);
}

/* Student content buttons */
.student-content .stButton > button {
    background: linear-gradient(135deg, #5b5ef4 0%, #7c3aed 100%);
    color: white; border: 0; border-radius: var(--radius-md);
    padding: 10px 20px; font-weight: 600; font-size: 13.5px; letter-spacing: 0.01em;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    box-shadow: 0 2px 8px rgba(91,94,244,0.25);
}
.student-content .stButton > button:hover {
    transform: translateY(-2px); box-shadow: 0 10px 24px rgba(91,94,244,0.4);
}

/* Step indicator ─────────────────────────────────────────────────────────── */
.step-bar { display: flex; align-items: center; gap: 0; margin-bottom: 28px; }
.step-item { display: flex; flex-direction: column; align-items: center; flex: 1; position: relative; }
.step-item:not(:last-child)::after {
    content: ''; position: absolute; top: 17px; left: calc(50% + 18px);
    width: calc(100% - 36px); height: 2px; background: rgba(255,255,255,0.1);
    z-index: 0;
}
.step-item.done:not(:last-child)::after { background: #5b5ef4; }
.step-circle { width: 34px; height: 34px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.15);
               background: rgba(255,255,255,0.05); display: flex; align-items: center;
               justify-content: center; font-size: 12px; font-weight: 700; color: #64748b;
               z-index: 1; transition: all 0.25s ease; }
.step-item.done .step-circle { background: #5b5ef4; border-color: #5b5ef4; color: white;
                                box-shadow: 0 0 0 4px rgba(91,94,244,0.2); }
.step-item.active .step-circle { border-color: #818cf8; color: #818cf8;
                                  box-shadow: 0 0 0 4px rgba(91,94,244,0.15); }
.step-label { font-size: 11px; color: #64748b; margin-top: 6px; font-weight: 500; white-space: nowrap; }
.step-item.done .step-label { color: #a5b4fc; }
.step-item.active .step-label { color: white; font-weight: 600; }

/* Registration enrollment card ──────────────────────────────────────────── */
.enroll-card { background: rgba(255,255,255,0.04); border-radius: var(--radius-xl);
               padding: 28px; border: 1px solid rgba(255,255,255,0.08);
               box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
.enroll-card h3 { color: white; font-size: 18px; font-weight: 700; margin: 0 0 8px 0; letter-spacing: -0.01em; }
.enroll-card p { color: #64748b; font-size: 13.5px; margin: 0 0 20px 0; line-height: 1.6; }

/* Keystroke progress bars ───────────────────────────────────────────────── */
.ks-bar-wrap { background: rgba(255,255,255,0.06); border-radius: 99px; height: 8px;
               overflow: hidden; margin: 6px 0; }
.ks-bar-fill { height: 100%; border-radius: 99px;
               background: linear-gradient(90deg, #5b5ef4, #818cf8);
               transition: width 0.4s cubic-bezier(0.4,0,0.2,1); }
.ks-bar-fill.amber { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.ks-bar-fill.green { background: linear-gradient(90deg, #22c55e, #4ade80); }

/* Exam page ─────────────────────────────────────────────────────────────── */
.exam-header { background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.07);
               padding: 16px 28px; display: flex; align-items: center;
               justify-content: space-between; gap: 16px; }
.exam-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px;
              border-radius: 99px; font-size: 12px; font-weight: 600; border: 1px solid; }

/* Submission success card ───────────────────────────────────────────────── */
@keyframes pop-in { 0%{transform:scale(0.8);opacity:0} 70%{transform:scale(1.05)} 100%{transform:scale(1);opacity:1} }
.success-icon { animation: pop-in 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards; }
.success-card { background: rgba(34,197,94,0.06); border: 1px solid rgba(34,197,94,0.2);
                border-radius: var(--radius-xl); padding: 36px; text-align: center; }
.success-card h2 { color: #4ade80; font-size: 24px; font-weight: 800; margin: 16px 0 8px;
                   letter-spacing: -0.02em; }
.success-card p { color: #94a3b8; font-size: 14px; margin: 0; line-height: 1.6; }

/* Alert / info boxes ────────────────────────────────────────────────────── */
.tp-alert { padding: 14px 18px; border-radius: var(--radius-md); margin-bottom: 16px;
            display: flex; align-items: flex-start; gap: 12px; font-size: 13.5px; }
.tp-alert-info { background: rgba(91,94,244,0.10); border: 1px solid rgba(91,94,244,0.2); color: #a5b4fc; }
.tp-alert-warn { background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.2); color: #fbbf24; }
.tp-alert-danger { background: rgba(239,68,68,0.10); border: 1px solid rgba(239,68,68,0.2); color: #f87171; }
.tp-alert-success { background: rgba(34,197,94,0.10); border: 1px solid rgba(34,197,94,0.2); color: #4ade80; }

/* Empty state ────────────────────────────────────────────────────────────── */
.empty-state { text-align: center; padding: 48px 24px; }
.empty-state .icon { font-size: 40px; margin-bottom: 12px; opacity: 0.5; }
.empty-state h4 { color: #94a3b8; font-size: 16px; font-weight: 600; margin: 0 0 6px 0; }
.empty-state p { color: #64748b; font-size: 13px; margin: 0; line-height: 1.6; }

/* Tables ────────────────────────────────────────────────────────────────── */
.stDataFrame { border-radius: var(--radius-lg) !important; overflow: hidden !important;
               border: 1px solid #e2e8f0 !important; box-shadow: var(--shadow-sm) !important; }
.stDataFrame [data-testid="stDataFrameResizable"] { border-radius: var(--radius-lg) !important; }

/* Select boxes ──────────────────────────────────────────────────────────── */
.faculty-content [data-baseweb="select"] > div {
    border-radius: var(--radius-md) !important;
    border-color: #e2e8f0 !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.faculty-content [data-baseweb="select"] > div:focus-within {
    border-color: #5b5ef4 !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.12) !important;
}
.student-content [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: var(--radius-md) !important;
    color: white !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.student-content [data-baseweb="select"] > div:focus-within {
    border-color: rgba(91,94,244,0.6) !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.15) !important;
}

/* Text inputs (light) ───────────────────────────────────────────────────── */
.faculty-content .stTextInput > div > div > input,
.faculty-content .stTextInput input {
    border-radius: var(--radius-md) !important;
    border-color: #e2e8f0 !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.faculty-content .stTextInput > div > div > input:focus,
.faculty-content .stTextInput input:focus {
    border-color: #5b5ef4 !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.12) !important;
}

/* Text inputs (dark) ────────────────────────────────────────────────────── */
.student-content .stTextInput > div > div > input,
.student-content .stTextInput input {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: var(--radius-md) !important;
    color: white !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.student-content .stTextInput > div > div > input:focus,
.student-content .stTextInput input:focus {
    border-color: rgba(91,94,244,0.6) !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.15) !important;
}
.student-content .stTextInput > div > div > input::placeholder { color: #475569 !important; }

/* Text areas (dark) ─────────────────────────────────────────────────────── */
.student-content .stTextArea textarea {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: var(--radius-md) !important;
    color: white !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.student-content .stTextArea textarea:focus {
    border-color: rgba(91,94,244,0.6) !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.12) !important;
}

/* Expander ──────────────────────────────────────────────────────────────── */
.faculty-content [data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important; border-radius: var(--radius-lg) !important;
    overflow: hidden !important; transition: box-shadow 0.2s !important;
}
.faculty-content [data-testid="stExpander"]:hover { box-shadow: var(--shadow-sm) !important; }
.student-content [data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: var(--radius-lg) !important; overflow: hidden !important;
}

/* Tabs ──────────────────────────────────────────────────────────────────── */
.student-content [data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04) !important; border-radius: 12px !important;
    padding: 4px !important; gap: 4px !important;
    border-bottom: none !important;
}
.student-content [data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 8px !important; padding: 8px 16px !important;
    font-weight: 500 !important; font-size: 13.5px !important;
    color: #64748b !important; background: transparent !important;
    border: none !important; transition: background 0.15s, color 0.15s !important;
}
.student-content [data-testid="stTabs"] [aria-selected="true"] {
    background: rgba(91,94,244,0.2) !important; color: #a5b4fc !important; font-weight: 600 !important;
}

/* Code editor textareas (lab) ────────────────────────────────────────────── */
div[data-testid="stTextArea"] textarea[aria-label="cpp_editor"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 14px !important; line-height: 1.75 !important;
    background: #1a1b26 !important; color: #c0caf5 !important;
    border: 1px solid #2a2b3d !important; border-radius: var(--radius-md) !important;
    padding: 18px !important; caret-color: #c0caf5 !important;
    min-height: 340px !important;
}
div[data-testid="stTextArea"] textarea[aria-label="cpp_editor"]:focus {
    border-color: #5b5ef4 !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,0.15) !important;
}

/* Terminal output ────────────────────────────────────────────────────────── */
.terminal { background: #0d1117; color: #3fb950; font-family: 'JetBrains Mono', monospace;
            font-size: 13px; padding: 18px; border-radius: var(--radius-md);
            border: 1px solid #21262d; min-height: 64px;
            white-space: pre-wrap; word-break: break-all; line-height: 1.65;
            box-shadow: inset 0 2px 8px rgba(0,0,0,0.3); }
.terminal-error { color: #f85149; }

/* Test case results ─────────────────────────────────────────────────────── */
.tc-pass { background: rgba(22,163,74,0.08); border-left: 3px solid #16a34a; padding: 10px 14px;
           margin: 4px 0; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
           font-size: 13px; color: #4ade80; }
.tc-fail { background: rgba(239,68,68,0.08); border-left: 3px solid #ef4444; padding: 10px 14px;
           margin: 4px 0; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
           font-size: 13px; color: #f87171; }

/* Scrollbar (webkit) ────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(148,163,184,0.3); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,0.5); }

/* Dividers ──────────────────────────────────────────────────────────────── */
.faculty-content hr { border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0; }
.student-content hr { border: 0; border-top: 1px solid rgba(255,255,255,0.07); margin: 20px 0; }

/* Streamlit form border fix ────────────────────────────────────────────── */
.faculty-content [data-testid="stForm"],
.student-content [data-testid="stForm"] {
    border: none !important; padding: 0 !important;
    background: none !important; box-shadow: none !important;
}

/* Spinner overlay ───────────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: #5b5ef4 !important; }

/* ══════════════════════════════════════════════════════════════════════════
   VISUAL REFRESH — decorative backgrounds, icon metric cards, page headers,
   rich empty states, progress rings, sidebar polish.
   ══════════════════════════════════════════════════════════════════════════ */

/* Decorative ambient backgrounds (kept subtle so text stays readable) ────── */
.faculty-content {
    background:
        radial-gradient(620px circle at 96% -8%, rgba(91,94,244,0.09), transparent 60%),
        radial-gradient(560px circle at -6% 8%, rgba(124,58,237,0.06), transparent 55%),
        radial-gradient(480px circle at 60% 115%, rgba(6,182,212,0.05), transparent 55%),
        #f1f5f9 !important;
    background-attachment: fixed !important;
}
.student-content {
    background:
        radial-gradient(620px circle at 96% -10%, rgba(91,94,244,0.16), transparent 55%),
        radial-gradient(560px circle at -8% 30%, rgba(124,58,237,0.10), transparent 55%) !important;
}

/* Page header (icon badge + title + subtitle) ─────────────────────────────── */
.page-header { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 28px; }
.page-header .icon-badge {
    width: 50px; height: 50px; border-radius: 15px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 23px;
    background: linear-gradient(135deg, #5b5ef4 0%, #7c3aed 100%);
    box-shadow: 0 8px 20px rgba(91,94,244,0.30);
}
.page-header .ph-text h1 { margin: 2px 0 4px 0 !important; }
.page-header .ph-text p { margin: 0 !important; }

/* Icon metric cards ─────────────────────────────────────────────────────── */
.metric-card .m-top, .metric-card-dark .m-top {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.metric-card .m-icon, .metric-card-dark .m-icon {
    width: 36px; height: 36px; border-radius: 11px; display: flex; align-items: center;
    justify-content: center; font-size: 16px; flex-shrink: 0;
}
.metric-card.accent-indigo .m-icon { background: rgba(91,94,244,0.12); color: #4f46e5; }
.metric-card.accent-green  .m-icon { background: rgba(34,197,94,0.12); color: #16a34a; }
.metric-card.accent-amber  .m-icon { background: rgba(245,158,11,0.14); color: #b45309; }
.metric-card.accent-red    .m-icon { background: rgba(239,68,68,0.12); color: #dc2626; }
.metric-card.accent-cyan   .m-icon { background: rgba(6,182,212,0.12); color: #0e7490; }
.metric-card-dark.accent-indigo .m-icon { background: rgba(129,140,248,0.16); color: #a5b4fc; }
.metric-card-dark.accent-green  .m-icon { background: rgba(74,222,128,0.16); color: #4ade80; }
.metric-card-dark.accent-amber  .m-icon { background: rgba(251,191,36,0.16); color: #fbbf24; }
.metric-card-dark.accent-red    .m-icon { background: rgba(248,113,113,0.16); color: #f87171; }
.metric-card-dark.accent-cyan   .m-icon { background: rgba(34,211,238,0.16); color: #67e8f9; }
.metric-card .m-trend { display: flex; align-items: flex-end; gap: 3px; height: 22px; margin-top: 10px; }
.metric-card .m-trend i, .metric-card-dark .m-trend i {
    display: block; flex: 1; border-radius: 3px 3px 0 0; background: rgba(91,94,244,0.18);
}
.metric-card-dark .m-trend i { background: rgba(129,140,248,0.22); }
.metric-card .m-trend i.hi, .metric-card-dark .m-trend i.hi { background: linear-gradient(180deg,#5b5ef4,#7c3aed); }

/* Rich, illustrated empty states ────────────────────────────────────────── */
.empty-pro {
    text-align: center; padding: 44px 26px;
    border: 1.5px dashed rgba(100,116,139,0.25); border-radius: var(--radius-xl);
    background: rgba(91,94,244,0.025);
}
.empty-pro .ep-icon {
    width: 60px; height: 60px; margin: 0 auto 14px auto; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; font-size: 26px;
    background: linear-gradient(135deg, rgba(91,94,244,0.14), rgba(124,58,237,0.14));
}
.empty-pro h4 { margin: 0 0 5px 0; font-size: 14.5px; font-weight: 700; color: #0f172a; }
.empty-pro p { margin: 0; font-size: 12.5px; color: #94a3b8; line-height: 1.6; max-width: 340px; margin: 0 auto; }
.empty-pro.dark { border-color: rgba(255,255,255,0.12); background: rgba(255,255,255,0.02); }
.empty-pro.dark h4 { color: white; }
.empty-pro.dark p { color: #64748b; }

/* Pure-CSS progress ring ─────────────────────────────────────────────────── */
.ring-wrap { display: flex; align-items: center; gap: 18px; }
.ring { width: 84px; height: 84px; border-radius: 50%; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        background: conic-gradient(var(--rc,#5b5ef4) calc(var(--rp,0)*1%), rgba(148,163,184,0.16) 0); }
.ring .ring-inner { width: 64px; height: 64px; border-radius: 50%; background: var(--rb,#fff);
        display: flex; align-items: center; justify-content: center; font-weight: 800;
        font-size: 15px; color: var(--text-primary); }

/* Sidebar polish: avatar + nav section label ────────────────────────────── */
.faculty-sidebar .side-avatar {
    width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0;
    background: linear-gradient(135deg, #5b5ef4, #7c3aed);
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: 700; font-size: 13.5px;
    box-shadow: 0 4px 14px rgba(91,94,244,0.35);
}
.faculty-sidebar .who-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.faculty-sidebar .who-row .who { margin-top: 0 !important; }
.faculty-sidebar .nav-label {
    font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.1em;
    color: #475569; font-weight: 700; margin: 2px 0 8px 4px;
}

/* Section label used inside dark cards ──────────────────────────────────── */
.card-eyebrow { display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 700;
    color: #64748b; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 14px; }
.card-eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: #5b5ef4; }

/* Row list item used in activity feeds ──────────────────────────────────── */
.feed-row { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 11px 0; border-bottom: 1px solid rgba(15,23,42,0.06); }
.feed-row:last-child { border-bottom: none; }
.feed-row .fr-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.feed-row .fr-dot { width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 13px; }
.feed-row-dark { border-bottom: 1px solid rgba(255,255,255,0.06); }
.feed-row-dark:last-child { border-bottom: none; }

/* ── Login hero / marketing panel ────────────────────────────────────────── */
.login-hero { padding: 58px 40px 40px 8px; max-width: 460px; }
.login-hero .eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px;
    border-radius: 999px; background: rgba(91,94,244,0.14); border: 1px solid rgba(91,94,244,0.25);
    color: #a5b4fc; font-size: 12px; font-weight: 600; letter-spacing: 0.04em; margin-bottom: 24px; }
.login-hero h1 { color: white; font-size: 36px; font-weight: 800; line-height: 1.18;
    letter-spacing: -0.02em; margin: 0 0 16px 0; }
.login-hero h1 .grad { background: linear-gradient(135deg,#818cf8,#c084fc);
    -webkit-background-clip: text; background-clip: text; color: transparent; }
.login-hero p.lead { color: rgba(255,255,255,0.48); font-size: 14.5px; line-height: 1.65;
    margin: 0 0 36px 0; max-width: 400px; }
.login-hero .feat-row { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 22px; }
.login-hero .feat-icon { width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0;
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; justify-content: center; font-size: 18px; }
.login-hero .feat-text b { color: white; font-size: 13.5px; display: block; margin-bottom: 2px; font-weight: 700; }
.login-hero .feat-text span { color: rgba(255,255,255,0.45); font-size: 12.5px; line-height: 1.55; }
.login-hero .stat-strip { display: flex; gap: 30px; margin-top: 34px; padding-top: 26px;
    border-top: 1px solid rgba(255,255,255,0.08); }
.login-hero .stat-strip .stat b { display: block; color: white; font-size: 21px; font-weight: 800; letter-spacing: -0.02em; }
.login-hero .stat-strip .stat span { color: rgba(255,255,255,0.4); font-size: 10.5px;
    text-transform: uppercase; letter-spacing: 0.06em; }
@media (max-width: 900px) { .login-hero { display: none; } }
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


def _ring(pct: float, label: str, color: str = "#5b5ef4", dark: bool = False) -> str:
    """Return HTML for a pure-CSS circular progress ring."""
    pct = max(0, min(100, pct))
    rb = "#161d33" if dark else "#ffffff"
    text_color = "color:white;" if dark else ""
    label_color = "#94a3b8" if dark else "#64748b"
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


def load_model() -> BehavioralAuthModel:
    """Load (or construct empty) BehavioralAuthModel from disk."""
    return BehavioralAuthModel.load(MODEL_PATH)


def retrain_model() -> Optional[Dict[str, float]]:
    """Retrain the RF+SVM ensemble across every enrolled student."""
    dm = get_data_manager()
    enrolled = dm.all_enrolled_users()
    if len(enrolled) < 2:
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
        _handle_exam_answer_update(payload)
    elif kind == "lab_run":
        _handle_lab_run(dm, payload)
    elif kind == "lab_submit":
        _handle_lab_submit(dm, payload)
    elif kind == "lab_continuous_check":
        _handle_lab_continuous(dm, payload)
    elif kind == "lab_paste":
        _handle_lab_paste(dm, payload)
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
    res = load_model().predict(feats, user)
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


def _handle_exam_answer_update(payload: Dict[str, Any]) -> None:
    """Sync answers from the iframe textareas back into session_state."""
    answers = payload.get("answers") or {}
    if isinstance(answers, dict):
        st.session_state.exam_answers.update(answers)


def _handle_lab_run(dm: DataManager, payload: Dict[str, Any]) -> None:
    """Compile + run lab code against the sample input only."""
    code = payload.get("code", "")
    stdin = payload.get("stdin", "")
    timeout = int(payload.get("time_limit", 3))
    res = get_compiler().compile_and_run(code, stdin=stdin, timeout=timeout)
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
        get_compiler(), code, problem.get("test_cases", []), time_limit=timeout
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
    res = load_model().predict(feats, user)
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
            '<div class="stat"><b>RF+SVM</b><span>Ensemble model</span></div>'
            '<div class="stat"><b>&lt;1s</b><span>Verification time</span></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    with card_col:
        st.markdown(
            f'<div class="login-card" style="margin-top: 40px; margin-bottom: 40px;">'
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
        st.markdown("</div>", unsafe_allow_html=True)


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


def _render_login_verify_behavior() -> None:
    """Verify student identity by typing the behavioral phrase before login."""
    user = st.session_state.get("_pending_login", {})
    username = user.get("username", "")
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

    # Process incoming verification data
    ks_login = st.query_params.get("ks_login", None)
    ks_login_ts = st.query_params.get("ks_login_ts", None)
    if ks_login and ks_login_ts:
        if ks_login_ts != st.session_state.get("_last_login_ts"):
            st.session_state._last_login_ts = ks_login_ts
            try:
                features_dict = json.loads(base64.b64decode(ks_login))
                feature_order = [
                    "mean_dwell", "std_dwell", "median_dwell", "max_dwell",
                    "mean_flight", "std_flight", "median_flight", "min_flight",
                    "typing_speed_wpm", "dwell_flight_ratio",
                    "rhythm_consistency", "total_time_ms", "n_keys",
                ]
                features = [float(features_dict.get(k, 0)) for k in feature_order]
                model = load_model()
                if model.is_trained:
                    result = model.predict(features, username)
                    conf = result.get("confidence", 0)
                    st.session_state._verify_login_confidence = conf
                    if conf >= 0.45:
                        # Passed! Log them in
                        st.session_state.authenticated = True
                        st.session_state.role = "student"
                        st.session_state.username = user["username"]
                        st.session_state.full_name = user.get("full_name", user["username"])
                        st.session_state.course_name = user.get("course_name")
                        st.session_state.enrollment_no = user.get("enrollment_no")
                        st.session_state.page = "courses"
                        st.session_state._pending_login = None
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.session_state._verify_login_attempts = attempts + 1
                else:
                    # No model trained yet, let them in
                    st.session_state.authenticated = True
                    st.session_state.role = "student"
                    st.session_state.username = user["username"]
                    st.session_state.full_name = user.get("full_name", user["username"])
                    st.session_state.course_name = user.get("course_name")
                    st.session_state.enrollment_no = user.get("enrollment_no")
                    st.session_state.page = "courses"
                    st.session_state._pending_login = None
                    st.query_params.clear()
                    st.rerun()
            except Exception:
                pass
            st.query_params.clear()

    st.markdown(f"<div style='color:white;font-size:18px;font-weight:700;margin-bottom:4px;'>Welcome back, {user.get('full_name','')}</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:13px;margin-bottom:16px;'>Type the phrase below to verify your identity</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);border-radius:12px;padding:14px 18px;text-align:center;color:#c7d2fe;font-size:18px;font-weight:600;letter-spacing:0.04em;margin-bottom:12px;'>{PHRASE}</div>", unsafe_allow_html=True)

    if attempts > 0:
        conf = st.session_state.get("_verify_login_confidence")
        if conf is not None:
            pct = conf * 100
            st.markdown(f"<div style='color:#fca5a5;font-size:13px;margin-bottom:8px;'>Confidence: {pct:.0f}% — too low. {3 - attempts} attempts remaining.</div>", unsafe_allow_html=True)

    verify_js = """
    <form id="verify-form" onsubmit="event.preventDefault(); doVerify(); return false;" style="font-family:Inter,sans-serif;">
      <input id="verify-input" type="text" placeholder="Type the phrase here..." autocomplete="off" spellcheck="false"
        style="width:100%%;box-sizing:border-box;padding:14px 16px;border-radius:12px;border:1.5px solid rgba(99,102,241,0.4);background:rgba(255,255,255,0.08);color:white;font-size:15px;outline:none;margin-bottom:10px;font-family:Inter,sans-serif;"/>
      <button type="submit" style="width:100%%;padding:12px;border-radius:12px;border:none;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;font-weight:600;font-size:14px;cursor:pointer;font-family:Inter,sans-serif;">Verify Identity</button>
      <div id="v-status" style="text-align:center;color:#a5b4fc;font-size:12px;margin-top:8px;"></div>
    </form>
    <script>
    var vbuf = [];
    var vinp = document.getElementById('verify-input');
    vinp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); }
      vbuf.push({key: e.key, type: 'down', t: Date.now()});
    });
    vinp.addEventListener('keyup', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); doVerify(); return; }
      vbuf.push({key: e.key, type: 'up', t: Date.now()});
    });
    function doVerify() {
      var features = vExtract(vbuf);
      if (features.n_keys < 10) { document.getElementById('v-status').textContent = 'Type the full phrase first'; document.getElementById('v-status').style.color = '#fca5a5'; return; }
      var encoded = btoa(JSON.stringify(features));
      var url = new URL(window.parent.location.href);
      url.searchParams.set('ks_login', encoded);
      url.searchParams.set('ks_login_ts', Date.now().toString());
      window.parent.history.replaceState({}, '', url);
      vbuf = [];
      vinp.value = '';
      document.getElementById('v-status').textContent = 'Verifying...';
      document.getElementById('v-status').style.color = '#a5b4fc';
      setTimeout(function(){ 
        window.parent.dispatchEvent(new Event('popstate'));
        var btns = window.parent.document.querySelectorAll('button');
        btns.forEach(function(b) { if(b.innerText.includes('HiddenTrigger')) b.click(); });
      }, 100);
    }
    function vExtract(buf) {
      var downTimes={},dwells=[],flights=[];
      var keys=buf.filter(function(e){return e.key.length===1||e.key==='Backspace'||e.key===' ';});
      var firstDown=null,lastUp=null,prevUpTime=null;
      keys.forEach(function(e){
        if(e.type==='down'){downTimes['k_'+e.t]=e.t;if(!firstDown)firstDown=e.t;if(prevUpTime!==null)flights.push(e.t-prevUpTime);}
        else{var ks=Object.keys(downTimes);if(ks.length>0){var lk=ks[ks.length-1];dwells.push(e.t-downTimes[lk]);delete downTimes[lk];}prevUpTime=e.t;lastUp=e.t;}
      });
      function mean(a){return a.length?a.reduce(function(s,v){return s+v;},0)/a.length:0;}
      function std(a){var m=mean(a);return a.length?Math.sqrt(a.reduce(function(s,v){return s+(v-m)*(v-m);},0)/a.length):0;}
      function median(a){if(!a.length)return 0;var s=a.slice().sort(function(x,y){return x-y;});var m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;}
      var pf=flights.filter(function(f){return f>=0;});
      var tt=(firstDown&&lastUp)?lastUp-firstDown:1000;
      var md=mean(dwells),mf=mean(pf);
      return {mean_dwell:md,std_dwell:std(dwells),median_dwell:median(dwells),max_dwell:dwells.length?Math.max.apply(null,dwells):0,mean_flight:mf,std_flight:std(pf),median_flight:median(pf),min_flight:pf.length?Math.min.apply(null,pf):0,typing_speed_wpm:tt>0?(keys.length/5)/(tt/60000):0,dwell_flight_ratio:mf>0?md/mf:1,rhythm_consistency:md>0?Math.max(0,Math.min(1,1-(std(dwells)/md))):0,total_time_ms:tt,n_keys:keys.length};
    }
    vinp.focus();
    </script>
    """
    components.html(verify_js, height=160)
    
    # Hidden button to trigger reruns from JS without full page reload
    st.markdown('<div style="display:none;">', unsafe_allow_html=True)
    st.button("HiddenTrigger_Verify", key="ht_verify")
    st.markdown('</div>', unsafe_allow_html=True)

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
        # Faculty/course selector
        faculty_list = dm.get_all_faculty()
        course_options = []
        fac_map = {}
        for f in faculty_list:
            label = f"{f.get('course_name', 'Course')} ({f.get('full_name', 'Faculty')})"
            course_options.append(label)
            fac_map[label] = f["username"]
        selected_course = None
        if course_options:
            selected_course = st.selectbox("Select your course & faculty", course_options)
        else:
            st.caption("No faculty courses available yet.")
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
            "faculty_username": fac_map.get(selected_course, "") if selected_course else "",
            "course_label": selected_course or "",
        }
        st.session_state.reg_step = 2
        st.session_state.reg_samples = []
        st.rerun()


def _handle_reg_sample() -> int:
    """Process incoming keystroke registration sample from JS widget."""
    ks_reg = st.query_params.get("ks_reg", None)
    reg_ts = st.query_params.get("reg_ts", None)
    if ks_reg and reg_ts:
        if reg_ts != st.session_state.get("last_reg_ts"):
            st.session_state.last_reg_ts = reg_ts
            try:
                import base64 as b64
                features = json.loads(b64.b64decode(ks_reg))
                if "reg_samples" not in st.session_state:
                    st.session_state.reg_samples = []
                st.session_state.reg_samples.append(features)
                st.query_params.clear()
            except Exception:
                pass
    return len(st.session_state.get("reg_samples", []))


def _reg_step2(dm) -> None:
    """Step 2: Behavioural enrollment — type phrase 10 times."""
    import json as _json
    sample_count = _handle_reg_sample()
    if sample_count >= ENROLL_TARGET:
        st.session_state.reg_step = 3
        st.rerun()
        return
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:12px;margin-bottom:8px;'>Step 2 of 3 — Teach the system your typing rhythm</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:rgba(255,255,255,0.45);font-size:13px;margin-bottom:12px;'>Type the phrase below exactly 10 times. This creates your unique behavioral fingerprint used to verify your identity during exams.</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);border-radius:12px;padding:14px 18px;text-align:center;color:#c7d2fe;font-size:18px;font-weight:600;letter-spacing:0.04em;margin-bottom:12px;'>{PHRASE}</div>", unsafe_allow_html=True)
    pct = int(sample_count / ENROLL_TARGET * 100)
    st.markdown(f"<div style='color:white;font-size:14px;font-weight:600;margin-bottom:6px;'>Sample {sample_count} of {ENROLL_TARGET}</div>", unsafe_allow_html=True)
    st.progress(sample_count / ENROLL_TARGET)
    # JS keystroke capture widget — uses form onsubmit to prevent parent form submit
    reg_widget_html = """
    <form id="sample-form" onsubmit="event.preventDefault(); submitSample(); return false;" style="font-family:Inter,sans-serif;">
      <input id="phrase-input" type="text" placeholder="Type the phrase here and press Enter..." autocomplete="off" spellcheck="false"
        style="width:100%%;box-sizing:border-box;padding:14px 16px;border-radius:12px;border:1.5px solid rgba(99,102,241,0.4);background:rgba(255,255,255,0.08);color:white;font-size:15px;outline:none;margin-bottom:10px;font-family:Inter,sans-serif;"/>
      <button type="submit" id="submit-btn"
        style="width:100%%;padding:12px;border-radius:12px;border:none;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;font-weight:600;font-size:14px;cursor:pointer;font-family:Inter,sans-serif;">Submit Sample</button>
      <div id="status-msg" style="text-align:center;color:#a5b4fc;font-size:12px;margin-top:8px;"></div>
    </form>
    <script>
    var buffer = [];
    var inp = document.getElementById('phrase-input');
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); }
      buffer.push({key: e.key, type: 'down', t: Date.now()});
    });
    inp.addEventListener('keyup', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); submitSample(); return; }
      buffer.push({key: e.key, type: 'up', t: Date.now()});
    });
    function submitSample() {
      var features = extractFeatures(buffer);
      if (features.n_keys < 10) {
        document.getElementById('status-msg').textContent = 'Type the full phrase before submitting';
        document.getElementById('status-msg').style.color = '#fca5a5';
        return;
      }
      var encoded = btoa(JSON.stringify(features));
      var url = new URL(window.parent.location.href);
      url.searchParams.set('ks_reg', encoded);
      url.searchParams.set('reg_ts', Date.now().toString());
      window.parent.history.replaceState({}, '', url);
      // Trigger Streamlit rerun
      var iframes = window.parent.document.querySelectorAll('iframe');
      iframes.forEach(function(f){ try { f.contentWindow.postMessage({isStreamlitMessage:true,type:'streamlit:componentReady'},'*'); } catch(x){} });
      buffer = [];
      inp.value = '';
      document.getElementById('status-msg').textContent = '\u2705 Sample captured! Processing...';
      document.getElementById('status-msg').style.color = '#4ade80';
      setTimeout(function(){ 
        window.parent.dispatchEvent(new Event('popstate'));
        var btns = window.parent.document.querySelectorAll('button');
        btns.forEach(function(b) { if(b.innerText.includes('HiddenTrigger')) b.click(); });
      }, 100);
    }
    function extractFeatures(buf) {
      var downTimes = {}, dwells = [], flights = [];
      var keys = buf.filter(function(e){ return e.key.length===1||e.key==='Backspace'||e.key===' '; });
      var firstDown = null, lastUp = null, prevUpTime = null;
      keys.forEach(function(e) {
        if (e.type === 'down') {
          downTimes['k_'+e.t] = e.t;
          if (!firstDown) firstDown = e.t;
          if (prevUpTime !== null) flights.push(e.t - prevUpTime);
        } else {
          var ks = Object.keys(downTimes);
          if (ks.length > 0) { var lk = ks[ks.length-1]; dwells.push(e.t - downTimes[lk]); delete downTimes[lk]; }
          prevUpTime = e.t; lastUp = e.t;
        }
      });
      function mean(a){return a.length?a.reduce(function(s,v){return s+v;},0)/a.length:0;}
      function std(a){var m=mean(a);return a.length?Math.sqrt(a.reduce(function(s,v){return s+(v-m)*(v-m);},0)/a.length):0;}
      function median(a){if(!a.length)return 0;var s=a.slice().sort(function(x,y){return x-y;});var m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;}
      var posFlights=flights.filter(function(f){return f>=0;});
      var totalTime=(firstDown&&lastUp)?lastUp-firstDown:1000;
      var md=mean(dwells),mf=mean(posFlights);
      return {
        mean_dwell:md,std_dwell:std(dwells),median_dwell:median(dwells),max_dwell:dwells.length?Math.max.apply(null,dwells):0,
        mean_flight:mf,std_flight:std(posFlights),median_flight:median(posFlights),min_flight:posFlights.length?Math.min.apply(null,posFlights):0,
        typing_speed_wpm:totalTime>0?(keys.length/5)/(totalTime/60000):0,
        dwell_flight_ratio:mf>0?md/mf:1,
        rhythm_consistency:md>0?Math.max(0,Math.min(1,1-(std(dwells)/md))):0,
        total_time_ms:totalTime,n_keys:keys.length
      };
    }
    inp.focus();
    </script>
    """
    components.html(reg_widget_html, height=170)

    # Hidden button to trigger reruns from JS without full page reload
    st.markdown('<div style="display:none;">', unsafe_allow_html=True)
    st.button("HiddenTrigger_Reg", key="ht_reg")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("← Back", key="reg_back"):
        st.session_state.reg_step = 1
        st.rerun()


def _reg_step3(dm) -> None:
    """Step 3: Train profile + complete registration."""
    rd = st.session_state.reg_data
    samples = st.session_state.get("reg_samples", [])
    st.markdown("<div style='color:rgba(255,255,255,0.5);font-size:12px;margin-bottom:8px;'>Step 3 of 3 — Finalizing</div>", unsafe_allow_html=True)
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
        # Save keystroke samples
        dm.save_keystroke_samples(rd["username"], samples)
        # Enroll in faculty course
        if rd.get("faculty_username"):
            dm.enroll_student(rd["username"], rd["faculty_username"])
        # Try training model
        train_result = retrain_model()
    st.markdown("<div style='text-align:center;font-size:48px;margin:12px 0;'>✅</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:white;text-align:center;font-size:18px;font-weight:600;margin-bottom:8px;'>Profile created!</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:rgba(255,255,255,0.6);text-align:center;font-size:13px;margin-bottom:16px;'>Your behavioral fingerprint is ready.</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.06);border-radius:12px;padding:16px;margin-bottom:16px;'>"
        f"<div style='color:#94a3b8;font-size:12px;'>Username</div><div style='color:white;font-weight:600;'>{rd['username']}</div>"
        f"<div style='color:#94a3b8;font-size:12px;margin-top:8px;'>Course</div><div style='color:white;font-weight:600;'>{rd.get('course_label','N/A')}</div>"
        f"<div style='color:#94a3b8;font-size:12px;margin-top:8px;'>Samples collected</div><div style='color:white;font-weight:600;'>{len(samples)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if train_result is None:
        st.info("Account created. Model will train when more students enroll.")
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
        st.rerun()


# ── Faculty layout ──────────────────────────────────────────────────────────
def show_faculty_sidebar() -> None:
    """Left navy sidebar with brand, profile, nav buttons, logout."""
    page = st.session_state.page
    items = [
        ("overview", "📊  Overview"),
        ("exams", "📝  Exam Management"),
        ("lab", "🧪  Code Lab"),
        ("reports", "📋  Reports"),
        ("settings", "⚙️  Settings"),
    ]
    with st.sidebar:
        pass  # silence default sidebar
    # Custom sidebar in main flow:
    sidebar_col, _ = st.columns([1, 4])
    with sidebar_col:
        st.markdown(
            f'<div class="faculty-sidebar">'
            f'<div class="brand">{SHIELD_SVG}<span>TrueTestAuth</span></div>'
            f'<div class="who">{st.session_state.full_name}</div>'
            f'<div class="course-pill">{st.session_state.course_name or ""}</div>'
            f"<hr/>",
            unsafe_allow_html=True,
        )
        for key, label in items:
            cls = "active" if page == key else ""
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{key}"):
                _goto(key)
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown('<div class="logout">', unsafe_allow_html=True)
        if st.button("⏻  Logout", key="nav_logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            _init_state()
            st.rerun()
        st.markdown("</div></div>", unsafe_allow_html=True)


def _faculty_layout(render_content) -> None:
    """Helper: emits the 240px sidebar + content layout with `render_content`."""
    sb, content = st.columns([1, 4])
    with sb:
        _render_faculty_sidebar_inner()
    with content:
        st.markdown('<div class="faculty-content">', unsafe_allow_html=True)
        render_content()
        st.markdown("</div>", unsafe_allow_html=True)


def _render_faculty_sidebar_inner() -> None:
    """Faculty sidebar markup + nav buttons (called inside a column)."""
    page = st.session_state.page
    items = [
        ("overview", "📊  Overview"),
        ("exams", "📝  Exam Management"),
        ("lab", "🧪  Code Lab"),
        ("reports", "📋  Reports"),
        ("settings", "⚙️  Settings"),
    ]
    course_pill = (
        f'<div class="course-pill">{st.session_state.course_name}</div>'
        if st.session_state.course_name
        else ""
    )
    initials = "".join(x[0] for x in (st.session_state.full_name or "F").split()[:2]).upper()
    st.markdown(
        f'<div class="faculty-sidebar">'
        f'<div class="brand">{SHIELD_SVG}<span>TrueTestAuth</span></div>'
        f'<div class="who-row"><div class="side-avatar">{initials}</div>'
        f'<div class="meta"><div class="who">{st.session_state.full_name}</div>'
        f'{course_pill}</div></div>'
        f"<hr/>"
        f'<div class="nav-label">Main menu</div>',
        unsafe_allow_html=True,
    )
    for key, label in items:
        if page == key:
            st.markdown('<div class="active">', unsafe_allow_html=True)
        if st.button(label, key=f"nav_{key}", width='stretch'):
            _goto(key)
        if page == key:
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown('<div class="logout">', unsafe_allow_html=True)
    if st.button("⏻  Logout", key="nav_logout", width='stretch'):
        keep = []
        for k in list(st.session_state.keys()):
            if k not in keep:
                del st.session_state[k]
        _init_state()
        st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)


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

        first_name = (st.session_state.full_name or "there").split()[0]
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
            st.markdown('<div class="tp-card">', unsafe_allow_html=True)
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
                        "<div><span style='color:#0f172a;font-weight:600;font-size:13.5px'>"
                        f"{r.get('student_name', r['username'])}</span>"
                        f"<span style='color:#94a3b8;font-size:12px;margin-left:8px'>{r['kind']}</span></div>"
                        "</div>"
                        f"<span style='color:#94a3b8;font-size:12px;white-space:nowrap'>{ts}</span></div>"
                    )
                st.markdown(rows, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="tp-card">', unsafe_allow_html=True)
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
                        "<div><span style='color:#0f172a;font-weight:600;font-size:13.5px'>"
                        f"{f.get('student_name', f['username'])}</span></div></div>"
                        f"<span style='color:#94a3b8;font-size:12px;white-space:nowrap'>"
                        f"conf {f['confidence']*100:.0f}% · {ts}</span></div>"
                    )
                st.markdown(rows, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if not students and not exams and not labs:
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            st.markdown('<div class="tp-card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="card-eyebrow"><span class="dot"></span>Getting started</div>'
                '<div style="display:flex;gap:18px;flex-wrap:wrap;">'
                '<div style="flex:1;min-width:200px;">'
                '<div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:4px;">'
                '① Create your first exam</div>'
                '<div style="font-size:12.5px;color:#94a3b8;line-height:1.6;">Head to '
                '<b>Exam Management</b> and add questions with a time limit.</div></div>'
                '<div style="flex:1;min-width:200px;">'
                '<div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:4px;">'
                '② Set up a code lab</div>'
                '<div style="font-size:12.5px;color:#94a3b8;line-height:1.6;">Add C++ problems with '
                'test cases under <b>Code Lab</b>.</div></div>'
                '<div style="flex:1;min-width:200px;">'
                '<div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:4px;">'
                '③ Share your course</div>'
                '<div style="font-size:12.5px;color:#94a3b8;line-height:1.6;">Students register with '
                'your course name to appear on this dashboard.</div></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

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
    """Form to compose an exam (questions + PDF parse) and persist it."""
    dm = get_data_manager()
    if "_exam_q_count" not in st.session_state:
        st.session_state._exam_q_count = 5

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

    with st.form("create_exam_form", clear_on_submit=False):
        c1, c2 = st.columns([2, 1])
        with c1:
            title = st.text_input("Exam title", placeholder="Mid-Sem — Data Structures")
            subject = st.text_input(
                "Subject / course", value=st.session_state.course_name or ""
            )
            instructions = st.text_area(
                "Instructions", height=80, placeholder="Read carefully…"
            )
        with c2:
            edate = st.date_input("Exam date", value=date.today())
            etime = st.time_input("Start time", value=dtime(10, 0))
            duration = st.slider("Duration (minutes)", 30, 180, 60)

        st.markdown(f"##### Questions ({st.session_state._exam_q_count})")
        questions: List[Dict[str, Any]] = []
        for i in range(st.session_state._exam_q_count):
            with st.expander(f"Question {i + 1}", expanded=(i == 0)):
                qa, qb = st.columns([3, 1])
                with qa:
                    qtype = st.selectbox(
                        "Type", ["Descriptive", "MCQ"], key=f"qt_{i}"
                    )
                    qtext_default = pdf_text if (i == 0 and pdf_text) else ""
                    qtext = st.text_area(
                        f"Question text {i + 1}",
                        value=qtext_default,
                        height=100,
                        key=f"qtext_{i}",
                    )
                with qb:
                    marks = st.number_input(
                        "Marks", min_value=1, max_value=50, value=10, step=1, key=f"qm_{i}"
                    )
                if qtype == "MCQ":
                    o1 = st.text_input("Option A", key=f"o1_{i}")
                    o2 = st.text_input("Option B", key=f"o2_{i}")
                    o3 = st.text_input("Option C", key=f"o3_{i}")
                    o4 = st.text_input("Option D", key=f"o4_{i}")
                    correct = st.radio(
                        "Correct option",
                        ["A", "B", "C", "D"],
                        horizontal=True,
                        key=f"corr_{i}",
                    )
                    options = [o1, o2, o3, o4]
                else:
                    options = []
                    correct = ""
                questions.append(
                    {
                        "q_id": f"q{i + 1}",
                        "type": qtype,
                        "text": qtext,
                        "marks": int(marks),
                        "options": options,
                        "correct": correct,
                    }
                )

        ok = st.form_submit_button("💾  Save exam", width='stretch')
        if ok:
            if not title.strip():
                st.error("Title is required.")
            elif not any(q["text"].strip() for q in questions):
                st.error("Add at least one question.")
            else:
                eid = dm.create_exam(
                    faculty_username=st.session_state.username,
                    title=title.strip(),
                    subject=subject.strip(),
                    date=str(edate),
                    start_time=etime.strftime("%H:%M"),
                    duration_mins=int(duration),
                    instructions=instructions,
                    questions=[q for q in questions if q["text"].strip()],
                )
                st.success(f"Saved exam id={eid}.")


def _faculty_active_exams() -> None:
    """Card grid of all exams owned by this faculty."""
    dm = get_data_manager()
    exams = dm.get_exams(faculty_username=st.session_state.username)
    if not exams:
        _empty("📂", "No exams created yet",
               "Switch to the \u201cCreate exam\u201d tab to build your first proctored exam.")
        return
    for e in exams:
        sts_cls = {
            "upcoming": "badge-upcoming",
            "active": "badge-active",
            "ended": "badge-ended",
        }.get(e.get("status", "upcoming"), "badge-upcoming")
        st.markdown(
            f'<div class="tp-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:14px;">'
            f'<div style="display:flex;align-items:center;gap:14px;min-width:0;">'
            f'<div class="m-icon" style="background:rgba(91,94,244,0.10);color:#4f46e5;'
            f'width:42px;height:42px;border-radius:12px;font-size:18px;flex-shrink:0;'
            f'display:flex;align-items:center;justify-content:center;">📝</div>'
            f'<div style="min-width:0;">'
            f'<b style="font-size:15.5px; color:#0f172a;">{e["title"]}</b>'
            f'<div style="color:#94a3b8;font-size:12.5px;margin-top:3px;">'
            f'{e["subject"]} · {e["date"]} {e.get("start_time","")} · '
            f'{e["duration_mins"]} min · {len(e["questions"])} questions</div>'
            f'</div></div>'
            f'<span class="badge {sts_cls}" style="flex-shrink:0;">{e.get("status","upcoming").upper()}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


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
    subs = dm.get_exam_submissions(exam_id=eid)
    if not subs:
        _empty("📭", "No submissions yet", "Once students complete this exam, their submissions will show up here.")
        return
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
                "Score": s.get("score", ""),
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
            f'<b style="font-size:15.5px; color:#0f172a;">{lab["title"]}</b>'
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
                f"<div style='color:#475569;margin-top:0.25rem;'>"
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
                   "Once students register under your course, their reports will appear here.")
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
            st.markdown('<div class="tp-card" style="text-align:center;">', unsafe_allow_html=True)
            avg_pct = summary["avg_conf"] * 100
            ring_color = "#16a34a" if avg_pct >= 65 else "#d97706" if avg_pct >= 45 else "#dc2626"
            st.markdown(_ring(avg_pct, "Avg confidence", ring_color), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
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


# ── Faculty: Settings ───────────────────────────────────────────────────────
def show_faculty_settings() -> None:
    """Settings: change course name + view enrolled students."""
    def _content():
        dm = get_data_manager()
        _page_header("⚙️", "Settings", "Update your course and view enrolled students.")

        sc1, sc2 = st.columns([1.1, 1])
        with sc1:
            st.markdown('<div class="tp-card">', unsafe_allow_html=True)
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
            st.markdown("</div>", unsafe_allow_html=True)
        with sc2:
            st.markdown('<div class="tp-card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="card-eyebrow"><span class="dot"></span>Account</div>',
                unsafe_allow_html=True,
            )
            initials = "".join(x[0] for x in (st.session_state.full_name or "F").split()[:2]).upper()
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;">'
                f'<div class="avatar" style="width:44px;height:44px;font-size:15px;">{initials}</div>'
                f'<div><div style="font-weight:700;font-size:14.5px;color:#0f172a;">'
                f'{st.session_state.full_name}</div>'
                f'<div style="font-size:12.5px;color:#94a3b8;">@{st.session_state.username} · Faculty</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="tp-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-eyebrow"><span class="dot"></span>Enrolled students</div>',
            unsafe_allow_html=True,
        )
        students = dm.get_faculty_students(st.session_state.username)
        if not students:
            _empty("🎓", "No students enrolled yet",
                   "Share your course name with students so they can register.")
        else:
            for s in students:
                initials = "".join(x[0] for x in (s.get("full_name", "S")).split()[:2]).upper()
                st.markdown(
                    "<div class='feed-row'><div class='fr-left'>"
                    f"<div class='avatar' style='width:32px;height:32px;font-size:12px;'>{initials}</div>"
                    f"<span><b style='color:#0f172a;'>{s.get('full_name', s['username'])}</b> "
                    f"<span style='color:#94a3b8;font-size:12.5px;'>· {s.get('enrollment_no','')}</span></span>"
                    "</div>"
                    f"<span class='badge badge-easy'>{s['username']}</span></div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)
    _faculty_layout(_content)


# ── Student layout ──────────────────────────────────────────────────────────
from ui_components import render_student_navbar as _ui_student_navbar, render_student_layout as _ui_student_layout

def show_student_navbar() -> None:
    _ui_student_navbar()
    # Add the logout button in a small column at the top right, inside the content area
    c1, c2 = st.columns([10, 1])
    with c2:
        if st.button("Logout", key="stu_logout", width='stretch'):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

def _student_layout(render) -> None:
    """Wrap student pages with the navbar + padded content area."""
    def wrapped():
        # The logout button is now part of the content wrapper
        c1, c2 = st.columns([10, 1])
        with c2:
            if st.button("Logout", key="stu_logout_top", width='stretch'):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()
        render()
    
    _ui_student_layout(wrapped)


# ── Student: Courses ─────────────────────────────────────────────────────────
def show_student_courses() -> None:
    """List of faculty-courses this student is enrolled in."""
    def _content():
        dm = get_data_manager()
        _page_header("🎓", "Your Courses", "Pick a course to see its exams and labs.", dark=True)
        courses = dm.get_student_courses(st.session_state.username)
        if not courses:
            _empty("🎓", "No courses yet",
                   "You are not enrolled in any course yet. Ask your professor to add you, "
                   "or run <code>python seed_demo.py</code> for demo data.", dark=True)
            return
        st.markdown('<div class="course-grid">', unsafe_allow_html=True)
        for fac in courses:
            initials = "".join(
                x[0] for x in (fac.get("full_name", "F")).split()[:2]
            ).upper()
            n_exams = len(dm.get_exams(faculty_username=fac["username"]))
            n_labs = len(dm.get_labs(faculty_username=fac["username"]))
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
                f"Open {fac['course_name']} →",
                key=f"open_{fac['username']}",
                width='stretch',
            ):
                st.session_state.selected_course = fac["username"]
                _goto("course_detail")
        st.markdown("</div>", unsafe_allow_html=True)
    _student_layout(_content)


def show_student_course_detail() -> None:
    """A course's two tabs: Exams + Labs."""
    def _content():
        dm = get_data_manager()
        fac = dm.get_user(st.session_state.selected_course or "") or {}
        st.markdown(
            f'<a href="?back=1" style="color:#6366f1;font-size:13px;">← Home</a>'
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
            exam_list = dm.get_exams(faculty_username=fac["username"])
            if not exam_list:
                _empty("📝", "No exams yet", "Your instructor hasn't published any exams for this course.", dark=True)
            for e in exam_list:
                sub = dm.get_exam_submission(st.session_state.username, e["exam_id"])
                status = "Submitted" if sub else "Not started"
                badge = "badge-active" if sub else "badge-upcoming"
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
                if not sub:
                    if st.button(f"Start exam: {e['title']}", key=f"start_{e['exam_id']}"):
                        st.session_state.active_exam_id = e["exam_id"]
                        st.session_state.exam_answers = {}
                        st.session_state.auth_log = []
                        st.session_state.cp_log = []
                        st.session_state.session_id = uuid.uuid4().hex
                        st.session_state.consecutive_fails = 0
                        st.session_state.exam_verified = False
                        st.session_state._verify_attempts = 0
                        st.session_state.exam_submitted = False
                        _goto("exam_verify")
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
                if st.button(f"Start lab: {lab['title']}", key=f"sl_{lab['lab_id']}"):
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
                f"<div style='height:10px;background:#f1f5f9;border-radius:99px;'>"
                f"<div style='height:100%;width:{pct:.1f}%;background:{color};"
                f"border-radius:99px;'></div></div></div>",
                unsafe_allow_html=True,
            )
        if st.session_state.exam_verified:
            st.success("Verification passed.")
            if st.button("Enter Exam →", type="primary"):
                st.session_state.exam_start_time = time.time()
                _goto("exam_portal")
        elif st.session_state._verify_attempts > 0:
            st.warning(
                f"Try again — {3 - st.session_state._verify_attempts} attempts remaining."
            )
    _student_layout(_content)


# ── Student: Exam portal ────────────────────────────────────────────────────
def _handle_continuous_auth() -> None:
    """Process incoming keystroke check from JS widget."""
    ks_json = st.query_params.get("ks_json", None)
    ks_ts = st.query_params.get("ks_ts", None)
    if not ks_json or not ks_ts:
        return
    if ks_ts == st.session_state.get("last_ks_ts"):
        return
    st.session_state.last_ks_ts = ks_ts
    try:
        features_dict = json.loads(base64.b64decode(ks_json))
        username = st.session_state.username
        # Convert dict to list for ML model
        feature_order = [
            "mean_dwell", "std_dwell", "median_dwell", "max_dwell",
            "mean_flight", "std_flight", "median_flight", "min_flight",
            "typing_speed_wpm", "dwell_flight_ratio",
            "rhythm_consistency", "total_time_ms", "n_keys",
        ]
        features = [float(features_dict.get(k, 0)) for k in feature_order]
        model = load_model()
        if not model.is_trained:
            st.query_params.clear()
            return
        result = model.predict(features, username)
        conf = result.get("confidence", 0)
        if conf >= AMBER_CONFIDENCE:
            status = "Verified"
            st.session_state.consecutive_fails = 0
        elif conf >= LOW_CONFIDENCE:
            status = "Warning"
            st.session_state.consecutive_fails = 0
        else:
            status = "Flagged"
            st.session_state.consecutive_fails = st.session_state.get("consecutive_fails", 0) + 1
        check = {
            "timestamp": time.time(),
            "confidence": conf,
            "status": status,
        }
        if "auth_log" not in st.session_state:
            st.session_state.auth_log = []
        st.session_state.auth_log.append(check)
        dm = get_data_manager()
        dm.log_auth_check(
            username, st.session_state.session_id or "",
            conf, status,
        )
        st.query_params.clear()
    except Exception:
        pass


def _get_continuous_auth_js() -> str:
    """Return JS that captures keystrokes from parent textareas for continuous auth."""
    return """
    <script>
    (function() {
      var buffer = [];
      var CHECK_INTERVAL = 30000;
      var MIN_KEYS = 15;
      function attachListeners() {
        var parentDoc = window.parent.document;
        var textareas = parentDoc.querySelectorAll('textarea');
        textareas.forEach(function(ta) {
          if (ta.dataset.authAttached) return;
          ta.dataset.authAttached = 'true';
          ta.addEventListener('keydown', function(e) {
            buffer.push({key: e.key, type: 'down', t: Date.now()});
          });
          ta.addEventListener('keyup', function(e) {
            buffer.push({key: e.key, type: 'up', t: Date.now()});
          });
        });
      }
      setInterval(attachListeners, 3000);
      attachListeners();
      function attachCopyPasteBlock() {
        var parentDoc = window.parent.document;
        var textareas = parentDoc.querySelectorAll('textarea');
        textareas.forEach(function(ta) {
          if (ta.dataset.cpBlocked) return;
          ta.dataset.cpBlocked = 'true';
          ta.addEventListener('paste', function(e) { e.preventDefault(); e.stopPropagation(); showToast('Paste disabled during exam', 'danger'); });
          ta.addEventListener('copy', function(e) { e.preventDefault(); showToast('Copy disabled during exam', 'warning'); });
          ta.addEventListener('cut', function(e) { e.preventDefault(); });
          ta.addEventListener('contextmenu', function(e) { e.preventDefault(); });
        });
        parentDoc.addEventListener('keydown', function(e) {
          var key = e.key.toLowerCase();
          if ((e.ctrlKey || e.metaKey) && ['v','c','x'].includes(key)) {
            e.preventDefault();
            if (key === 'v') showToast('Paste disabled', 'danger');
            if (key === 'c') showToast('Copy disabled', 'warning');
          }
        }, true);
      }
      setInterval(attachCopyPasteBlock, 3000);
      attachCopyPasteBlock();
      function showToast(msg, type) {
        var parentDoc = window.parent.document;
        var toast = parentDoc.createElement('div');
        toast.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;padding:12px 20px;border-radius:10px;font-size:13px;font-weight:500;color:white;pointer-events:none;' + (type==='danger'?'background:#ef4444;':'background:#f59e0b;');
        toast.textContent = msg;
        parentDoc.body.appendChild(toast);
        setTimeout(function(){ if(toast.parentNode) toast.parentNode.removeChild(toast); }, 3000);
      }
      function extractFeatures(buf) {
        var downTimes={},dwells=[],flights=[];
        var eligibleKeys=buf.filter(function(e){return e.key.length===1||e.key==='Backspace'||e.key===' ';});
        var firstDown=null,lastUp=null,prevUpTime=null;
        eligibleKeys.forEach(function(e){
          if(e.type==='down'){if(!firstDown)firstDown=e.t;downTimes['k_'+e.t]=e.t;if(prevUpTime!==null)flights.push(e.t-prevUpTime);}
          else{var ks=Object.keys(downTimes);if(ks.length>0){var lk=ks[ks.length-1];dwells.push(e.t-downTimes[lk]);delete downTimes[lk];}prevUpTime=e.t;lastUp=e.t;}
        });
        function mean(a){return a.length?a.reduce(function(s,v){return s+v;},0)/a.length:0;}
        function std(a){var m=mean(a);return a.length?Math.sqrt(a.reduce(function(s,v){return s+(v-m)*(v-m);},0)/a.length):0;}
        function median(a){if(!a.length)return 0;var s=a.slice().sort(function(x,y){return x-y;});var m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;}
        var posFlights=flights.filter(function(f){return f>=0;});
        var totalTime=(firstDown&&lastUp)?lastUp-firstDown:1000;
        var md=mean(dwells),mf=mean(posFlights);
        return {
          mean_dwell:md,std_dwell:std(dwells),median_dwell:median(dwells),max_dwell:dwells.length?Math.max.apply(null,dwells):0,
          mean_flight:mf,std_flight:std(posFlights),median_flight:median(posFlights),min_flight:posFlights.length?Math.min.apply(null,posFlights):0,
          typing_speed_wpm:totalTime>0?(eligibleKeys.length/5)/(totalTime/60000):0,
          dwell_flight_ratio:mf>0?md/mf:1,
          rhythm_consistency:md>0?Math.max(0,Math.min(1,1-(std(dwells)/md))):0,
          total_time_ms:totalTime,n_keys:eligibleKeys.length
        };
      }
      setInterval(function(){
        if(buffer.length<MIN_KEYS)return;
        var features=extractFeatures(buffer);
        if(features.n_keys<MIN_KEYS)return;
        var encoded=btoa(JSON.stringify(features));
        var url=new URL(window.parent.location.href);
        url.searchParams.set('ks_json',encoded);
        url.searchParams.set('ks_ts',Date.now().toString());
        window.parent.history.replaceState({},'',url);
        buffer=[];
      },CHECK_INTERVAL);
    })();
    </script>
    """


def show_exam_portal() -> None:
    """Live exam UI — questions on the left, status sidebar on the right."""
    # Process continuous auth FIRST before any UI
    _handle_continuous_auth()
    def _content():
        dm = get_data_manager()
        exam = dm.get_exam(st.session_state.active_exam_id) or {}
        if not exam:
            st.error("Exam not found.")
            return
        if st.session_state.exam_submitted:
            _goto("submitted")
            return
        # Inject continuous auth JS (hidden, height=1)
        components.html(_get_continuous_auth_js(), height=1)
        # Compute timer FIRST so auto-refresh JS can use it
        elapsed = int(time.time() - (st.session_state.exam_start_time or time.time()))
        total = exam["duration_mins"] * 60
        remaining = max(0, total - elapsed)
        mm, ss = divmod(remaining, 60)
        warn = "warning" if remaining < 5 * 60 else ""
        # Auto-refresh every 30s to update timer + trigger deadline auto-submit
        auto_refresh_js = f"""
        <script>
        (function(){{
          var remaining = {remaining};
          if (remaining <= 0) {{ window.parent.location.reload(); }}
          else {{ setTimeout(function(){{ window.parent.location.reload(); }}, Math.min(remaining * 1000, 30000)); }}
        }})();
        </script>
        """
        components.html(auto_refresh_js, height=0)
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
                questions=exam["questions"],
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
                <circle cx="60" cy="60" r="45" fill="none" stroke="#e2e8f0" stroke-width="8"/>
                <circle cx="60" cy="60" r="45" fill="none" stroke="{color}" stroke-width="8"
                  stroke-linecap="round" stroke-dasharray="{circumference}"
                  stroke-dashoffset="{offset}" transform="rotate(-90 60 60)"
                  style="transition:stroke-dashoffset 0.8s ease,stroke 0.4s ease"/>
                <text x="60" y="55" text-anchor="middle" font-size="20" font-weight="600"
                  fill="{color}" font-family="Inter,sans-serif">{pct:.0f}%</text>
                <text x="60" y="73" text-anchor="middle" font-size="11" fill="#64748b"
                  font-family="Inter,sans-serif">{status_text}</text>
              </svg>
              <div style="font-size:12px;color:#64748b;margin-top:4px">
                Check {len(st.session_state.auth_log)} · Next in ~30s
              </div>
            </div>
            </div>
            """
            st.markdown(gauge_html, unsafe_allow_html=True)
            if st.session_state.auth_log:
                st.markdown('<div class="tp-card">', unsafe_allow_html=True)
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
                st.markdown("</div>", unsafe_allow_html=True)
        if st.session_state.consecutive_fails >= 2:
            st.warning("Suspicious typing detected — re-verify on next check.")

    _student_layout(_content)


def _do_exam_submit(dm: DataManager, exam: Dict[str, Any]) -> None:
    """Persist the exam submission, integrity score and auth/cp logs."""
    auth_log = st.session_state.auth_log
    cp_log = st.session_state.cp_log
    avg_conf = (
        sum(a["confidence"] for a in auth_log) / len(auth_log) if auth_log else 0.0
    )
    score = _auto_grade_mcq(exam, st.session_state.exam_answers)
    integrity = dm.calculate_integrity_score(avg_conf, len(cp_log))
    dm.save_exam_submission(
        username=st.session_state.username,
        exam_id=exam["exam_id"],
        session_id=st.session_state.session_id,
        answers=st.session_state.exam_answers,
        auth_log=auth_log,
        cp_log=cp_log,
        score=score,
        integrity=integrity,
    )
    st.session_state.exam_submitted = True
    _goto("submitted")


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
            f'<a href="?back=1" style="color:#6366f1;font-size:13px;">← Back to course</a>',
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
        c = st.columns(3)
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
        elif page == "lab":      show_faculty_lab()
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
