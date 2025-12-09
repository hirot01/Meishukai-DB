from pathlib import Path

# ファイル/シート設定
DATA_FILE = Path("data.xlsx")
AUDIT_FILE = Path("audit_log.xlsx")
SHEET_NAME = "items"

# スキーマ
CORE_FIELDS = ["id", "name", "category", "quantity", "updated_at"]
EXTRA_FIELDS = ["会員氏名", "蔵元", "地域", "精米歩合", "備考", "例会", "例会日時"]
TARGET_FIELDS = CORE_FIELDS + EXTRA_FIELDS

# 権限ロール名
ADMIN_ROLE = "admin"
USER_ROLE = "user"

# 日本酒の“種別”候補（列名として来る想定）
STYLE_CANDIDATES = [
    "本醸造", "特別本醸造", "純米", "特別純米",
    "吟醸", "純米吟醸", "大吟醸", "純米大吟醸", "その他"
]