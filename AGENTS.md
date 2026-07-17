# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack
- **Backend**: Python, FastAPI, SQLite (via `sqlite3` stdlib), `pytesseract` + `Pillow` for OCR
- **Frontend**: Vanilla HTML/CSS/JS + Tailwind CSS (CDN) — no build step, no npm
- **OCR engine**: Tesseract must be installed on the OS; `pytesseract` is the Python wrapper only
- No Docker config exists — run with `uvicorn app.main:app --reload`

## File Layout
```
/app/main.py       — FastAPI app, all endpoints, OCR call, regex parser
/app/database.py   — SQLite init, table DDL, CRUD helper functions
/frontend/index.html
/frontend/style.css
/frontend/script.js
```

## Critical Conventions

### Backend
- SQLite file lives at runtime alongside `main.py` — **`*.db` and `*.sqlite3` are gitignored**.
- FastAPI serves the frontend statically via `StaticFiles` mount on `/` — no separate dev server needed.
- File upload validation: **max 10 MB**, accept `image/jpeg` and `image/png` only (enforced in `POST /api/upload`).
- OCR call must pass `lang='jpn'` to `pytesseract.image_to_string()` — default (`eng`) will misread Japanese receipts.
- Regex parser for date/amount/vendor lives in `main.py`, not a separate module.
- CSV export (`GET /api/export`) returns a `StreamingResponse` with `Content-Disposition: attachment` — not a JSON blob.
- Table name is `expenses`; column names are `id`, `date`, `amount`, `vendor`, `raw_text`, `created_at` — match exactly in all queries.

### Frontend
- Tailwind CSS loaded via CDN only — do not introduce `package.json`.
- All API calls use `fetch()` against relative paths (`/api/...`) — no hardcoded host.
- Upload flow: drag-and-drop OR `<input type="file">` → `FormData` → `POST /api/upload` → inline edit form shown with returned JSON.
- CSV download trigger: `window.location.href = '/api/export'` (not `fetch`) so the browser handles file download natively.

## Running
```
# Install Python deps
pip install fastapi uvicorn pytesseract pillow

# Start server (from repo root)
uvicorn app.main:app --reload --port 8000

# Open browser
http://localhost:8000
```
- Tesseract OCR binary must be installed separately (`apt install tesseract-ocr tesseract-ocr-jpn` / Homebrew / Windows installer).
- **Windows 追加手順**: インストーラーは `jpn.traineddata` を同梱しない場合がある。`tesseract --list-langs` で `jpn` が表示されない場合は [tessdata releases](https://github.com/tesseract-ocr/tessdata/raw/main/jpn.traineddata) からダウンロードして `C:\Program Files\Tesseract-OCR\tessdata\` に配置する。
- `main.py` は `TESSDATA_PREFIX` 環境変数を `C:\Program Files\Tesseract-OCR\tessdata`（`tessdata` サブディレクトリまで含む）に設定済み — 別の場所にインストールした場合は変更すること。

## No Automated Tests
Manual smoke-test: upload a JPEG receipt → verify extracted fields → edit → delete → export CSV.
