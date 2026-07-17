"""
database.py — SQLite 初期化・テーブル定義・CRUD ヘルパー

テーブル: expenses
  id         INTEGER  PRIMARY KEY AUTOINCREMENT
  date       TEXT     日付（抽出値 or 手動入力）
  amount     TEXT     金額（抽出値 or 手動入力）
  vendor     TEXT     支払先（抽出値 or 手動入力）
  raw_text   TEXT     OCR 生テキスト
  created_at TEXT     登録日時（ISO 8601）
"""

import sqlite3
from pathlib import Path
from typing import Optional

# DB ファイルは app/ ディレクトリと同階層に配置
DB_PATH = Path(__file__).parent / "expenses.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict 風アクセスを可能にする
    return conn


def init_db() -> None:
    """テーブルが存在しない場合に作成する。アプリ起動時に必ず呼ぶ。"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT    NOT NULL DEFAULT '',
                amount     TEXT    NOT NULL DEFAULT '',
                vendor     TEXT    NOT NULL DEFAULT '',
                raw_text   TEXT    NOT NULL DEFAULT '',
                created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        conn.commit()


# ─── CRUD ────────────────────────────────────────────────────────────────────

def create_expense(
    date: str,
    amount: str,
    vendor: str,
    raw_text: str,
) -> dict:
    """新規レコードを挿入し、挿入後の行を dict で返す。"""
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO expenses (date, amount, vendor, raw_text)
            VALUES (:date, :amount, :vendor, :raw_text)
            """,
            {"date": date, "amount": amount, "vendor": vendor, "raw_text": raw_text},
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def get_all_expenses() -> list[dict]:
    """全レコードを新着順で返す。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_expense(expense_id: int, fields: dict) -> Optional[dict]:
    """指定フィールドのみ更新し、更新後の行を返す。存在しなければ None。"""
    allowed = {"date", "amount", "vendor"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = expense_id
    with _connect() as conn:
        conn.execute(f"UPDATE expenses SET {set_clause} WHERE id = :id", updates)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_expense(expense_id: int) -> bool:
    """削除成功なら True、対象なしなら False。"""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
    return cur.rowcount > 0
