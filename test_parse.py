"""
test_parse.py — 既存 DB の raw_text に対して新パーサーをテストする
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

from app.main import _normalize, parse_ocr_text
import sqlite3

db_path = os.path.join("app", "expenses.db")
conn = sqlite3.connect(db_path)
rows = conn.execute("SELECT id, raw_text FROM expenses ORDER BY id DESC LIMIT 3").fetchall()
conn.close()

for record_id, raw_text in rows:
    print(f"=== ID={record_id} 解析結果 ===")
    result = parse_ocr_text(raw_text)
    print(f"  日付:   {result['date']!r}")
    print(f"  金額:   {result['amount']!r}")
    print(f"  支払先: {result['vendor']!r}")
    print()
    print("  正規化テキスト:")
    for line in _normalize(raw_text).splitlines():
        if line.strip():
            print(f"    {line!r}")
    print()
