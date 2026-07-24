// ==========================================
// HRS フロントデスク（管理者）画面
// ==========================================

// クライアント側で保持する予約データ（フィルタ用）
let reservationsData = [];
let checkinData = [];
let checkoutData = [];

const TOKEN_KEY = 'hrs_admin_token';

// ステータスの日本語表示
const STATUS_LABELS = {
    'Created': '予約済み',
    'CheckedIn': 'チェックイン済み',
    'Completed': 'チェックアウト済み',
    'Cancelled': 'キャンセル済み',
};
const STATUS_CLASS = {
    'Created': 'created',
    'CheckedIn': 'checked-in',
    'Completed': 'completed',
    'Cancelled': 'cancelled',
};

// ==========================================
// 共通ユーティリティ
// ==========================================

function setLoading(isLoading) {
    document.getElementById('loading').classList.toggle('hidden', !isLoading);
}

function showMessage(elementId, text, type = 'info') {
    const el = document.getElementById(elementId);
    el.textContent = text;
    el.className = `message ${type}`;
}

function clearMessage(elementId) {
    const el = document.getElementById(elementId);
    el.textContent = '';
    el.className = 'message empty';
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

function statusBadge(status) {
    const label = STATUS_LABELS[status] || status;
    const cls = STATUS_CLASS[status] || 'created';
    return `<span class="status-badge ${cls}">${escapeHtml(label)}</span>`;
}

function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || '';
}

/**
 * 認証付き API 呼び出し。401 の場合はログイン画面へ戻す。
 */
async function apiCall(endpoint, method = 'GET', params = null, body = null) {
    let url = endpoint;
    if (params) {
        const qs = new URLSearchParams(params).toString();
        url = qs ? `${endpoint}?${qs}` : endpoint;
    }
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-Admin-Token': getToken(),
        },
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (response.status === 401) {
        logout();
        throw new Error('認証が切れました。再度ログインしてください。');
    }
    if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
    }
    return await response.json();
}

// ==========================================
// ログイン / ログアウト
// ==========================================

async function login() {
    const password = document.getElementById('login-password').value;
    if (!password) {
        showMessage('login-message', 'パスワードを入力してください。', 'error');
        return;
    }
    setLoading(true);
    clearMessage('login-message');
    try {
        const response = await fetch('/front/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });
        if (response.status === 401) {
            showMessage('login-message', 'パスワードが違います。', 'error');
            return;
        }
        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
        const data = await response.json();
        sessionStorage.setItem(TOKEN_KEY, data.token);
        enterApp();
    } catch (error) {
        showMessage('login-message', 'ログインに失敗しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    document.getElementById('app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('login-password').value = '';
}

function enterApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    clearMessage('login-message');
    switchView('reservations-view');
    loadReservations();
}

// ==========================================
// ビュー切り替え（サイドバー）
// ==========================================

function switchView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
    document.querySelectorAll('.nav-btn[data-view]').forEach(b => {
        b.classList.toggle('active', b.dataset.view === viewId);
    });
    if (viewId === 'checkin-view') loadCheckinCandidates();
    if (viewId === 'checkout-view') loadCheckoutCandidates();
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
        document.getElementById('reservations-list').innerHTML =
            `<p class="placeholder error-text">${escapeHtml(error.message)}</p>`;
    } finally {
        setLoading(false);
    }
}

function renderReservations() {
    const num = document.getElementById('res-filter-number').value.trim();
    const name = document.getElementById('res-filter-name').value.trim();
    const dateVal = document.getElementById('res-filter-date').value;

    const rows = reservationsData.filter(r =>
        (!num || String(r.reservation_number).includes(num)) &&
        (!name || (r.guest_name || '').includes(name)) &&
        (!dateVal || r.staying_date === dateVal)
    );

    renderTable('reservations-list', rows, { onRowClick: 'openReservationDetail' });
}

function openReservationDetail(reservationNumber) {
    const res = reservationsData.find(r => r.reservation_number === reservationNumber);
    if (res) openModal(res, '予約詳細', []);
}

// ==========================================
// チェックイン（本日の予約）
// ==========================================

async function loadCheckinCandidates() {
    setLoading(true);
    try {
        const data = await apiCall('/front/checkin/candidates', 'GET');
        checkinData = data.reservations || [];
        renderCheckin();
    } catch (error) {
        document.getElementById('checkin-list').innerHTML =
            `<p class="placeholder error-text">${escapeHtml(error.message)}</p>`;
    } finally {
        setLoading(false);
    }
}

function renderCheckin() {
    const num = document.getElementById('ci-filter-number').value.trim();
    const name = document.getElementById('ci-filter-name').value.trim();
    const rows = checkinData.filter(r =>
        (!num || String(r.reservation_number).includes(num)) &&
        (!name || (r.guest_name || '').includes(name))
    );
    if (rows.length === 0 && checkinData.length === 0) {
        document.getElementById('checkin-list').innerHTML =
            '<p class="placeholder">本日チェックイン予定の予約はありません</p>';
        return;
    }
    renderTable('checkin-list', rows, { onRowClick: 'openCheckinDetail' });
}

function openCheckinDetail(reservationNumber) {
    const res = checkinData.find(r => r.reservation_number === reservationNumber);
    if (!res) return;
    openModal(res, 'チェックイン', [
        { label: 'チェックインを確定', cls: 'btn-success', onclick: () => confirmCheckIn(res.reservation_number) },
    ]);
}

async function confirmCheckIn(reservationNumber) {
    setLoading(true);
    clearMessage('modal-message');
    try {
        const result = await apiCall('/front/check-in/confirm', 'POST', { reservation_number: reservationNumber });
        const message = result.message || '';
        if (message.includes('【エラー】')) {
            showMessage('modal-message', message.replace('【エラー】', ''), 'error');
            return;
        }
        showMessage('modal-message', message, 'success');
        document.getElementById('modal-actions').innerHTML = '';
        setTimeout(() => { closeModal(); loadCheckinCandidates(); }, 1800);
    } catch (error) {
        showMessage('modal-message', 'チェックイン処理中にエラーが発生しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

// ==========================================
// チェックアウト（宿泊中）
// ==========================================

async function loadCheckoutCandidates() {
    setLoading(true);
    try {
        const data = await apiCall('/front/checkout/candidates', 'GET');
        checkoutData = data.reservations || [];
        renderCheckout();
    } catch (error) {
        document.getElementById('checkout-list').innerHTML =
            `<p class="placeholder error-text">${escapeHtml(error.message)}</p>`;
    } finally {
        setLoading(false);
    }
}

function renderCheckout() {
    const room = document.getElementById('co-filter-room').value.trim();
    const rows = checkoutData.filter(r =>
        !room || (r.room_numbers || []).some(n => String(n).includes(room))
    );
    if (rows.length === 0 && checkoutData.length === 0) {
        document.getElementById('checkout-list').innerHTML =
            '<p class="placeholder">現在宿泊中の予約はありません</p>';
        return;
    }
    renderTable('checkout-list', rows, { onRowClick: 'openCheckoutDetail' });
}

function openCheckoutDetail(reservationNumber) {
    const res = checkoutData.find(r => r.reservation_number === reservationNumber);
    if (!res) return;
    openModal(res, 'チェックアウト', [
        { label: 'チェックアウトを確定', cls: 'btn-success', onclick: () => confirmCheckOut(res.room_numbers[0]) },
    ]);
}

async function confirmCheckOut(roomNumber) {
    setLoading(true);
    clearMessage('modal-message');
    try {
        const result = await apiCall('/front/check-out/confirm', 'POST', { room_number: roomNumber });
        const message = result.message || '';
        if (message.includes('【エラー】')) {
            showMessage('modal-message', message.replace('【エラー】', ''), 'error');
            return;
        }
        showMessage('modal-message', message, 'success');
        document.getElementById('modal-actions').innerHTML = '';
        setTimeout(() => { closeModal(); loadCheckoutCandidates(); }, 1800);
    } catch (error) {
        showMessage('modal-message', 'チェックアウト処理中にエラーが発生しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

// ==========================================
// テーブル描画（共通）
// ==========================================

function renderTable(containerId, rows, { onRowClick }) {
    if (rows.length === 0) {
        document.getElementById(containerId).innerHTML =
            '<p class="placeholder">該当する予約がありません</p>';
        return;
    }
    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>予約番号</th>
                    <th>予約名</th>
                    <th>宿泊日</th>
                    <th>部屋</th>
                    <th>料金</th>
                    <th>状態</th>
                </tr>
            </thead>
            <tbody>
    `;
    rows.forEach(r => {
        html += `
            <tr class="clickable-row" onclick="${onRowClick}(${r.reservation_number})">
                <td>${escapeHtml(r.reservation_number)}</td>
                <td>${escapeHtml(r.guest_name)}</td>
                <td>${escapeHtml(r.staying_date)}</td>
                <td>${escapeHtml((r.room_numbers || []).join(', '))}</td>
                <td>${escapeHtml(r.total_amount)}円</td>
                <td>${statusBadge(r.status)}</td>
            </tr>
        `;
    });
    html += '</tbody></table>';
    document.getElementById(containerId).innerHTML = html;
}

// ==========================================
// 詳細モーダル
// ==========================================

function openModal(res, title, actions) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = `
        <div class="detail-row"><span class="detail-label">予約番号</span><span class="detail-value highlight">${escapeHtml(res.reservation_number)}</span></div>
        <div class="detail-row"><span class="detail-label">予約名</span><span class="detail-value">${escapeHtml(res.guest_name)} 様</span></div>
        <div class="detail-row"><span class="detail-label">宿泊日</span><span class="detail-value">${escapeHtml(res.staying_date)}</span></div>
        <div class="detail-row"><span class="detail-label">利用部屋</span><span class="detail-value">${escapeHtml((res.room_numbers || []).join(', '))}</span></div>
        <div class="detail-row"><span class="detail-label">料金</span><span class="detail-value">${escapeHtml(res.total_amount)}円</span></div>
        <div class="detail-row"><span class="detail-label">状態</span><span class="detail-value">${statusBadge(res.status)}</span></div>
    `;
    const actionsEl = document.getElementById('modal-actions');
    actionsEl.innerHTML = '';
    actions.forEach(a => {
        const btn = document.createElement('button');
        btn.className = `btn ${a.cls}`;
        btn.textContent = a.label;
        btn.onclick = a.onclick;
        actionsEl.appendChild(btn);
    });
    clearMessage('modal-message');
    document.getElementById('detail-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('detail-modal').classList.add('hidden');
}

// ==========================================
// 初期化
// ==========================================

document.addEventListener('DOMContentLoaded', function () {
    // Enter でログイン
    document.getElementById('login-password').addEventListener('keypress', e => {
        if (e.key === 'Enter') login();
    });
    // Escape でモーダルを閉じる
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeModal();
    });

    // トークンが残っていれば自動で本体を表示（切れていれば最初のAPIで弾かれログインへ）
    if (getToken()) {
        enterApp();
    }
});
