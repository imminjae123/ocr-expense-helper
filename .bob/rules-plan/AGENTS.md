# Project Architecture Rules (Non-Obvious Only)

- FastAPI serves both the API (`/api/*`) and the static frontend (`/`) from a single process — there is no separate frontend server or reverse proxy.
- SQLite is the only database; there is no ORM (SQLAlchemy etc.) — all queries use the `sqlite3` stdlib with parameterised statements.
- The regex-based parser (date/amount/vendor) is intentionally simple and embedded in `main.py` — it is expected to misfire on unusual receipts; the edit UI is the designed correction path, not a smarter parser.
- No authentication layer is specified — this is a local-only tool; do not plan for multi-user or auth features.
- Image files are processed in-memory (Pillow → pytesseract) and need not be persisted; the `/app/uploads/` directory is optional and only needed if you choose to save originals.
- CSV export streams the full `expenses` table — there is no pagination or filtering; this is acceptable because the dataset is personal/local scale.
