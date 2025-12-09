import streamlit as st
import pandas as pd
from pathlib import Path
from .storage import save_items
from .config import DATA_FILE, SHEET_NAME, STYLE_CANDIDATES
from datetime import datetime

def importer_ui(is_admin: bool):
    """管理者専用：Excelアップロード＋列マッピングUI"""
    if not is_admin:
        return  # 一般ユーザーには非表示

    st.sidebar.header("⚙️ 設定（取り込み）")

    uploaded = st.sidebar.file_uploader(
        "既存Excelをアップロード",
        type=["xlsx"],
        accept_multiple_files=False
    )

    if not uploaded:
        return

    try:
        xls = pd.ExcelFile(uploaded, engine="openpyxl")
        sheet = st.sidebar.selectbox("読み込むシート", options=xls.sheet_names, index=0)
        df_raw = pd.read_excel(xls, sheet_name=sheet, engine="openpyxl")
        st.sidebar.success(f"シート '{sheet}' を読み込みました。")

        with st.expander("🔎 生データプレビュー（先頭20行）", expanded=False):
            st.dataframe(df_raw.head(20), use_container_width=True)

        st.subheader("🔁 列の対応付け（Mapping）")

        guessed = guess_mapping(list(df_raw.columns))
        cols = [None] + list(df_raw.columns)

        mapping = {}
        for col in ["id", "name", "category", "quantity", "updated_at",
                    "会員氏名", "蔵元", "地域", "精米歩合", "備考", "例会", "例会日時"]:
            mapping[col] = st.selectbox(
                f"{col}",
                options=cols,
                index=cols.index(guessed[col]) if guessed[col] in cols else 0,
                key=f"map_{col}"
            )

        # 種別自動抽出
        style_cols = st.multiselect(
            "🧪 種別に使う列（値が入っている列名をcategoryに採用）",
            options=list(df_raw.columns),
            default=[c for c in STYLE_CANDIDATES if c in df_raw.columns]
        )

        if st.button("✅ この対応で取り込む（data.xlsxに保存）", type="primary"):
            df_norm = normalize_df(df_raw, mapping, style_cols)
            save_items(df_norm)
            st.success("取り込み＆保存が完了しました。")
            st.cache_data.clear()

    except Exception as e:
        st.error(f"読み込みでエラー：{e}")


def guess_mapping(cols):
    """列名の自動推測（ゆるめ）"""
    s = [str(c) for c in cols]
    def find(keys):
        for c in s:
            lc = c.lower()
            for k in keys:
                if k.lower() in lc:
                    return c
        return None

    mapping = {k: None for k in [
        "id", "name", "category", "quantity", "updated_at",
        "会員氏名", "蔵元", "地域", "精米歩合", "備考", "例会", "例会日時"
    ]}

    mapping["name"] = find(["銘柄", "商品名", "名称", "品名", "name"])
    mapping["updated_at"] = find(["例会日時", "更新日", "updated_at"])
    mapping["category"] = find(["カテゴリ", "区分", "分類", "category"])
    mapping["id"] = find(["id", "番号", "no"])
    mapping["quantity"] = find(["数量", "在庫", "qty"])
    mapping["会員氏名"] = find(["会員氏名", "氏名"])
    mapping["蔵元"] = find(["蔵元", "メーカー", "酒造"])
    mapping["地域"] = find(["地域", "都道府県"])
    mapping["精米歩合"] = find(["精米歩合", "歩合"])
    mapping["備考"] = find(["備考", "メモ"])
    mapping["例会"] = find(["例会"])
    mapping["例会日時"] = find(["例会日時"])
    return mapping


def normalize_df(df_raw: pd.DataFrame, mapping: dict, style_cols: list[str]) -> pd.DataFrame:
    """アップロードされたExcelを標準スキーマに変換"""
    out = pd.DataFrame()
    for tgt, src in mapping.items():
        out[tgt] = df_raw[src] if src in df_raw.columns else None

    # 日付・数値整形
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce").fillna(0).astype(int)
    out["updated_at"] = pd.to_datetime(out["updated_at"], errors="coerce").fillna(datetime.now())

    # category未設定ならstyle_colsから自動抽出
    if mapping.get("category") is None:
        def pick_style(row):
            for col in style_cols:
                if col in row.index:
                    v = row[col]
                    if pd.notna(v) and str(v).strip() not in ["", "0", "False", "×", "✕", "✖"]:
                        return col
            return None
        out["category"] = df_raw.apply(pick_style, axis=1)

    return out
