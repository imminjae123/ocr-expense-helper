"""
check_db.py — DB の中身をコマンドラインで確認するスクリプト
使い方:
  python check_db.py           # 一覧表示
  python check_db.py raw <id>  # 指定 ID の OCR 生テキストを表示
"""
import sys
import os
import sqlite3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_PATH = os.path.join(os.path.dirname(__file__), "app", "expenses.db")

if not os.path.exists(DB_PATH):
    print(f"DB が見つかりません: {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# --- サブコマンド: raw <id> ---
if len(sys.argv) == 3 and sys.argv[1] == "raw":
    target_id = int(sys.argv[2])
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (target_id,)).fetchone()
    conn.close()
    if row is None:
        print(f"ID={target_id} は見つかりません。")
        sys.exit(1)
    print(f"=== ID={target_id} raw_text ===")
    print(row["raw_text"])
    print()
    print(f"=== 行ごと (repr) ===")
    for i, line in enumerate(row["raw_text"].splitlines()):
        if line.strip():
            print(f"{i:3d}: {repr(line)}")
    sys.exit(0)

# --- デフォルト: 一覧表示 ---
rows = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
conn.close()

if not rows:
    print("レコードがありません。")
    sys.exit(0)

print(f"{'ID':>4}  {'日付':<13}  {'金額':<13}  {'支払先':<22}  登録日時")
print("─" * 80)

for r in rows:
    print(
        f"{r['id']:>4}  "
        f"{(r['date']  or '(未抽出)'):<13}  "
        f"{(r['amount'] or '(未抽出)'):<13}  "
        f"{(r['vendor'] or '(未抽出)'):<22}  "
        f"{r['created_at'] or ''}"
    )

print()
print(f"合計 {len(rows)} 件")
print()
print("ヒント: OCR 生テキストを見るには → python check_db.py raw <ID>")
