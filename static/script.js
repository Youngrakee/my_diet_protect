// Tab handling
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    document.getElementById(tabId).classList.add('active');

    // Find button and add active class
    const buttons = document.querySelectorAll('.tab-btn');
    if (tabId === 'analyze') {
        buttons[0].classList.add('active');
        checkProfile();
    }
    if (tabId === 'history') {
        buttons[1].classList.add('active');
        fetchHistory().then(() => {
            fetchSugarLogs().then(() => initChart());
        });
    }
    if (tabId === 'chat') buttons[2].classList.add('active');
}

// Analysis Mode Toggle
function toggleMode() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    if (mode === 'text') {
        document.getElementById('text-input-group').classList.remove('hidden');
        document.getElementById('image-input-group').classList.add('hidden');
    } else {
        document.getElementById('text-input-group').classList.add('hidden');
        document.getElementById('image-input-group').classList.remove('hidden');
    }
}

// Analysis Form Submit
document.getElementById('analyze-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('analyze-btn');
    const loading = document.getElementById('analysis-loading');
    const resultDiv = document.getElementById('analysis-result');

    btn.disabled = true;
    loading.classList.remove('hidden');
    resultDiv.classList.add('hidden');

    const formData = new FormData(e.target);

    try {
        const res = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            displayResult(data);
        } else {
            alert('분석에 실패했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (err) {
        alert('서버 연결 중 오류가 발생했습니다.');
    } finally {
        btn.disabled = false;
        loading.classList.add('hidden');
    }
};

function displayResult(r) {
    const resultDiv = document.getElementById('analysis-result');
    const impactClass = r.blood_sugar_impact.replace(' ', '_');

    resultDiv.innerHTML = `
        <div class="card">
            <div class="result-header">
                <h3>${r.food_name}</h3>
                <span class="impact-badge impact-${impactClass}">${r.blood_sugar_impact}</span>
            </div>
            
            <div class="nutrients">
                <div class="nutrient-item">
                    <span class="nutrient-label">탄수화물</span>
                    <span class="nutrient-value">${r.carbs_ratio}%</span>
                </div>
                <div class="nutrient-item">
                    <span class="nutrient-label">단백질</span>
                    <span class="nutrient-value">${r.protein_ratio}%</span>
                </div>
                <div class="nutrient-item">
                    <span class="nutrient-label">지방</span>
                    <span class="nutrient-value">${r.fat_ratio}%</span>
                </div>
            </div>
            
            <div style="margin-bottom: 1rem; font-size: 0.9375rem;">
                <p>${r.summary}</p>
            </div>
            
            <div class="card" style="background: rgba(74, 222, 128, 0.1); border-color: rgba(74, 222, 128, 0.2);">
                <h4 style="font-size: 0.875rem; color: var(--primary); margin-bottom: 0.5rem;">✅ 식후 상세 행동 가이드</h4>
                <p style="font-size: 0.875rem;">${r.detailed_action_guide || '가이드 정보가 없습니다.'}</p>
            </div>
            
            <p style="margin-top: 1rem; font-size: 0.875rem;">💡 <strong>한줄평:</strong> ${r.action_guide}</p>
        </div>
    `;
    resultDiv.classList.remove('hidden');
}

// History Fetching
async function fetchHistory() {
    const listDiv = document.getElementById('history-list');

    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        window.historyData = data; // Store for chart

        if (data.length === 0) {
            listDiv.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 2rem;">저장된 식단 기록이 없습니다.</p>';
            return;
        }

        listDiv.innerHTML = data.map((log, index) => `
            <div class="history-item" onclick="toggleHistoryDetail(${index})">
                <div style="display: flex; gap: 1rem;">
                    ${log.image_path ? `
                        <div style="width: 60px; height: 60px; border-radius: 0.5rem; overflow: hidden; flex-shrink: 0;">
                            <img src="/static/uploads/${log.image_path}" style="width: 100%; height: 100%; object-fit: cover;">
                        </div>
                    ` : `
                        <div style="width: 60px; height: 60px; border-radius: 0.5rem; background: var(--bg-dark); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <i data-lucide="utensils" style="width: 20px; color: var(--text-muted);"></i>
                        </div>
                    `}
                    <div style="flex-grow: 1;">
                        <div class="history-date">${log.created_at}</div>
                        <div class="history-title">${log.food_description}</div>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            <span class="impact-badge impact-${log.blood_sugar_impact.replace(' ', '_')}" style="padding: 0.125rem 0.375rem; font-size: 0.625rem;">
                                ${log.blood_sugar_impact}
                            </span>
                            <span style="font-size: 0.75rem; color: var(--text-muted);">
                                ${log.carbs_ratio}/${log.protein_ratio}/${log.fat_ratio}
                            </span>
                        </div>
                    </div>
                    <i data-lucide="chevron-down" class="chevron" id="chevron-${index}"></i>
                </div>
                
                <div id="detail-${index}" class="history-detail hidden" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
                    <p style="font-size: 0.8125rem; color: var(--text-muted); margin-bottom: 0.5rem;">${log.summary}</p>
                    <div style="background: rgba(74, 222, 128, 0.05); padding: 0.75rem; border-radius: 0.5rem; border-left: 3px solid var(--primary);">
                        <h5 style="font-size: 0.75rem; color: var(--primary); margin-bottom: 0.25rem;">💡 상세 가이드</h5>
                        <p style="font-size: 0.75rem;">${log.detailed_action_guide || '가이드 정보가 없습니다.'}</p>
                    </div>
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch (err) {
        listDiv.innerHTML = '<p style="text-align: center; color: var(--error); padding: 2rem;">기록을 불러오지 못했습니다.</p>';
    }
}

async function fetchSugarLogs() {
    try {
        const res = await fetch('/api/health/sugar');
        const data = await res.json();
        window.sugarData = data;
    } catch (err) { }
}

async function logSugar() {
    const levelInput = document.getElementById('sugar-level-input');
    const noteInput = document.getElementById('sugar-note-input');
    const level = parseInt(levelInput.value);
    const note = noteInput.value.trim();

    if (!level) return alert('수치를 입력해주세요.');

    try {
        const res = await fetch('/api/health/sugar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sugar_level: level, note: note })
        });

        if (res.ok) {
            levelInput.value = '';
            noteInput.value = '';
            alert('기록되었습니다.');
            fetchSugarLogs().then(() => initChart());
        }
    } catch (err) {
        alert('저장에 실패했습니다.');
    }
}

function toggleHistoryDetail(index) {
    const detail = document.getElementById(`detail-${index}`);
    const chevron = document.getElementById(`chevron-${index}`);
    const isHidden = detail.classList.contains('hidden');

    detail.classList.toggle('hidden');
    if (chevron) {
        chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
        chevron.style.transition = 'transform 0.2s';
    }
}

let impactChart = null;
function initChart() {
    const ctx = document.getElementById('impactChart');
    if (!ctx) return;

    const chartType = document.querySelector('input[name="chart-type"]:checked').value;

    if (impactChart) impactChart.destroy();

    let labels, dataPoints, labelName, borderColor, bgColor, yMax, yTicks;

    if (chartType === 'impact') {
        if (!window.historyData || window.historyData.length === 0) return;
        const data = [...window.historyData].reverse();
        const impactValues = { '낮음': 1, '보통': 2, '높음': 3, '매우 높음': 4 };

        labels = data.map(l => l.created_at.split(' ')[0]);
        dataPoints = data.map(l => impactValues[l.blood_sugar_impact] || 0);
        labelName = '식단 임팩트';
        borderColor = '#4ade80';
        bgColor = 'rgba(74, 222, 128, 0.1)';
        yMax = 5;
        yTicks = {
            stepSize: 1,
            callback: value => ['', '낮음', '보통', '높음', '매우 높음', ''][value],
            color: '#94a3b8'
        };
    } else {
        if (!window.sugarData || window.sugarData.length === 0) {
            // Draw empty chart with custom message or just return
            labels = ['기록 없음'];
            dataPoints = [0];
            labelName = '혈당 수치 (기록 없음)';
        } else {
            const data = [...window.sugarData].reverse();
            labels = data.map(l => l.created_at.split(' ')[0]);
            dataPoints = data.map(l => l.sugar_level);
            labelName = '혈당 수치 (mg/dL)';
        }
        borderColor = '#ef4444';
        bgColor = 'rgba(239, 68, 68, 0.1)';
        yMax = undefined;
        yTicks = { color: '#94a3b8' };
    }

    impactChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: labelName,
                data: dataPoints,
                borderColor: borderColor,
                backgroundColor: bgColor,
                tension: 0.4,
                fill: true,
                pointRadius: 4,
                pointBackgroundColor: borderColor
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    min: 0,
                    max: yMax,
                    ticks: yTicks,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { display: false }
                }
            }
        }
    });
}

// Chat Functionality
let chatHistory = [];

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;

    appendMessage('user', msg);
    input.value = '';

    chatHistory.push({ role: 'user', content: msg });

    // Add pending message
    const pendingId = 'pending-' + Date.now();
    appendMessage('assistant', '<div class="spinner" style="width: 14px; height: 14px; margin: 0;"></div>', pendingId);

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: chatHistory })
        });

        const data = await res.json();
        document.getElementById(pendingId).innerHTML = data.reply;
        chatHistory.push({ role: 'assistant', content: data.reply });
    } catch (err) {
        document.getElementById(pendingId).innerHTML = '<span style="color: var(--error);">죄송합니다. 오류가 발생했습니다.</span>';
    }
}

function appendMessage(role, content, id = null) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    if (id) div.id = id;
    div.innerHTML = content;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

document.getElementById('chat-input').onkeypress = (e) => {
    if (e.key === 'Enter') sendMessage();
};

async function checkProfile() {
    try {
        const res = await fetch('/profile_data');
        const data = await res.json();
        const reminder = document.getElementById('profile-reminder');
        if (!data.gender || !data.age) {
            reminder.classList.remove('hidden');
        } else {
            reminder.classList.add('hidden');
        }
    } catch (err) { }
}

// Initial check
checkProfile();
