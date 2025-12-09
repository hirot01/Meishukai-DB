import streamlit as st
from src.config import *
from src.auth import login_ui
from src.importer import importer_ui
from src.view_main import render_main_page
from src.view_audit import render_audit_page

st.set_page_config(
    page_title="Excel DB App (Modularized)",
    page_icon="🍶",
    layout="wide"
)

# === ログイン ===
auth = login_ui()
IS_ADMIN = auth.get("role") == "admin"

# === 管理者専用：Excel取り込み ===
importer_ui(IS_ADMIN)

# === ページ選択 ===
st.sidebar.divider()

page = st.sidebar.radio("ページ選択", ["📋 データ管理", "🪵 監査ログ"])
if page == "📋 データ管理":
    render_main_page(auth)
elif page == "🪵 監査ログ":
    render_audit_page(auth)