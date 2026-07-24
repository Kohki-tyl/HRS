// ==========================================
// HRS フロントデスク（管理者）画面
// ==========================================

let reservationsData = [];
let checkinData = [];
let checkoutData = [];

const TOKEN_KEY = 'hrs_admin_token';

const STATUS_LABELS = {
    'Created': '予約済み',
    'CheckedIn': 'チェックイン済み',
    'Completed': 'チェックアウト済み',
    'Cancelled': 'キャンセル済み',
};
const STATUS_CLASS = {
    'Created': 'created', 'CheckedIn': 'checked-in', 'Completed': 'completed', 'Cancelled': 'cancelled',
};
const STATUS_ORDER = { 'Created': 0, 'CheckedIn': 1, 'Completed': 2, 'Cancelled': 3 };

// 表示する列と、ソート用のキー抽出・セル描画
const COLUMNS = [
    { key: 'reservation_number', label: '予約番号', sort: r => r.reservation_number, cell: r => `<span class="tnum">${escapeHtml(r.reservation_number)}</span>` },
    { key: 'guest_name', label: '予約名', sort: r => r.guest_name || '', cell: r => escapeHtml(r.guest_name) },
    { key: 'staying_date', label: '宿泊日', sort: r => r.staying_date || '', cell: r => `<span class="tnum">${escapeHtml(r.staying_date)}</span>` },
    { key: 'rooms', label: '部屋', sort: r => (r.room_numbers || [])[0] ?? 0, cell: r => `<span class="tnum">${escapeHtml((r.room_numbers || []).join(', '))}</span>` },
    { key: 'total_amount', label: '料金', sort: r => r.total_amount ?? 0, cell: r => `<span class="tnum">${escapeHtml(r.total_amount)}円</span>` },
    { key: 'status', label: '状態', sort: r => STATUS_ORDER[r.status] ?? 9, cell: r => statusBadge(r.status) },
];

// ビューごとのソート状態（dir: 1=昇順, -1=降順）
const sortState = {
    res: { key: 'staying_date', dir: 1 },
    ci: { key: 'reservation_number', dir: 1 },
    co: { key: 'reservation_number', dir: 1 },
};

// ==========================================
// ユーティリティ
// ==========================================

function el(id) { return document.getElementById(id); }
function setLoading(on) { el('loading').classList.toggle('hidden', !on); }
function escapeHtml(v) {
    return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function statusBadge(status) {
    return `<span class="status-badge ${STATUS_CLASS[status] || 'created'}">${escapeHtml(STATUS_LABELS[status] || status)}</span>`;
}
// 現在日時を「2026年7月25日 1時05分現在」の形式で返す
function nowLabel() {
    const d = new Date();
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${d.getHours()}時${String(d.getMinutes()).padStart(2, '0')}分現在`;
}
let clockTimer = null;
function updateClock() {
    const label = nowLabel();
    const ci = el('ci-today'), co = el('co-today');
    if (ci) ci.textContent = label;
    if (co) co.textContent = label;
}
function getToken() { return sessionStorage.getItem(TOKEN_KEY) || ''; }

let toastTimer = null;
function toast(text, type = 'success') {
    const t = el('toast');
    t.textContent = text;
    t.className = `toast ${type}`;
    t.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.add('hidden'), 2600);
}

async function apiCall(endpoint, method = 'GET', params = null, body = null) {
    let url = endpoint;
    if (params) {
        const qs = new URLSearchParams(params).toString();
        url = qs ? `${endpoint}?${qs}` : endpoint;
    }
    const options = { method, headers: { 'Content-Type': 'application/json', 'X-Admin-Token': getToken() } };
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(url, options);
    if (response.status === 401) { logout(); throw new Error('認証が切れました。再度ログインしてください。'); }
    if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
    return await response.json();
}

// ==========================================
// ログイン / ログアウト
// ==========================================

async function login() {
    const password = el('login-password').value;
    if (!password) { showLoginMsg('パスワードを入力してください。'); return; }
    setLoading(true);
    try {
        const response = await fetch('/front/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }),
        });
        if (response.status === 401) { showLoginMsg('パスワードが違います。'); return; }
        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
        const data = await response.json();
        sessionStorage.setItem(TOKEN_KEY, data.token);
        enterApp();
    } catch (error) {
        showLoginMsg('ログインに失敗しました。');
        console.error(error);
    } finally {
        setLoading(false);
    }
}
function showLoginMsg(text) { const m = el('login-message'); m.textContent = text; m.className = 'message error'; }
function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    el('app').classList.add('hidden');
    el('login-screen').classList.remove('hidden');
    el('login-password').value = '';
}
function enterApp() {
    el('login-screen').classList.add('hidden');
    el('app').classList.remove('hidden');
    el('login-message').textContent = '';
    updateClock();
    if (!clockTimer) clockTimer = setInterval(updateClock, 30000);
    switchView('reservations-view');
    loadReservations();
}

// ==========================================
// ビュー切り替え
// ==========================================

function switchView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    el(viewId).classList.add('active');
    document.querySelectorAll('.nav-btn[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === viewId));
    if (viewId === 'checkin-view') loadCheckinCandidates();
    if (viewId === 'checkout-view') loadCheckoutCandidates();
}

// ==========================================
// 検索・ソート・テーブル描画（共通）
// ==========================================

function matchAttr(r, attr, q) {
    if (!q) return true;
    if (attr === 'room_numbers') return (r.room_numbers || []).some(n => String(n).includes(q));
    return String(r[attr] ?? '').includes(q);
}

function sortBy(viewKey, key) {
    const ss = sortState[viewKey];
    if (ss.key === key) ss.dir *= -1; else { ss.key = key; ss.dir = 1; }
    if (viewKey === 'res') renderReservations();
    if (viewKey === 'ci') renderCheckin();
    if (viewKey === 'co') renderCheckout();
}

function buildTable(rows, viewKey, { onRowClick, action }) {
    const ss = sortState[viewKey];
    const col = COLUMNS.find(c => c.key === ss.key) || COLUMNS[0];
    const sorted = rows.slice().sort((a, b) => {
        const av = col.sort(a), bv = col.sort(b);
        if (av < bv) return -1 * ss.dir;
        if (av > bv) return 1 * ss.dir;
        return 0;
    });

    let h = '<table class="data-table"><thead><tr>';
    COLUMNS.forEach(c => {
        const arrow = ss.key === c.key ? (ss.dir === 1 ? '<span class="sort-arrow">▲</span>' : '<span class="sort-arrow">▼</span>') : '';
        h += `<th class="sortable" onclick="sortBy('${viewKey}','${c.key}')">${c.label}${arrow}</th>`;
    });
    if (action) h += '<th class="action-col"></th>';
    h += '</tr></thead><tbody>';

    sorted.forEach(r => {
        h += `<tr class="clickable-row" onclick="${onRowClick}(${r.reservation_number})">`;
        COLUMNS.forEach(c => { h += `<td>${c.cell(r)}</td>`; });
        if (action) {
            h += `<td class="action-cell"><button class="btn-sm ${action.cls}" onclick="event.stopPropagation(); ${action.fn}(${r.reservation_number})">${action.label}</button></td>`;
        }
        h += '</tr>';
    });
    h += '</tbody></table>';
    return h;
}

// ==========================================
// 予約一覧
// ==========================================

async function loadReservations() {
    setLoading(true);
    try {
        const data = await apiCall('/front/reservations', 'GET');
        reservationsData = data.reservations || [];
        renderReservations();
    } catch (error) {
        el('reservations-list').innerHTML = `<p class="placeholder error-text">${escapeHtml(error.message)}</p>`;
    } finally {
        setLoading(false);
    }
}

function renderReservations() {
    const attr = el('res-attr').value;
    const q = el('res-query').value.trim();
    const rows = reservationsData.filter(r => matchAttr(r, attr, q));
    el('reservations-list').innerHTML = rows.length
        ? buildTable(rows, 'res', { onRowClick: 'openReservationDetail' })
        : '<p class="placeholder">該当する予約がありません</p>';
}

function openReservationDetail(n) {
    const res = reservationsData.find(r => r.reservation_number === n);
    if (res) openModal(res, '予約詳細', []);
}

// ==========================================
// チェックイン
// ==========================================

async function loadCheckinCandidates() {
    setLoading(true);
    try {
        const data = await apiCall('/front/checkin/candidates', 'GET');
        checkinData = data.reservations || [];
        renderCheckin();
    } catch (error) {
        el('checkin-list').innerHTML = `<p class="placeholder error-text">${escapeHtml(error.message)}</p>`;
    } finally {
        setLoading(false);
    }
}

function renderCheckin() {
    const attr = el('ci-attr').value;
    const q = el('ci-query').value.trim();
    if (checkinData.length === 0) {
        el('checkin-list').innerHTML = '<p class="placeholder">本日チェックイン予定の予約はありません</p>';
        return;
    }
    const rows = checkinData.filter(r => matchAttr(r, attr, q));
    el('checkin-list').innerHTML = rows.length
        ? buildTable(rows, 'ci', { onRowClick: 'openCheckinDetail', action: { label: 'チェックイン', cls: 'btn-success', fn: 'askCheckIn' } })
        : '<p class="placeholder">該当する予約がありません</p>';
}

function openCheckinDetail(n) {
    const res = checkinData.find(r => r.reservation_number === n);
    if (res) openModal(res, 'チェックイン', [{ label: 'チェックインを確定', cls: 'btn-success', onclick: () => askCheckIn(n) }]);
}

function askCheckIn(n) {
    askConfirm(`予約番号 ${n} をチェックインします。よろしいですか？`, () => doCheckIn(n));
}

async function doCheckIn(n) {
    setLoading(true);
    try {
        const result = await apiCall('/front/check-in/confirm', 'POST', { reservation_number: n });
        const message = result.message || '';
        if (message.includes('【エラー】')) toast(message.replace('【エラー】', ''), 'error');
        else toast('チェックインが完了しました。', 'success');
        closeModal();
        loadCheckinCandidates();
    } catch (error) {
        toast('チェックイン処理中にエラーが発生しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

// ==========================================
// チェックアウト
// ==========================================

async function loadCheckoutCandidates() {
    setLoading(true);
    try {
        const data = await apiCall('/front/checkout/candidates', 'GET');
        checkoutData = data.reservations || [];
        renderCheckout();
    } catch (error) {
        el('checkout-list').innerHTML = `<p class="placeholder error-text">${escapeHtml(error.message)}</p>`;
    } finally {
        setLoading(false);
    }
}

function renderCheckout() {
    const attr = el('co-attr').value;
    const q = el('co-query').value.trim();
    if (checkoutData.length === 0) {
        el('checkout-list').innerHTML = '<p class="placeholder">現在宿泊中の予約はありません</p>';
        return;
    }
    const rows = checkoutData.filter(r => matchAttr(r, attr, q));
    el('checkout-list').innerHTML = rows.length
        ? buildTable(rows, 'co', { onRowClick: 'openCheckoutDetail', action: { label: 'チェックアウト', cls: 'btn-success', fn: 'askCheckOut' } })
        : '<p class="placeholder">該当する予約がありません</p>';
}

function openCheckoutDetail(n) {
    const res = checkoutData.find(r => r.reservation_number === n);
    if (res) openModal(res, 'チェックアウト', [{ label: 'チェックアウトを確定', cls: 'btn-success', onclick: () => askCheckOut(n) }]);
}

function askCheckOut(n) {
    const res = checkoutData.find(r => r.reservation_number === n);
    const room = res ? (res.room_numbers || [])[0] : '';
    askConfirm(`部屋番号 ${room}（予約番号 ${n}）をチェックアウトします。よろしいですか？`, () => doCheckOut(n, room));
}

async function doCheckOut(n, room) {
    setLoading(true);
    try {
        const result = await apiCall('/front/check-out/confirm', 'POST', { room_number: room });
        const message = result.message || '';
        if (message.includes('【エラー】')) toast(message.replace('【エラー】', ''), 'error');
        else toast('チェックアウトが完了しました。', 'success');
        closeModal();
        loadCheckoutCandidates();
    } catch (error) {
        toast('チェックアウト処理中にエラーが発生しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

// ==========================================
// 詳細モーダル / 確認ダイアログ
// ==========================================

function openModal(res, title, actions) {
    el('modal-title').textContent = title;
    el('modal-body').innerHTML = `
        <div class="detail-row"><span class="detail-label">予約番号</span><span class="detail-value highlight tnum">${escapeHtml(res.reservation_number)}</span></div>
        <div class="detail-row"><span class="detail-label">予約名</span><span class="detail-value">${escapeHtml(res.guest_name)} 様</span></div>
        <div class="detail-row"><span class="detail-label">宿泊日</span><span class="detail-value tnum">${escapeHtml(res.staying_date)}</span></div>
        <div class="detail-row"><span class="detail-label">利用部屋</span><span class="detail-value tnum">${escapeHtml((res.room_numbers || []).join(', '))}</span></div>
        <div class="detail-row"><span class="detail-label">料金</span><span class="detail-value tnum">${escapeHtml(res.total_amount)}円</span></div>
        <div class="detail-row"><span class="detail-label">状態</span><span class="detail-value">${statusBadge(res.status)}</span></div>
    `;
    const actionsEl = el('modal-actions');
    actionsEl.innerHTML = '';
    actions.forEach(a => {
        const btn = document.createElement('button');
        btn.className = `btn ${a.cls}`;
        btn.textContent = a.label;
        btn.onclick = a.onclick;
        actionsEl.appendChild(btn);
    });
    el('detail-modal').classList.remove('hidden');
}
function closeModal() { el('detail-modal').classList.add('hidden'); }

function askConfirm(text, onYes) {
    el('confirm-text').textContent = text;
    el('confirm-yes').onclick = () => { closeConfirm(); onYes(); };
    el('confirm-modal').classList.remove('hidden');
}
function closeConfirm() { el('confirm-modal').classList.add('hidden'); }

// ==========================================
// 初期化
// ==========================================

document.addEventListener('DOMContentLoaded', function () {
    el('login-password').addEventListener('keypress', e => { if (e.key === 'Enter') login(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeConfirm(); closeModal(); } });
    if (getToken()) enterApp();
});
