import streamlit as st
import pandas as pd
from .audit import _read_audit

def render_audit_page(auth):
    import streamlit as st
    from .audit import _read_audit

    if auth.get("role") != "admin":
        st.warning("このページは管理者のみが閲覧できます。")
        return

    st.subheader("🪵 変更履歴（最新100件）")

    logs = _read_audit()
    if logs.empty:
        st.info("履歴はまだありません。")
    else:
        logs = logs.sort_values("ts", ascending=False).head(100)
        st.dataframe(logs, use_container_width=True, hide_index=True)


