'use strict';

/* ===================================================
   script.js — フロントエンドロジック
   全 API 通信は相対パス (/api/...) で行う
   クライアント側の状態管理なし — 毎回 API から再取得
   =================================================== */

// ─── DOM 取得 ──────────────────────────────────────────────────────────────
const dropZone        = document.getElementById('drop-zone');
const fileInput       = document.getElementById('file-input');
const uploadSpinner   = document.getElementById('upload-spinner');
const uploadError     = document.getElementById('upload-error');

const resultSection   = document.getElementById('result-section');
const resultId        = document.getElementById('result-id');
const resultDate      = document.getElementById('result-date');
const resultAmount    = document.getElementById('result-amount');
const resultVendor    = document.getElementById('result-vendor');
const resultRaw       = document.getElementById('result-raw');
const btnSaveResult   = document.getElementById('btn-save-result');
const btnDiscardResult = document.getElementById('btn-discard-result');

const expensesTbody   = document.getElementById('expenses-tbody');
const emptyRow        = document.getElementById('empty-row');
const btnExport       = document.getElementById('btn-export');

const editModal       = document.getElementById('edit-modal');
const editForm        = document.getElementById('edit-form');
const editId          = document.getElementById('edit-id');
const editDate        = document.getElementById('edit-date');
const editAmount      = document.getElementById('edit-amount');
const editVendor      = document.getElementById('edit-vendor');
const btnModalCancel  = document.getElementById('btn-modal-cancel');

// ─── ユーティリティ ────────────────────────────────────────────────────────

function showError(msg) {
  uploadError.textContent = msg;
  uploadError.classList.remove('hidden');
}

function clearError() {
  uploadError.textContent = '';
  uploadError.classList.add('hidden');
}

function setUploading(loading) {
  if (loading) {
    dropZone.classList.add('hidden');
    uploadSpinner.classList.remove('hidden');
    uploadSpinner.classList.add('flex');
  } else {
    dropZone.classList.remove('hidden');
    uploadSpinner.classList.add('hidden');
    uploadSpinner.classList.remove('flex');
  }
}

// ─── アップロード処理 ──────────────────────────────────────────────────────

async function uploadFile(file) {
  clearError();
  setUploading(true);
  resultSection.classList.add('hidden');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'アップロードに失敗しました。' }));
      throw new Error(err.detail || 'アップロードに失敗しました。');
    }
    const data = await res.json();
    showResultForm(data);
    await loadExpenses();
  } catch (e) {
    showError(e.message);
  } finally {
    setUploading(false);
    // input をリセットして同じファイルを再アップロード可能にする
    fileInput.value = '';
  }
}

function showResultForm(data) {
  resultId.value     = data.id;
  resultDate.value   = data.date;
  resultAmount.value = data.amount;
  resultVendor.value = data.vendor;
  resultRaw.textContent = data.raw_text || '（テキストなし）';
  resultSection.classList.remove('hidden');
  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── 抽出結果の保存（手動修正後 PUT） ──────────────────────────────────────

btnSaveResult.addEventListener('click', async () => {
  const id = resultId.value;
  if (!id) return;

  try {
    const res = await fetch(`/api/expenses/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date:   resultDate.value.trim(),
        amount: resultAmount.value.trim(),
        vendor: resultVendor.value.trim(),
      }),
    });
    if (!res.ok) throw new Error('保存に失敗しました。');
    resultSection.classList.add('hidden');
    await loadExpenses();
  } catch (e) {
    showError(e.message);
  }
});

btnDiscardResult.addEventListener('click', async () => {
  // 破棄：DB には既に保存されているのでそのままにし、フォームだけ閉じる
  resultSection.classList.add('hidden');
});

// ─── ドラッグ&ドロップ ──────────────────────────────────────────────────────

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

dropZone.addEventListener('click', (e) => {
  // label 内の click と重複しないよう input への直接クリックのみ除外
  if (e.target === fileInput) return;
  fileInput.click();
});

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (file) uploadFile(file);
});

// ─── 経費一覧の取得・描画 ──────────────────────────────────────────────────

async function loadExpenses() {
  try {
    const res = await fetch('/api/expenses');
    if (!res.ok) throw new Error();
    const expenses = await res.json();
    renderTable(expenses);
  } catch {
    // テーブル描画失敗は致命的でないためサイレントに
  }
}

function renderTable(expenses) {
  // empty-row 以外をクリア
  Array.from(expensesTbody.querySelectorAll('tr:not(#empty-row)')).forEach(r => r.remove());

  if (expenses.length === 0) {
    emptyRow.classList.remove('hidden');
    return;
  }
  emptyRow.classList.add('hidden');

  expenses.forEach(e => {
    const tr = document.createElement('tr');
    tr.dataset.id = e.id;
    tr.innerHTML = `
      <td class="text-gray-700">${escHtml(e.date || '—')}</td>
      <td class="text-gray-700 font-medium">${escHtml(e.amount || '—')}</td>
      <td class="text-gray-700">${escHtml(e.vendor || '—')}</td>
      <td class="text-gray-400 text-xs">${escHtml(e.created_at || '')}</td>
      <td class="text-right whitespace-nowrap">
        <button
          class="btn-edit text-xs text-blue-600 hover:underline mr-3"
          data-id="${e.id}"
          data-date="${escAttr(e.date)}"
          data-amount="${escAttr(e.amount)}"
          data-vendor="${escAttr(e.vendor)}"
        >編集</button>
        <button
          class="btn-delete text-xs text-red-500 hover:underline"
          data-id="${e.id}"
        >削除</button>
      </td>
    `;
    expensesTbody.appendChild(tr);
  });
}

// XSS 防止ヘルパー
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function escAttr(str) {
  return String(str || '').replace(/"/g, '&quot;');
}

// ─── テーブル内ボタン（イベント委譲） ─────────────────────────────────────

expensesTbody.addEventListener('click', async (e) => {
  const editBtn   = e.target.closest('.btn-edit');
  const deleteBtn = e.target.closest('.btn-delete');

  if (editBtn) {
    openEditModal(editBtn.dataset);
  }

  if (deleteBtn) {
    const id = deleteBtn.dataset.id;
    if (!confirm('このレコードを削除しますか？')) return;
    try {
      const res = await fetch(`/api/expenses/${id}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error('削除に失敗しました。');
      await loadExpenses();
    } catch (err) {
      alert(err.message);
    }
  }
});

// ─── 編集モーダル ──────────────────────────────────────────────────────────

function openEditModal({ id, date, amount, vendor }) {
  editId.value     = id;
  editDate.value   = date  || '';
  editAmount.value = amount || '';
  editVendor.value = vendor || '';
  editModal.classList.remove('hidden');
}

function closeEditModal() {
  editModal.classList.add('hidden');
}

btnModalCancel.addEventListener('click', closeEditModal);

// モーダル背景クリックで閉じる
editModal.addEventListener('click', (e) => {
  if (e.target === editModal) closeEditModal();
});

editForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = editId.value;
  try {
    const res = await fetch(`/api/expenses/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date:   editDate.value.trim(),
        amount: editAmount.value.trim(),
        vendor: editVendor.value.trim(),
      }),
    });
    if (!res.ok) throw new Error('保存に失敗しました。');
    closeEditModal();
    await loadExpenses();
  } catch (err) {
    alert(err.message);
  }
});

// ─── CSV ダウンロード ───────────────────────────────────────────────────────
// fetch ではなく window.location でブラウザネイティブのダウンロードを使う
btnExport.addEventListener('click', () => {
  window.location.href = '/api/export';
});

// ─── 初期ロード ────────────────────────────────────────────────────────────
loadExpenses();
