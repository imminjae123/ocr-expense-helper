# Project Coding Rules (Non-Obvious Only)

- `pytesseract.image_to_string(img, lang='jpn')` — `lang` param is mandatory; omitting it defaults to English and corrupts Japanese text extraction.
- `database.py` must call `init_db()` at import time (or FastAPI `lifespan`), NOT lazily per-request — the table must exist before the first upload hits.
- `PUT /api/expenses/{id}` accepts a JSON body with only the fields to update; use SQLite `UPDATE … SET` with named params — do not reconstruct the full row.
- `GET /api/export` must set `media_type="text/csv"` and include a BOM (`\ufeff`) so Excel opens the file without encoding errors on Windows.
- File size check: read `file.size` on the `UploadFile` object in FastAPI — do **not** read the entire file into memory first to measure it.
- Regex patterns for date (`\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2}`), amount (`[¥￥]?\s*[\d,]+\s*円?`), vendor (first non-empty line or `株式会社|有限会社` context) must be in `main.py`.
- `uploads/` directory (`/app/uploads/`) is gitignored — create it programmatically with `pathlib.Path.mkdir(exist_ok=True)` on startup if temporary image storage is needed.
- Frontend `script.js` must re-fetch `GET /api/expenses` after every upload, edit, and delete to keep the table in sync — no client-side state management.
