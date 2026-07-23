"""
main.py — FastAPI アプリ本体
  - OCR (pytesseract) + 正規表現パーサー
  - CRUD エンドポイント
  - StaticFiles で /frontend を / にマウント
"""

import io
import os
import re
import csv
from pathlib import Path
from contextlib import asynccontextmanager

import numpy as np

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import pytesseract

# Windows 環境向け: tesseract.exe のパスと tessdata ディレクトリを明示
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

from app.database import init_db, create_expense, get_all_expenses, update_expense, delete_expense

# ────────────────────────────────────────────────────────────────────────────
# 定数
# ────────────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ────────────────────────────────────────────────────────────────────────────
# 正規表現パターン（日本語領収書向け）
# ────────────────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────
# 正規化ヘルパー
# ────────────────────────────────────────────────────────────────────────────

def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    OCR 精度を上げるための画像前処理。
    1. グレースケール化
    2. 300 DPI 相当になるよう拡大（短辺が 2000px 未満の場合）
    3. コントラスト強調（CLAHE 相当）→ 白飛び・黒潰れを防ぐ
    """
    # グレースケール
    img = img.convert("L")

    # 短辺が小さい場合は拡大（300dpi 相当に近づける）
    w, h = img.size
    min_side = min(w, h)
    if min_side < 2000:
        scale = 2000 / min_side
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # コントラスト強調: 二値化より穏やかな処理で白飛び・黒潰れを防ぐ
    # percentile ベースで正規化（暗部を黒・明部を白に引き延ばす）
    arr = np.array(img, dtype=np.float32)
    p_low  = float(np.percentile(arr, 5))   # 暗側 5%点
    p_high = float(np.percentile(arr, 95))  # 明側 95%点
    if p_high > p_low:
        arr = (arr - p_low) / (p_high - p_low) * 255.0
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    else:
        arr = arr.astype(np.uint8)
    return Image.fromarray(arr)


def _normalize(text: str) -> str:
    """OCR テキストの表記ゆれを正規化する。"""
    # 全角数字 → 半角
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 全角スペース → 半角
    text = text.replace("\u3000", " ")
    # 全角スラッシュ・各種ダッシュ → 半角
    text = text.replace("／", "/").replace("－", "-").replace("ー", "-")
    # en-dash / em-dash / ハイフンマイナス系 → 除去（金額末尾の「–」対策）
    text = re.sub(r"[\u2013\u2014\u2015\uFF0D]", "", text)
    # 丸数字（①〜㉟）→ 算用数字
    for i, c in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟", 1):
        text = text.replace(c, str(i))
    # OCR が「年」を「牛」「牟」「午」などに誤読するケースを補正
    text = re.sub(r"(\d{4})\s*[牛牟午]\s*", r"\1年", text)
    # OCR が「月」を「丹」「冂」などに誤読するケースを補正
    text = re.sub(r"(\d{1,2})\s*[丹冂]\s*", r"\1月", text)
    # 8桁 YYYYMMDD（スペースなし連結） → YYYY/MM/DD
    text = re.sub(r"\b(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b", r"\1/\2/\3", text)
    # 日付行に年・月・日の漢字なしで数字が "2023 6 1" のようにバラバラに並ぶケースを補正
    text = re.sub(r"\b(20\d{2})\s+(1[0-2]|0?[1-9])\s+(3[01]|[12]\d|0?[1-9])\b", r"\1/\2/\3", text)
    # 金額の数字間スペースを除去: "4 5 , 4 5 5" → "45,455"
    # 数字1文字 + スペース + 数字1文字 が連続するパターンを結合
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    # カンマ前後のスペース除去: "45 , 455" → "45,455"
    text = re.sub(r"\s*,\s*(?=\d)", ",", text)
    return text


# ────────────────────────────────────────────────────────────────────────────
# 正規表現パターン（_normalize 済みテキストに適用）
# ────────────────────────────────────────────────────────────────────────────

# 日付：2023年6月1日 / 2023/6/1 / 2023-06-01 / 令和5年6月1日 / R5.6.1
RE_DATE = re.compile(
    r"(?:"
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?"          # 西暦漢字
    r"|(\d{4})\s*[/\-\.]\s*(\d{1,2})\s*[/\-\.]\s*(\d{1,2})"     # 西暦スラッシュ等
    r"|(?:令和|平成|昭和|大正)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?"  # 元号
    r"|[RrHhSs]\s*(\d{1,2})\s*[\.年]\s*(\d{1,2})\s*[\.月]\s*(\d{1,2})"              # 略記
    r")"
)

# 金額：¥ 50,000 / ￥50000 / 50,000円 / 合計 50,000 / 金額 45,455
# ¥ と数字の間・数字間のスペースを吸収
# 末尾の「-」「–」は _normalize で除去済み
RE_AMOUNT = re.compile(
    r"(?:"
    # ラベル付き（合計/小計/税込/金額 など。スペース混じりに対応）
    r"(?:合\s*計|小\s*計|税\s*込\s*合\s*計|税\s*込|お\s*買\s*上\s*げ\s*合\s*計"
    r"|金\s*額|請\s*求\s*金\s*額|ご\s*請\s*求\s*金\s*額|領\s*収\s*金\s*額"
    r"|お\s*支\s*払\s*金\s*額|お\s*買\s*上\s*金\s*額)"
    r"\s*[¥￥\\Y]?\s*([\d][\d,\s]*)"
    r"|[¥￥\\Y]\s*([\d][\d,\s]*)"                                 # ¥/￥ 記号付き
    r"|([\d][\d,\s]*\d)\s*円"                                     # 〜円（2桁以上）
    r")"
)

# 支払先：「有限会社 スズキ」のように社名とスズキの間にスペースが入るケースも対応
RE_VENDOR_COMPANY = re.compile(
    r"((?:株式会社|有限会社|合同会社|一般社団法人|特定非営利活動法人)\s*\S[^\n]{0,29}"
    r"|\S[^\n]{0,29}(?:株式会社|有限会社|合同会社))"
)


# ────────────────────────────────────────────────────────────────────────────
# パーサー
# ────────────────────────────────────────────────────────────────────────────

def _clean_number(raw: str) -> int | None:
    """数字文字列からカンマ・スペースを除去して int に変換する。"""
    cleaned = re.sub(r"[,\s]", "", raw)
    try:
        return int(cleaned)
    except ValueError:
        return None


# 税抜・消費税ラベル（合算フォールバック用）
RE_TAX_EXCL = re.compile(
    r"(?:税\s*抜\s*(?:金\s*額)?|本\s*体\s*(?:価\s*格)?|小\s*計)"
    r"\s*[¥￥\\Y]?\s*([\d][\d,]*)"
)
RE_TAX_AMT = re.compile(
    r"(?:消\s*費\s*税\s*(?:額)?|税\s*額|内\s*消\s*費\s*税)"
    r"\s*[¥￥\\Y]?\s*([\d][\d,]*)"
)


def _extract_amounts(text: str) -> list[int]:
    """正規化済みテキストから金額候補を全て抽出して返す。"""
    results = []
    for m in RE_AMOUNT.finditer(text):
        raw = next(filter(None, m.groups()), None)
        if raw:
            val = _clean_number(raw)
            if val is not None and val >= 100:
                results.append(val)
    return results


def parse_ocr_text(text: str) -> dict:
    """OCR テキストから日付・金額・支払先を抽出して返す。"""
    text = _normalize(text)

    # ── 日付 ────────────────────────────────────────────────────
    date_str = ""
    m = RE_DATE.search(text)
    if m:
        g = m.groups()
        if g[0]:    # 西暦漢字 (2023年6月1日)
            y, mo, d = g[0], g[1], g[2]
        elif g[3]:  # 西暦スラッシュ (2023/6/1)
            y, mo, d = g[3], g[4], g[5]
        elif g[6]:  # 元号 (令和5年...)
            era_map = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911}
            era_name = re.search(r"令和|平成|昭和|大正", text)
            base = era_map.get(era_name.group() if era_name else "", 2018)
            y, mo, d = str(base + int(g[6])), g[7], g[8]
        else:       # 略記 R5.6.1
            y, mo, d = str(2018 + int(g[9])), g[10], g[11]
        date_str = f"{y}/{mo.zfill(2)}/{d.zfill(2)}"

    # ── 金額 ─────────────────────────────────────────────────────
    # 戦略1: 合計・¥記号・〜円 でマッチした全金額の最大値
    amounts = _extract_amounts(text)
    amount_val = max(amounts) if amounts else None

    # 戦略2（フォールバック）: 税抜金額 + 消費税額 を合算
    # → 戦略1で取れた値が「税抜金額」だけの可能性がある場合に使う
    #   判定: 税抜ラベル付き金額が最大値と一致 → 合算を試みる
    if amount_val is not None:
        m_excl = RE_TAX_EXCL.search(text)
        m_tax  = RE_TAX_AMT.search(text)
        if m_excl and m_tax:
            excl_val = _clean_number(m_excl.group(1))
            tax_val  = _clean_number(m_tax.group(1))
            if excl_val and tax_val:
                summed = excl_val + tax_val
                # 合算値が現在の最大値より大きければ採用
                if summed > amount_val:
                    amount_val = summed

    amount_str = f"¥{amount_val:,}" if amount_val else ""

    # ── 支払先（発行元） ─────────────────────────────────────────
    vendor_str = ""

    # 優先度1: スペース混じり誤認に対応した社名キーワード検索
    company_keywords = (
        r"(?:株\s*式\s*会\s*社"
        r"|有\s*限\s*会\s*社"
        r"|合\s*同\s*会\s*社"
        r"|一\s*般\s*社\s*団\s*法\s*人"
        r"|特\s*定\s*非\s*営\s*利\s*活\s*動\s*法\s*人)"
    )
    m = re.search(company_keywords + r"[^\n]{0,25}", text)
    if m:
        vendor_str = re.sub(r"\s+", "", m.group(0))[:30]
    else:
        # 優先度2: 「株」「有」「合」で始まる行（キーワード誤認でも先頭文字は合う可能性）
        for line in text.splitlines():
            s = line.strip()
            if re.match(r"^[株有合]", s) and len(s) >= 4:
                vendor_str = re.sub(r"\s+", "", s)[:30]
                break

        # 優先度3: 日本語文字を含む最初の意味ある行
        if not vendor_str:
            for line in text.splitlines():
                s = line.strip()
                if (len(s) >= 2
                        and re.search(r"[\u3040-\u9fff]", s)
                        and not re.match(r"^[\d¥￥,\s\-\.\+]+$", s)):
                    vendor_str = s[:40]
                    break

    return {"date": date_str, "amount": amount_str, "vendor": vendor_str}


# ────────────────────────────────────────────────────────────────────────────
# アプリ起動 / 停止
# ────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # テーブルを確実に作成してからリクエストを受け付ける
    yield


app = FastAPI(title="OCR 経費精算ヘルパー", lifespan=lifespan)


# ────────────────────────────────────────────────────────────────────────────
# API エンドポイント（/api/* は StaticFiles より先に定義すること）
# ────────────────────────────────────────────────────────────────────────────

def _run_ocr(img: Image.Image) -> str:
    """
    PSM 6（均一ブロック）と PSM 11（散在テキスト）の両方で OCR を実行し、
    結果を改行で連結して返す。
    - PSM 6: 本文・ラベル行を取りやすい
    - PSM 11: 中央の大きな孤立数字（合計金額）を取りやすい
    """
    text_psm6  = pytesseract.image_to_string(img, lang="jpn+eng", config="--psm 6  --oem 1")
    text_psm11 = pytesseract.image_to_string(img, lang="jpn+eng", config="--psm 11 --oem 1")
    return text_psm6 + "\n" + text_psm11


@app.post("/api/ocr-debug")
async def ocr_debug(file: UploadFile = File(...)):
    """開発用：OCR 生テキストをそのまま返す（本番では削除可）。"""
    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    img = _preprocess_image(img)
    raw_psm6  = pytesseract.image_to_string(img, lang="jpn+eng", config="--psm 6  --oem 1")
    raw_psm11 = pytesseract.image_to_string(img, lang="jpn+eng", config="--psm 11 --oem 1")
    raw_merged = raw_psm6 + "\n" + raw_psm11
    parsed = parse_ocr_text(raw_merged)
    return {
        "raw_psm6": raw_psm6,
        "raw_psm11": raw_psm11,
        "merged": raw_merged,
        "normalized": _normalize(raw_merged),
        "parsed": parsed,
    }


@app.post("/api/upload")
async def upload_receipt(file: UploadFile = File(...)):
    """画像を受け取り OCR → パース → DB 保存 → JSON 返却。"""
    # ── バリデーション ──────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="JPEG または PNG のみアップロード可能です。",
        )
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="ファイルサイズは 10MB 以内にしてください。",
        )

    # ── 画像前処理 + OCR（PSM 6 & 11 マージ）───────────────
    try:
        img = Image.open(io.BytesIO(contents))
        img = _preprocess_image(img)
        raw_text = _run_ocr(img)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 処理に失敗しました: {e}")

    # ── パース & 保存 ───────────────────────────────────────
    parsed = parse_ocr_text(raw_text)
    record = create_expense(
        date=parsed["date"],
        amount=parsed["amount"],
        vendor=parsed["vendor"],
        raw_text=raw_text,
    )
    return record


@app.get("/api/expenses")
def list_expenses():
    """全経費レコードを新着順で返す。"""
    return get_all_expenses()


@app.put("/api/expenses/{expense_id}")
def update_expense_endpoint(expense_id: int, body: dict):
    """
    指定 ID の日付・金額・支払先を部分更新する。
    リクエストボディ例: {"date": "2026/07/17", "amount": "¥5,000", "vendor": "株式会社○○"}
    """
    updated = update_expense(expense_id, body)
    if updated is None:
        raise HTTPException(status_code=404, detail="レコードが見つかりません。")
    return updated


@app.delete("/api/expenses/{expense_id}", status_code=204)
def delete_expense_endpoint(expense_id: int):
    """指定 ID のレコードを削除する。"""
    if not delete_expense(expense_id):
        raise HTTPException(status_code=404, detail="レコードが見つかりません。")


@app.get("/api/export")
def export_csv():
    """
    全経費データを BOM 付き UTF-8 CSV として返す。
    BOM (\ufeff) を先頭に付けることで Windows Excel が文字化けなく開ける。
    汎用列順: 日付, 金額, 支払先, メモ（raw_text は除外）
    """
    expenses = get_all_expenses()

    def generate():
        buf = io.StringIO()
        buf.write("\ufeff")  # BOM
        writer = csv.writer(buf)
        writer.writerow(["日付", "金額", "支払先", "登録日時"])
        for e in expenses:
            writer.writerow([e["date"], e["amount"], e["vendor"], e["created_at"]])
        yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


# ────────────────────────────────────────────────────────────────────────────
# 静的ファイル配信（API 定義の後に必ずマウント）
# ────────────────────────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
