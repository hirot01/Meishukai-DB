from datetime import datetime
from pathlib import Path
import pandas as pd
from .config import AUDIT_FILE

def ensure_audit():
    """監査ログファイルがなければ作成"""
    if not AUDIT_FILE.exists():
        df = pd.DataFrame(columns=[
            "ts", "user", "action", "record_id", "name",
            "changed_fields", "before_json", "after_json"
        ])
        with pd.ExcelWriter(AUDIT_FILE, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="logs")

def _read_audit() -> pd.DataFrame:
    """監査ログを読み込み"""
    ensure_audit()
    try:
        return pd.read_excel(AUDIT_FILE, sheet_name="logs", engine="openpyxl")
    except Exception:
        return pd.DataFrame(columns=[
            "ts", "user", "action", "record_id", "name",
            "changed_fields", "before_json", "after_json"
        ])

def append_audit(action: str, user: str, before: dict|None, after: dict|None):
    """監査ログを追記"""
    ensure_audit()
    df = _read_audit()

    rec_id = (after or before or {}).get("id", "")
    name = (after or before or {}).get("name", "")
    changed = []
    if before and after:
        keys = set(before.keys()) | set(after.keys())
        changed = [k for k in keys if str(before.get(k)) != str(after.get(k))]

    row = {
        "ts": datetime.now(),
        "user": user or "-",
        "action": action,
        "record_id": rec_id,
        "name": name,
        "changed_fields": ", ".join(changed),
        "before_json": str(before or {}),
        "after_json": str(after or {}),
    }

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    with pd.ExcelWriter(AUDIT_FILE, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="logs")
