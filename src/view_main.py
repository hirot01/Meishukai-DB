import streamlit as st
import pandas as pd
import unicodedata
import re

from datetime import datetime
from .storage import (
    load_items, save_items,
    sort_members_by_frequency,
    bump_member_history, seed_member_history_from_items,
)
from .audit import append_audit

def normalize_member_name(s: str) -> str:
    if not s:
        return s
    s = unicodedata.normalize("NFKC", s)   # 全角→半角など
    s = s.strip()
    s = re.sub(r"\s+", " ", s)             # 連続空白を単一スペースに
    return s

def render_main_page(auth):
    """📦 データ管理ページ"""
    st.title("🍶 診断士迷酒会 DB（データ管理）")

    # ===== タブ構成 =====
    tabs = st.tabs(["📋 登録済みデータ", "📝 新規登録"])

    # -------------------------------------------------
    # 📋 登録済みデータタブ
    # -------------------------------------------------
    with tabs[0]:
        df = load_items()
        if df.empty:
            st.info("データがまだ登録されていません。")
        else:
            group_mode = st.toggle("📚 例会ごとにグループ表示", value=True)
            view = df.copy()

            import re
            
            # === 例会ラベル整形 ===
            def meeting_label(v: object) -> str:
                s = str(v).strip()
                if s in ["", "nan", "None"]:
                    return "登録承認待ち"
                if "第" in s and "回" in s:
                    return s
                try:
                    n = int(float(s))
                    return f"第{n}回"
                except Exception:
                    return s

            view["例会表示"] = view.get("例会", pd.Series([""] * len(view))).apply(meeting_label)

            # 会員氏名オプション（頻度順）
            seed_member_history_from_items(view)  # 履歴が空なら既存出現回数で初期化
            _name_base = (
                view["会員氏名"]
                .dropna()
                .astype(str).map(str.strip)
            )
            _name_base = [x for x in _name_base.unique().tolist() if x]
            name_opts = ["(すべて)"] + sort_members_by_frequency(sorted(_name_base))

            # 例会オプション（「登録承認待ち」→数値順）
            def _sort_meeting_key(x: str):
                if x == "登録承認待ち":
                    return (0, 0)
                m = re.search(r"\d+", str(x))
                num = int(m.group()) if m else 10**9
                return (1, num)

            meeting_opts = ["(すべて)"] + sorted(view["例会表示"].dropna().unique(), key=_sort_meeting_key)

            # UI（2カラム）
            c1, c2 = st.columns([1.2, 1])
            with c1:
                sel_name = st.selectbox("会員氏名で絞り込み", name_opts, index=0, key="search_member")
            with c2:
                sel_meeting = st.selectbox("例会で絞り込み", meeting_opts, index=0, key="search_meeting")

            # 絞り込み適用
            if sel_name != "(すべて)":
                target = normalize_member_name(sel_name)
                view["_name_norm"] = view["会員氏名"].astype(str).map(normalize_member_name)
                view = view[view["_name_norm"] == target].drop(columns=["_name_norm"], errors="ignore")

            if sel_meeting != "(すべて)":
                view = view[view["例会表示"] == sel_meeting]

            # === 精米歩合の安全整形 ===
            def fmt_seimai(x) -> str:
                s = str(x).strip()
                if s in ("", "nan", "None", "-"):
                    return ""
                # 数値が含まれていれば最初の数値を抽出
                m = re.search(r"\d+(\.\d+)?", s)
                if m:
                    v = float(m.group())
                    if v <= 1:  # 0.55 → 55%
                        v *= 100
                    return f"{v:.0f}％"
                # 数値が見つからない場合（例：「麹米40％、掛米55％」など）はそのまま返す
                return s

            if "精米歩合" in view.columns:
                view["精米歩合"] = view["精米歩合"].apply(fmt_seimai).astype(str)

            # === 表示対象列（idは除外） ===
            display_cols = ["name", "蔵元", "地域", "category", "会員氏名", "精米歩合", "備考", "例会表示"]
            display_cols = [c for c in display_cols if c in view.columns]

            # === グループ表示 ===
            if group_mode:
                import re
                def group_sort_key(label: str) -> tuple[int, int]:
                    if label == "登録承認待ち":
                        return (0, -1)  # ← 最優先で先頭
                    m = re.search(r"\d+", label)
                    num = int(m.group()) if m else 9999
                    return (1, num)

                for key in sorted(view["例会表示"].unique(), key=group_sort_key):
                    g = view[view["例会表示"] == key]
                    st.markdown(f"**■ 例会: {key}（{len(g)}件）**")
                    st.dataframe(
                        g[display_cols],
                        width="stretch",
                        hide_index=True
                    )
            else:
                st.dataframe(view[display_cols], width="stretch", hide_index=True)

            # --- 管理者だけ：例会番号の付与/編集 -------------------------
            if auth.get("role") == "admin":
                import re

                st.divider()
                st.subheader("🗂 例会番号の付与 / 編集（管理者）")

                df_all = df  # 表示に使った df をそのまま使う

                # 登録承認待ち（例会 未設定）を抽出
                is_pending = df_all.get("例会").isna() | (df_all.get("例会").astype(str).str.strip() == "")
                pending_df = df_all[is_pending]

                mode = st.radio(
                    "対象の選び方",
                    ["登録承認待ちのみ", "全データから選ぶ"],
                    horizontal=True,
                    key="meeting_edit_scope"
                )
                candidates = pending_df if mode == "登録承認待ちのみ" else df_all

                if candidates.empty:
                    st.info("現在、付与/編集対象の候補がありません。")
                else:
                    # レコード選択（複数可）
                    def label_for(i: int) -> str:
                        row = candidates.loc[i]
                        rid = row.get("id")
                        nm  = str(row.get("name", ""))
                        mem = str(row.get("会員氏名", ""))
                        mt  = str(row.get("例会", "")).strip() or "登録承認待ち"
                        return f"[id:{rid}] {mem} / {nm} / 例会:{mt}"

                    indices = candidates.index.tolist()
                    chosen = st.multiselect(
                        "対象レコード（複数選択可）",
                        options=indices,
                        format_func=label_for
                    )

                    colA, colB = st.columns([1,1])
                    with colA:
                        meeting_input = st.text_input("付与する例会番号（例：8 または 第8回）", placeholder="8")
                    with colB:
                        clear_flag = st.checkbox("空欄にして『登録承認待ち』へ戻す", value=False)

                    apply_btn = st.button("🔧 適用", type="primary")

                    if apply_btn:
                        if not chosen:
                            st.error("レコードを選択してください。")
                        else:
                            # 入力正規化
                            def normalize_meeting(s: str | None):
                                if clear_flag:
                                    return None
                                s = (s or "").strip()
                                if not s:
                                    return None
                                m = re.search(r"\d+", s)
                                return str(int(m.group())) if m else None  # 例会列には「数字文字列」を格納

                            new_val = normalize_meeting(meeting_input)
                            before_rows = df_all.loc[chosen].copy()

                            # 例会を更新
                            df_all.loc[chosen, "例会"] = new_val

                            # 保存 & 監査ログ
                            save_items(df_all)
                            for _, b in before_rows.iterrows():
                                rid = b.get("id")
                                after = df_all[df_all["id"] == rid].iloc[0].to_dict()
                                append_audit(
                                    action="update_meeting",
                                    user=auth.get("user"),
                                    before=b.to_dict(),
                                    after=after,
                                )

                            st.success(f"{len(chosen)}件に適用しました。")
                            st.cache_data.clear()

        # === 管理者専用の保存ボタン ===
        if auth.get("role") == "admin":
            st.divider()
            st.subheader("✏️ 管理者編集")
            if st.button("💾 データ保存"):
                save_items(df)
                append_audit("manual_save", user=auth.get("user"), before=None, after="save")
                st.success("保存しました。")

        # === 管理者専用：一括削除 ===
        if auth.get("role") == "admin" and not df.empty:
            st.divider()
            st.subheader("🗑️ 一括削除（管理者）")

            df_all = load_items()

            # ① 表示用IDラベル（見やすさ用）
            view_del = df_all.copy()
            view_del["ラベル"] = (
                "[id:" + df_all["id"].astype(str) + "] "
                + df_all.get("name", "").astype(str)
                + " / " + df_all.get("会員氏名", "").astype(str)
                + " / " + df_all.get("蔵元", "").astype(str)
            )

            # ② 絞り込み（任意）
            c1, c2 = st.columns(2)
            with c1:
                q_del = st.text_input("🔎 フリーワード（銘柄 / 会員 / 蔵元 / 地域 / 種別）", "")
            with c2:
                # 例会表示を使って「登録承認待ち」などで絞る（任意）
                def meeting_label(v: object) -> str:
                    s = str(v).strip()
                    if s in ["", "nan", "None"]:
                        return "登録承認待ち"
                    if "第" in s and "回" in s:
                        return s
                    try:
                        n = int(float(s))
                        return f"第{n}回"
                    except Exception:
                        return s
                view_del["例会表示"] = view_del.get("例会", pd.Series([""] * len(view_del))).apply(meeting_label)


                def _sort_meeting_key(x: str):
                    if x == "登録承認待ち":
                        return (0, 0)
                    m = re.search(r"\d+", str(x))
                    num = int(m.group()) if m else 10**9  # 数字が無いものは最後へ
                    return (1, num)

                options_meeting_sorted = sorted(view_del["例会表示"].dropna().unique(), key=_sort_meeting_key)
                options_meeting = ["(すべて)"] + options_meeting_sorted

                sel_meeting = st.selectbox("例会で絞り込み", options_meeting, index=0)

            # ③ 絞り込み適用
            filt = view_del.copy()
            if q_del:
                ql = q_del.lower()
                def contains(s: pd.Series) -> pd.Series:
                    return s.fillna("").astype(str).str.lower().str.contains(ql, na=False)
                filt = filt[
                    contains(filt.get("name", pd.Series([""]*len(filt))))
                    | contains(filt.get("会員氏名", pd.Series([""]*len(filt))))
                    | contains(filt.get("蔵元", pd.Series([""]*len(filt))))
                    | contains(filt.get("地域", pd.Series([""]*len(filt))))
                    | contains(filt.get("category", pd.Series([""]*len(filt))))
                ]
            if sel_meeting != "(すべて)":
                filt = filt[filt["例会表示"] == sel_meeting]

            # ④ 複数選択 → 削除
            if filt.empty:
                st.info("該当するレコードがありません。")
            else:
                # IDのリストと表示ラベル
                id_list = filt["id"].tolist()
                label_map = {int(r["id"]): r["ラベル"] for _, r in filt.iterrows()}

                chosen = st.multiselect(
                    "削除対象を選択（複数可）",
                    options=id_list,
                    format_func=lambda rid: label_map.get(int(rid), f"[id:{rid}]"),
                )

                colx, coly = st.columns([1,1])
                with colx:
                    confirm = st.text_input("確認のため DELETE と入力", help="大文字で DELETE と入力すると削除できます。")
                with coly:
                    do_delete = st.button("🗑️ 選択したレコードを削除", type="secondary", disabled=(len(chosen)==0 or confirm != "DELETE"))

                if do_delete:
                    # 監査のため削除前スナップショット
                    before_rows = df_all[df_all["id"].isin(chosen)].copy()

                    # 実削除
                    df_after = df_all[~df_all["id"].isin(chosen)].copy()
                    save_items(df_after)

                    # 監査ログ（1件ずつ）
                    for _, b in before_rows.iterrows():
                        append_audit(
                            action="delete",
                            user=auth.get("user"),
                            before=b.to_dict(),
                            after=None
                        )

                    st.success(f"🗑️ {len(chosen)}件を削除しました。")
                    st.cache_data.clear()
                    st.rerun()

            # === 管理者専用: 例会番号登録フォーム ===
            st.subheader("🗂️ 登録承認待ち → 例会番号付与")

            pending = df[df.get("例会", "") == "登録承認待ち"]
            if pending.empty:
                st.info("現在、登録承認待ちのデータはありません。")
            else:
                target = st.selectbox(
                    "対象データを選択（会員氏名 - 銘柄名）",
                    options=[
                        f"{row['id']}: {row['会員氏名']} - {row['name']}"
                        for _, row in pending.iterrows()
                    ]
                )
                meeting_input = st.text_input("付与する例会番号（数字のみ、例：8）")

                if st.button("📌 例会番号を登録"):
                    import re
                    m = re.fullmatch(r"\d+", meeting_input.strip())
                    if not m:
                        st.error("⚠️ 数字のみで入力してください。")
                    else:
                        meeting_num = f"第{int(meeting_input)}回"
                        target_id = int(target.split(":")[0])
                        df.loc[df["id"] == target_id, "例会"] = meeting_num
                        save_items(df)
                        append_audit("update_meeting", user=auth.get("user"), before=None, after={"id": target_id, "例会": meeting_num})
                        st.success(f"✅ ID {target_id} のデータに {meeting_num} を登録しました！")
                        st.cache_data.clear()

    # -------------------------------------------------
    # 📝 新規登録タブ
    # -------------------------------------------------
    with tabs[1]:
        st.subheader("🆕 新規登録フォーム")

        with st.form("entry_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                # 既存会員の候補を用意（頻度順）
                _df_names = load_items()
                seed_member_history_from_items(_df_names)
                _base = _df_names["会員氏名"].dropna().astype(str).map(str.strip)
                _base = [x for x in _base.unique().tolist() if x]
                _member_names_sorted = sort_members_by_frequency(sorted(_base))

                st.markdown("**会員氏名**")
                mode = st.radio(
                    "会員の選択方法",
                    ["既存から選ぶ", "新規入力"],
                    horizontal=True,
                    label_visibility="collapsed",
                    key="member_mode_new",
                )

                if mode == "既存から選ぶ":
                    _selected = st.selectbox(
                        "既存会員",
                        _member_names_sorted,
                        index=None,
                        placeholder="選択してください",
                        key="member_select_existing",
                    )
                    kaiin = (_selected or "").strip()
                else:
                    kaiin = st.text_input(
                        "新規会員氏名",
                        value="",
                        placeholder="氏名を入力",
                        key="member_input_new",
                    ).strip()

                meigara = st.text_input("銘柄名")
                kuramoto = st.text_input("蔵元（例：油長酒造）")
                
            with col2:
                chiiki = st.text_input("地域（例：奈良県御所市）")
                category = st.text_input("種別（例：純米吟醸、本醸造など）")
                seimai = st.text_input("精米歩合（％・半角数字のみ）", help="例：60")
                bikou = st.text_area("備考", height=80)

            submitted = st.form_submit_button("📤 登録する")

            if submitted:
                has_error = False

                # ★正規化（必ず最初に）
                kaiin = normalize_member_name(kaiin)
                meigara = meigara.strip()
                kuramoto = kuramoto.strip()
                chiiki = chiiki.strip()
                category = category.strip()
                seimai = seimai.strip()
                bikou = bikou.strip()

                # === バリデーション ===
                if not kaiin.strip() or not meigara.strip():
                    st.error("⚠️ 会員氏名と銘柄名は必須です。")
                    has_error = True

                import re
                if seimai and not re.fullmatch(r"[0-9]+(\.[0-9]+)?", seimai):
                    st.error("⚠️ 精米歩合は半角数字（小数点可）のみで入力してください。")
                    has_error = True

                if has_error:
                    st.warning("⚠️ 入力内容を修正してからもう一度送信してください。")
                    return

                # === 登録処理 ===
                df = load_items()
                next_id = int(pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").fillna(0).max()) + 1

                new_row = pd.DataFrame([
                    {
                        "id": next_id,
                        "会員氏名": kaiin.strip(),
                        "name": meigara.strip(),
                        "蔵元": kuramoto.strip(),
                        "地域": chiiki.strip(),
                        "category": category.strip(),
                        "精米歩合": seimai.strip(),
                        "updated_at": datetime.now(),
                        "備考": bikou.strip(),
                        "例会": "登録承認待ち",
                        # 例会は未設定で登録 → 「登録承認待ち」グループへ入る
                    }
                ])

                df = pd.concat([df, new_row], ignore_index=True)
                save_items(df)

                bump_member_history(kaiin.strip())

                append_audit("add", user=auth.get("user"), before=None, after=new_row.iloc[0].to_dict())
                st.success("✅ 登録しました！")
                st.cache_data.clear()

