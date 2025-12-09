from datetime import datetime
from pathlib import Path
import pandas as pd
from typing import Tuple
from .config import DATA_FILE, SHEET_NAME, TARGET_FIELDS

def ensure_file(path: Path):
    """ファイルがなければ空のExcelを作る"""
    if not path.exists():
        df = pd.DataFrame(columns=TARGET_FIELDS)
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=SHEET_NAME)

def load_items() -> pd.DataFrame:
    """Excel → DataFrame"""
    ensure_file(DATA_FILE)
    df = pd.read_excel(DATA_FILE, sheet_name=SHEET_NAME, engine="openpyxl")
    # 欠損列を補完して順序を固定
    for c in TARGET_FIELDS:
        if c not in df.columns:
            df[c] = None
    return df[TARGET_FIELDS].copy()

def save_items(df: pd.DataFrame) -> None:
    """DataFrame → Excel"""
    if "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce").fillna(datetime.now())
    with pd.ExcelWriter(DATA_FILE, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=SHEET_NAME)

# ==============================
# 会員氏名の選択頻度管理
# ==============================
from collections import Counter
import json

_DATA_DIR = Path(".data")  # 保存用ディレクトリ
_DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = _DATA_DIR / "member_select_history.json"

def load_member_history() -> Counter:
    """会員氏名の選択頻度を読み込む（なければ空のCounter）"""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Counter(data)
    return Counter()

def save_member_history(counter: Counter) -> None:
    """頻度データを保存"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(counter, f, ensure_ascii=False, indent=2)

def bump_member_history(name: str) -> Counter:
    """指定氏名のカウントを+1して保存"""
    counter = load_member_history()
    counter[name] += 1
    save_member_history(counter)
    return counter

def sort_members_by_frequency(member_names) -> list[str]:
    """頻度（降順）→氏名（昇順）の優先でソートしたリストを返す"""
    counter = load_member_history()
    cleaned = [x for x in member_names if x and str(x).strip()]
    return sorted(cleaned, key=lambda x: (-counter.get(x, 0), str(x)))

# 初期ブートストラップ：履歴が空なら既存データの出現回数で初期化
def seed_member_history_from_items(df: pd.DataFrame) -> None:
    from collections import Counter
    counter = load_member_history()
    if counter:  # もう履歴があれば何もしない
        return
    if "会員氏名" not in df.columns:
        return
    ser = df["会員氏名"].dropna().astype(str).map(str.strip)
    ser = ser[ser != ""]
    if ser.empty:
        return
    base_counts = Counter(ser.tolist())
    # 既存データの出現回数で初期値を入れる
    for k, v in base_counts.items():
        counter[k] += int(v)
    save_member_history(counter)
