# Project Documentation Rules (Non-Obvious Only)

- The only specification is `ocr-expense-helper.md` — `README.md` is empty.
- `*.db` / `*.sqlite3` files are gitignored, so there is no committed schema migration file; the DDL is defined entirely in `database.py`.
- `/app/uploads/` is gitignored — it does not exist in the repo; the app must create it at runtime.
- "弥生会計/マネーフォワード等のインポート形式に近い汎用CSV形式" (spec §2 export) means a generic CSV with headers `日付,金額,支払先,メモ` — no official spec document exists; use common sense for column order.
- Tesseract installation is an OS-level prerequisite not managed by `pip` — this is the most common setup failure; document it prominently for any user-facing README.
