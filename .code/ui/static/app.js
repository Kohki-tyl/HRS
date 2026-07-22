// ==========================================
// ユーティリティ関数
// ==========================================

/**
 * メッセージを表示する
 */
function showMessage(elementId, text, type = 'info') {
    const element = document.getElementById(elementId);
    element.textContent = text;
    element.className = `message ${type}`;
}

/**
 * メッセージをクリアする
 */
function clearMessage(elementId) {
    const element = document.getElementById(elementId);
    element.textContent = '';
    element.className = 'message empty';
}

/**
 * ローディング表示を制御する
 */
function setLoading(isLoading) {
    const loadingElement = document.getElementById('loading');
    if (isLoading) {
        loadingElement.classList.remove('hidden');
    } else {
        loadingElement.classList.add('hidden');
    }
}

/**
 * フェーズを切り替える
 */
function switchPhase(phaseElementId) {
    // 同じタブ内の他のフェーズを非表示に
    const parentCard = document.getElementById(phaseElementId).parentElement;
    const allPhases = parentCard.querySelectorAll('.phase');
    allPhases.forEach(phase => phase.classList.remove('active'));
    
    // 指定フェーズをアクティブに
    document.getElementById(phaseElementId).classList.add('active');
}

/**
 * API呼び出しのヘルパー関数
 */
async function apiCall(endpoint, method = 'POST', params = {}) {
    try {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// ==========================================
// チェックイン関連の関数
// ==========================================

/**
 * チェックイン: 予約を検索
 */
async function checkInSearchReservation() {
    const reservationNumber = document.getElementById('checkin-number').value.trim();

    if (!reservationNumber) {
        showMessage('checkin-search-message', '予約番号を入力してください。', 'error');
        return;
    }

    setLoading(true);
    clearMessage('checkin-search-message');
    clearMessage('checkin-confirm-message');

    try {
        const result = await apiCall('/front/check-in/search', 'POST', {
            reservation_number: reservationNumber
        });

        const message = result.message || '';

        // エラーメッセージの場合（【エラー】で始まる）
        if (message.includes('【エラー】')) {
            showMessage('checkin-search-message', message.replace('【エラー】', ''), 'error');
            return;
        }

        // 成功: 詳細情報を表示してフェーズ切り替え
        displayCheckInDetail(result.message, reservationNumber);
        switchPhase('checkin-confirm');
        showMessage('checkin-search-message', '', 'success');

    } catch (error) {
        showMessage('checkin-search-message', 'システムエラーが発生しました。しばらく後で再度お試しください。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

/**
 * チェックイン詳細情報を表示
 */
function displayCheckInDetail(message, reservationNumber) {
    // メッセージを解析して詳細情報を抽出
    const lines = message.split('\n');
    const detail = {};

    lines.forEach(line => {
        if (line.includes('ご予約者様:')) {
            detail.guestName = line.replace('ご予約者様:', '').trim();
        } else if (line.includes('ご宿泊日程:')) {
            detail.stayingDate = line.replace('ご宿泊日程:', '').trim();
        } else if (line.includes('予定お部屋:')) {
            detail.rooms = line.replace('予定お部屋:', '').trim();
        }
    });

    const detailCard = document.getElementById('checkin-detail');
    detailCard.innerHTML = `
        <div class="detail-row">
            <div class="detail-label">予約番号</div>
            <div class="detail-value highlight">${reservationNumber}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">ご予約者様</div>
            <div class="detail-value">${detail.guestName || '情報取得中...'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">ご宿泊日程</div>
            <div class="detail-value">${detail.stayingDate || '情報取得中...'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">予定お部屋</div>
            <div class="detail-value">${detail.rooms || '情報取得中...'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">ステータス</div>
            <div class="detail-value">予約済み</div>
        </div>
    `;

    // 予約番号を保存（確定時に使用）
    document.getElementById('checkin-number').dataset.confirmed = reservationNumber;
}

/**
 * チェックイン: 確定
 */
async function checkInConfirm() {
    const reservationNumber = document.getElementById('checkin-number').dataset.confirmed;

    if (!reservationNumber) {
        showMessage('checkin-confirm-message', 'エラー: 予約番号が見つかりません。最初からやり直してください。', 'error');
        return;
    }

    setLoading(true);
    clearMessage('checkin-confirm-message');

    try {
        const result = await apiCall('/front/check-in/confirm', 'POST', {
            reservation_number: reservationNumber
        });

        const message = result.message || '';

        // エラーメッセージの場合
        if (message.includes('【エラー】')) {
            showMessage('checkin-confirm-message', message.replace('【エラー】', ''), 'error');
            return;
        }

        // 成功: 部屋番号を抽出して表示
        showMessage('checkin-confirm-message', message, 'success');
        
        // 2秒後に最初に戻る
        setTimeout(() => {
            checkInReset();
        }, 3000);

    } catch (error) {
        showMessage('checkin-confirm-message', 'チェックイン処理中にエラーが発生しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

/**
 * チェックイン: リセット
 */
function checkInReset() {
    document.getElementById('checkin-number').value = '';
    document.getElementById('checkin-number').dataset.confirmed = '';
    clearMessage('checkin-search-message');
    clearMessage('checkin-confirm-message');
    switchPhase('checkin-search');
}

// ==========================================
// チェックアウト関連の関数
// ==========================================

/**
 * チェックアウト: 請求情報を検索
 */
async function checkOutSearchInformation() {
    const roomNumber = document.getElementById('checkout-number').value.trim();

    if (!roomNumber) {
        showMessage('checkout-search-message', '部屋番号を入力してください。', 'error');
        return;
    }

    setLoading(true);
    clearMessage('checkout-search-message');
    clearMessage('checkout-confirm-message');
    document.getElementById('payment-confirmed').checked = false;

    try {
        const result = await apiCall('/front/check-out/search', 'POST', {
            room_number: roomNumber
        });

        const message = result.message || '';

        // エラーメッセージの場合
        if (message.includes('【エラー】')) {
            showMessage('checkout-search-message', message.replace('【エラー】', ''), 'error');
            return;
        }

        // 成功: 請求情報を表示してフェーズ切り替え
        displayCheckOutDetail(result.message, roomNumber);
        switchPhase('checkout-confirm');
        showMessage('checkout-search-message', '', 'success');

    } catch (error) {
        showMessage('checkout-search-message', 'システムエラーが発生しました。しばらく後で再度お試しください。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

/**
 * チェックアウト詳細情報を表示
 */
function displayCheckOutDetail(message, roomNumber) {
    // メッセージを解析して詳細情報を抽出
    const lines = message.split('\n');
    const detail = {};

    lines.forEach(line => {
        if (line.includes('ご宿泊者様:')) {
            detail.guestName = line.replace('ご宿泊者様:', '').trim();
        } else if (line.includes('ご利用お部屋:')) {
            detail.rooms = line.replace('ご利用お部屋:', '').trim();
        } else if (line.includes('ご請求額:')) {
            detail.amount = line.replace('ご請求額:', '').trim();
        }
    });

    const detailCard = document.getElementById('checkout-detail');
    detailCard.innerHTML = `
        <div class="detail-row">
            <div class="detail-label">部屋番号</div>
            <div class="detail-value highlight">${roomNumber}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">ご宿泊者様</div>
            <div class="detail-value">${detail.guestName || '情報取得中...'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">ご利用お部屋</div>
            <div class="detail-value">${detail.rooms || '情報取得中...'}</div>
        </div>
        <div class="detail-row amount-row">
            <div class="detail-label">ご請求額</div>
            <div class="detail-value">${detail.amount || '情報取得中...'}</div>
        </div>
    `;

    // 部屋番号を保存（確定時に使用）
    document.getElementById('checkout-number').dataset.confirmed = roomNumber;
}

/**
 * チェックアウト: 確定
 */
async function checkOutConfirm() {
    const roomNumber = document.getElementById('checkout-number').dataset.confirmed;

    if (!roomNumber) {
        showMessage('checkout-confirm-message', 'エラー: 部屋番号が見つかりません。最初からやり直してください。', 'error');
        return;
    }

    setLoading(true);
    clearMessage('checkout-confirm-message');

    try {
        const result = await apiCall('/front/check-out/confirm', 'POST', {
            room_number: roomNumber
        });

        const message = result.message || '';

        // エラーメッセージの場合
        if (message.includes('【エラー】')) {
            showMessage('checkout-confirm-message', message.replace('【エラー】', ''), 'error');
            return;
        }

        // 成功: メッセージを表示
        showMessage('checkout-confirm-message', message, 'success');

        // 2秒後に最初に戻る
        setTimeout(() => {
            checkOutReset();
        }, 3000);

    } catch (error) {
        showMessage('checkout-confirm-message', 'チェックアウト処理中にエラーが発生しました。', 'error');
        console.error(error);
    } finally {
        setLoading(false);
    }
}

/**
 * チェックアウト: リセット
 */
function checkOutReset() {
    document.getElementById('checkout-number').value = '';
    document.getElementById('checkout-number').dataset.confirmed = '';
    document.getElementById('payment-confirmed').checked = false;
    clearMessage('checkout-search-message');
    clearMessage('checkout-confirm-message');
    switchPhase('checkout-search');
    updateCheckOutConfirmButton();
}

/**
 * チェックアウト確定ボタンの有効化/無効化を更新
 */
function updateCheckOutConfirmButton() {
    const checkbox = document.getElementById('payment-confirmed');
    const button = document.getElementById('checkout-confirm-btn');
    button.disabled = !checkbox.checked;
}

// ==========================================
// イベントリスナー
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    // タブ切り替え
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            
            // ボタンのアクティブ状態を更新
            tabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // タブコンテンツを切り替え
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            
            // リセット処理
            checkInReset();
            checkOutReset();
        });
    });

    // チェックアウト: 支払い確認チェックボックス
    document.getElementById('payment-confirmed').addEventListener('change', function() {
        updateCheckOutConfirmButton();
    });

    // Enterキーでの送信
    document.getElementById('checkin-number').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            if (this.dataset.confirmed) {
                checkInConfirm();
            } else {
                checkInSearchReservation();
            }
        }
    });

    document.getElementById('checkout-number').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            if (this.dataset.confirmed) {
                if (document.getElementById('payment-confirmed').checked) {
                    checkOutConfirm();
                }
            } else {
                checkOutSearchInformation();
            }
        }
    });

    // 数字のみを入力できるようにフィルタ
    document.getElementById('checkin-number').addEventListener('input', function(e) {
        this.value = this.value.replace(/[^0-9]/g, '');
    });

    document.getElementById('checkout-number').addEventListener('input', function(e) {
        this.value = this.value.replace(/[^0-9]/g, '');
    });

    // 初期状態を設定
    updateCheckOutConfirmButton();
});

// ==========================================
// 予約一覧関連の関数
// ==========================================

/**
 * 予約一覧を取得して表示
 */
async function loadReservations() {
    setLoading(true);
    
    try {
        const response = await fetch('/front/reservations', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }

        const data = await response.json();
        const reservations = data.reservations || [];

        if (reservations.length === 0) {
            document.getElementById('reservations-list').innerHTML = 
                '<p class="placeholder">No reservations found</p>';
        } else {
            displayReservationsTable(reservations);
        }

    } catch (error) {
        console.error('Error loading reservations:', error);
        document.getElementById('reservations-list').innerHTML = 
            '<p class="placeholder" style="color: var(--danger-color);">Error loading reservations. Please try again.</p>';
    } finally {
        setLoading(false);
    }
}

/**
 * 予約一覧をテーブルで表示
 */
function displayReservationsTable(reservations) {
    let tableHTML = `
        <table class="reservations-table">
            <thead>
                <tr>
                    <th>Res. No.</th>
                    <th>Guest Name</th>
                    <th>Check-in Date</th>
                    <th>Room</th>
                    <th>Amount</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    `;

    reservations.forEach(res => {
        const statusBadge = getStatusBadge(res.status || 'CREATED');
        tableHTML += `
            <tr>
                <td>${res.reservation_number || res.number}</td>
                <td>${res.guest_name || res.guest?.name || 'N/A'}</td>
                <td>${res.check_in_date || res.check_in_date_planned || 'N/A'}</td>
                <td>${res.room_number || res.room?.number || 'N/A'}</td>
                <td>${res.total_amount || res.payment?.total_amount || '0'}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    });

    tableHTML += `
            </tbody>
        </table>
    `;

    document.getElementById('reservations-list').innerHTML = tableHTML;
}

/**
 * ステータスに応じたバッジHTMLを生成
 */
function getStatusBadge(status) {
    const statusMap = {
        'CREATED': { text: 'Created', class: 'created' },
        'CHECKED_IN': { text: 'Checked In', class: 'checked-in' },
        'COMPLETED': { text: 'Completed', class: 'completed' },
        'CANCELLED': { text: 'Cancelled', class: 'cancelled' }
    };

    const badgeInfo = statusMap[status] || { text: status, class: 'created' };
    return `<span class="status-badge ${badgeInfo.class}">${badgeInfo.text}</span>`;
}
