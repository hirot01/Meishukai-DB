import streamlit as st
from .config import ADMIN_ROLE

# 開発用デフォルトユーザー（secrets.toml がない場合用）
DEFAULT_USERS = {
    "admin": {"password": "admin123", "role": "admin", "display": "管理者"},
    "guest": {"password": "guest", "role": "user", "display": "一般ユーザー"},
}

def login_ui():
    """サイドバーにログインUIを表示し、認証状態を返す"""
    if "auth" not in st.session_state:
        st.session_state.auth = {"ok": False, "user": None, "role": "user", "display": None}

    st.sidebar.header("🔐 ログイン")

    if not st.session_state.auth["ok"]:
        with st.sidebar.form("login_form", clear_on_submit=False):
            username = st.text_input("ユーザー名")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログイン")

        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.auth = {"ok": True, **user}
                st.success(f"ログインしました：{user['display']}（{user['role']}）")
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが違います。")
    else:
        u = st.session_state.auth
        st.markdown(f"**{u['display']}** としてログイン中（役割：`{u['role']}`）")
        if st.sidebar.button("ログアウト"):
            st.session_state.auth = {"ok": False, "user": None, "role": "user", "display": None}
            st.rerun()

    return st.session_state.auth


def authenticate(username: str, password: str):
    """認証ロジック（secrets.toml or デフォルト）"""
    try:
        users = st.secrets.get("users", {})
    except Exception:
        users = DEFAULT_USERS

    u = users.get(username)
    if not u or str(u.get("password")) != str(password):
        return None
    return {
        "user": username,
        "display": u.get("display", username),
        "role": u.get("role", "user"),
    }


def require_admin(session_user) -> bool:
    """管理者ロールか判定"""
    return bool(session_user and session_user.get("role") == ADMIN_ROLE)
