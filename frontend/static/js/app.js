/* ==========================================================
   Call Quality Auditor — admin dashboard
   Panels: Team Overview, Employees, Audit Report, Coaching Plan
   ========================================================== */

// ---------- Small helpers ----------

const $ = (id) => document.getElementById(id);

// Escape untrusted text (transcripts, AI output, names) before putting it in HTML.
function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatScore(value) {
    return value === null || value === undefined ? '–' : Number(value).toFixed(1);
}

function formatPercent(value) {
    return value === null || value === undefined ? '–' : `${Math.round(value)}%`;
}

function formatDate(isoString) {
    return isoString ? new Date(isoString).toLocaleString() : '';
}

function outcomeBadge(audit) {
    if (audit.status === 'processing') return '<span class="badge-warn">Processing…</span>';
    if (audit.status === 'failed') return '<span class="badge-fail">Error</span>';
    const css = { PASS: 'badge-pass', WARN: 'badge-warn', FAIL: 'badge-fail' }[audit.outcome] || 'badge-warn';
    return `<span class="${css}">${escapeHtml(audit.outcome)}</span>`;
}

const VERDICT_BADGES = {
    pass: '<span class="badge-pass">Pass</span>',
    fail: '<span class="badge-fail">Fail</span>',
    not_applicable: '<span class="badge-na">N/A</span>',
};

// Fetch JSON from our API; throws an Error with the server's message on failure.
async function api(path, options = {}) {
    const response = await fetch(path, options);
    if (response.status === 401) {
        window.location.href = '/login';
        throw new Error('Session expired');
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
}

function refreshIcons() {
    lucide.createIcons();
}

// ---------- Panel navigation ----------

let previousPanel = 'overview-panel';

function showPanel(panelId) {
    const current = document.querySelector('.content-panel.active');
    if (current && current.id !== 'audit-panel') previousPanel = current.id;

    document.querySelectorAll('.content-panel').forEach((panel) => panel.classList.toggle('active', panel.id === panelId));
    document.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.panel === panelId));

    const panel = $(panelId);
    $('panelTitle').textContent = panel.dataset.title;
    $('panelSubtitle').textContent = panel.dataset.subtitle;

    // Start every panel at the top of the page.
    window.scrollTo(0, 0);
    document.querySelector('.main-content').scrollTop = 0;
}

function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach((item) => {
        item.addEventListener('click', () => {
            showPanel(item.dataset.panel);
            if (item.dataset.panel === 'employee-panel') loadEmployee($('employeeSelect').value);
        });
    });
    $('backButton').addEventListener('click', () => showPanel(previousPanel));
}

// ---------- Theme ----------

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    $('themeIcon').setAttribute('data-lucide', theme === 'light' ? 'moon' : 'sun');
    refreshIcons();
    if (scoreChart) scoreChart.updateOptions({ theme: { mode: theme } });
}

function setupTheme() {
    $('themeToggle').addEventListener('click', () => {
        const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', next);
        applyTheme(next);
    });
}

// ---------- Team overview ----------

let scoreChart = null;

async function loadOverview() {
    const data = await api('/api/overview');

    const team = data.team;
    $('teamAvgScore').textContent = formatScore(team.avg_overall);
    $('teamPassRate').textContent = formatPercent(team.pass_rate);
    $('teamFailCount').textContent = team.fail_count || 0;
    $('teamAuditCount').textContent = team.audit_count;
    $('teamAgentCount').textContent = `${team.agent_count} employee${team.agent_count === 1 ? '' : 's'}`;

    renderLeaderboard(data.agents);
    renderViolations($('teamViolations'), data.top_violations);
    renderScoreChart(data.agents);
    renderAuditRows($('recentAuditsBody'), data.recent_audits, true);
    updateEmployeeList(data.agents.map((agent) => agent.agent_name));
}

function renderLeaderboard(agents) {
    const body = $('leaderboardBody');
    if (!agents.length) {
        body.innerHTML = '<tr><td colspan="7" class="no-data-msg">No completed audits yet.</td></tr>';
        return;
    }
    body.innerHTML = agents.map((agent) => `
        <tr class="clickable-row" data-agent="${escapeHtml(agent.agent_name)}">
            <td style="font-weight: 700;">${escapeHtml(agent.agent_name)}</td>
            <td>${agent.audit_count}</td>
            <td><strong>${formatScore(agent.avg_overall)}</strong></td>
            <td>${formatScore(agent.avg_empathy)}</td>
            <td>${formatScore(agent.avg_professionalism)}</td>
            <td>${formatPercent(agent.pass_rate)}</td>
            <td>${agent.fail_count ? `<span class="badge-fail">${agent.fail_count}</span>` : '0'}</td>
        </tr>`).join('');

    body.querySelectorAll('tr').forEach((row) => row.addEventListener('click', () => {
        $('employeeSelect').value = row.dataset.agent;
        showPanel('employee-panel');
        loadEmployee(row.dataset.agent);
    }));
}

function renderViolations(container, violations) {
    if (!violations.length) {
        container.innerHTML = '<div class="badge-pass" style="padding: 16px; width: 100%; justify-content: center;">No rules broken</div>';
        return;
    }
    container.innerHTML = violations.map((violation) => `
        <div class="violation-alert-card">
            <div class="violation-alert-title">
                Rule ${escapeHtml(violation.rule_id)} · ${escapeHtml(violation.rule_title)}
                ${violation.zero_tolerance ? '<span class="badge-fail" style="margin-left: 6px;">Critical</span>' : ''}
            </div>
            <div class="violation-alert-meta">Broken in ${violation.count} call${violation.count === 1 ? '' : 's'}</div>
        </div>`).join('');
}

function renderScoreChart(agents) {
    const container = $('scoreChart');
    if (scoreChart) { scoreChart.destroy(); scoreChart = null; }
    if (!agents.length) {
        container.innerHTML = '<div class="no-data-msg">No data yet.</div>';
        return;
    }
    container.innerHTML = '';
    scoreChart = new ApexCharts(container, {
        chart: { type: 'bar', height: 300, background: 'transparent', toolbar: { show: false } },
        theme: { mode: document.documentElement.getAttribute('data-theme') || 'dark' },
        series: [
            { name: 'Overall', data: agents.map((a) => Number(formatScore(a.avg_overall))) },
            { name: 'Empathy', data: agents.map((a) => Number(formatScore(a.avg_empathy))) },
            { name: 'Professionalism', data: agents.map((a) => Number(formatScore(a.avg_professionalism))) },
        ],
        xaxis: { categories: agents.map((a) => a.agent_name) },
        yaxis: { min: 0, max: 100 },
        colors: ['#58a6ff', '#3fb950', '#d29922'],
        plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
        dataLabels: { enabled: false },
        legend: { position: 'top' },
    });
    scoreChart.render();
}

// Shared by "Recent audits" and an employee's audit list.
function renderAuditRows(body, audits, showAgent) {
    const columns = showAgent ? 6 : 5;
    if (!audits.length) {
        body.innerHTML = `<tr><td colspan="${columns}" class="no-data-msg">No audits yet.</td></tr>`;
        return;
    }
    body.innerHTML = audits.map((audit) => `
        <tr class="clickable-row" data-audit-id="${audit.id}">
            <td>${audit.id}</td>
            ${showAgent ? `<td style="font-weight: 700;">${escapeHtml(audit.agent_name)}</td>` : ''}
            <td>${escapeHtml(audit.filename)}</td>
            <td><strong>${formatScore(audit.overall_score)}</strong></td>
            <td>${outcomeBadge(audit)}</td>
            <td>${formatDate(audit.created_at)}</td>
        </tr>`).join('');

    body.querySelectorAll('tr').forEach((row) => row.addEventListener('click', () => openAudit(row.dataset.auditId)));
}

// ---------- Employees ----------

function updateEmployeeList(names) {
    const select = $('employeeSelect');
    const selected = select.value;
    select.innerHTML = names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
    if (names.includes(selected)) select.value = selected;

    $('knownAgents').innerHTML = names.map((name) => `<option value="${escapeHtml(name)}">`).join('');
}

async function loadEmployee(agentName) {
    if (!agentName) {
        $('employeeDetails').hidden = true;
        $('employeeEmpty').hidden = false;
        return;
    }
    const data = await api(`/api/agents/${encodeURIComponent(agentName)}`);
    const summary = data.summary;

    $('employeeDetails').hidden = false;
    $('employeeEmpty').hidden = true;
    $('empAvgScore').textContent = formatScore(summary && summary.avg_overall);
    $('empSoftSkills').textContent = summary
        ? `${formatScore(summary.avg_empathy)} / ${formatScore(summary.avg_professionalism)}` : '–';
    $('empPassRate').textContent = formatPercent(summary && summary.pass_rate);
    $('empAuditCount').textContent = summary ? summary.audit_count : 0;

    renderAuditRows($('employeeAuditsBody'), data.audits, false);
    renderViolations($('employeeViolations'), data.top_violations);
}

// ---------- Audit report ----------

async function openAudit(auditId) {
    showPanel('audit-panel');
    const report = $('auditReport');
    report.innerHTML = '<div class="no-data-msg">Loading report…</div>';

    const audit = await api(`/api/audits/${auditId}`);
    if (audit.status !== 'completed') {
        report.innerHTML = `<div class="card"><div class="card-body">
            <h3 class="card-title">${escapeHtml(audit.agent_name)} · ${escapeHtml(audit.filename)}</h3>
            <p style="margin-top: 12px;">${outcomeBadge(audit)} ${escapeHtml(audit.error || audit.progress_message)}</p>
        </div></div>`;
        return;
    }

    report.innerHTML = `
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-body">
                <div class="flex-header">
                    <div>
                        <h3 class="card-title">${escapeHtml(audit.agent_name)}</h3>
                        <p class="card-subtitle">${escapeHtml(audit.filename)} · ${formatDate(audit.created_at)}</p>
                    </div>
                    <div class="report-outcome">${outcomeBadge(audit)}</div>
                </div>
                <p style="margin-top: 16px; line-height: 1.6;">${escapeHtml(audit.summary)}</p>
            </div>
        </div>

        <div class="metrics-grid metrics-grid-4">
            ${scoreTile('Overall score', audit.overall_score, 'bg-empathy', 'Weighted 40 / 30 / 30')}
            ${scoreTile('Compliance (40%)', audit.compliance_score, 'bg-danger', 'Zero-tolerance rules')}
            ${scoreTile('Protocol (30%)', audit.protocol_score, 'bg-conversations', 'Other policy rules')}
            ${scoreTile('Soft skills (30%)', audit.soft_skills_score, 'bg-professionalism',
                        `Empathy ${formatScore(audit.empathy)} · Professionalism ${formatScore(audit.professionalism)}`)}
        </div>

        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h3 class="card-title">Policy rules checked</h3>
                <p class="card-subtitle">Rules picked by retrieval (RAG) for this call, with the AI's verdict and evidence</p>
            </div>
            <div class="card-body table-responsive">
                <table class="data-table">
                    <thead><tr><th>Rule</th><th>Verdict</th><th>Evidence</th><th>Explanation</th></tr></thead>
                    <tbody>${audit.findings.map(findingRow).join('')}</tbody>
                </table>
            </div>
        </div>

        <div class="grid-2-1">
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Transcript</h3>
                    <p class="card-subtitle">Personal data redacted: ${escapeHtml(audit.pii_summary)}</p>
                </div>
                <div class="card-body"><div class="transcript-display">${escapeHtml(audit.transcript)}</div></div>
            </div>
            <div class="card">
                <div class="card-header"><h3 class="card-title">Coaching tips</h3></div>
                <div class="card-body">
                    <ul class="results-bullet-list">
                        ${audit.suggestions.map((tip) => `<li>${escapeHtml(tip)}</li>`).join('') || '<li>None</li>'}
                    </ul>
                </div>
            </div>
        </div>`;
}

function scoreTile(label, value, colorClass, caption) {
    return `<div class="metric-card ${colorClass}">
        <span class="metric-lbl">${label}</span>
        <h2 class="metric-val">${formatScore(value)}</h2>
        <p class="metric-meta">${caption}</p>
    </div>`;
}

function findingRow(finding) {
    return `<tr>
        <td><strong>${escapeHtml(finding.rule_id)}</strong> ${escapeHtml(finding.rule_title)}
            ${finding.zero_tolerance ? '<br><span class="badge-fail" style="margin-top: 4px;">Zero tolerance</span>' : ''}</td>
        <td>${VERDICT_BADGES[finding.verdict] || escapeHtml(finding.verdict)}</td>
        <td class="evidence-cell">${finding.evidence ? `“${escapeHtml(finding.evidence)}”` : ''}</td>
        <td>${escapeHtml(finding.explanation)}</td>
    </tr>`;
}

// ---------- Uploading a call ----------

function setupUpload() {
    const fileInput = $('audioInput');
    fileInput.addEventListener('change', () => {
        $('fileNameLabel').textContent = fileInput.files[0] ? fileInput.files[0].name : 'No file chosen';
    });

    $('uploadForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!fileInput.files[0]) {
            alert('Choose a call recording first.');
            return;
        }

        const form = new FormData();
        form.append('agent_name', $('agentNameInput').value.trim());
        form.append('language', $('languageSelect').value);
        form.append('audio', fileInput.files[0]);

        setUploading(true, 'Uploading…');
        try {
            const { audit_id } = await api('/api/audits', { method: 'POST', body: form });
            await waitForAudit(audit_id);
            $('uploadForm').reset();
            $('fileNameLabel').textContent = 'MP3, WAV, M4A… up to 25 MB';
            await loadOverview();
            openAudit(audit_id);
        } catch (error) {
            alert(`Audit failed: ${error.message}`);
            loadOverview();
        } finally {
            setUploading(false);
        }
    });
}

function setUploading(isUploading, message = '') {
    $('uploadButton').disabled = isUploading;
    $('progressBox').hidden = !isUploading;
    $('progressText').textContent = message;
}

// Poll the audit's status every 2 seconds until it completes or fails.
async function waitForAudit(auditId) {
    while (true) {
        const status = await api(`/api/audits/${auditId}/status`);
        if (status.status === 'completed') return;
        if (status.status === 'failed') throw new Error(status.error || 'Unknown error');
        $('progressText').textContent = `${status.progress_message}…`;
        await new Promise((resolve) => setTimeout(resolve, 2000));
    }
}

// ---------- Coaching plan ----------

function setupCoaching() {
    $('roadmapButton').addEventListener('click', async () => {
        const content = $('roadmapContent');
        $('roadmapButton').disabled = true;
        content.innerHTML = '<div class="no-data-msg"><div class="spinner" style="margin: 0 auto 12px;"></div>AI is building the plan…</div>';
        try {
            const { roadmap } = await api('/api/coaching-roadmap', { method: 'POST' });
            content.innerHTML = DOMPurify.sanitize(marked.parse(roadmap));
        } catch (error) {
            content.innerHTML = `<div class="badge-fail" style="padding: 16px;">${escapeHtml(error.message)}</div>`;
        } finally {
            $('roadmapButton').disabled = false;
        }
    });
}

// ---------- Start ----------

document.addEventListener('DOMContentLoaded', () => {
    applyTheme(localStorage.getItem('theme') || 'dark');
    setupNavigation();
    setupTheme();
    setupUpload();
    setupCoaching();
    $('employeeSelect').addEventListener('change', (event) => loadEmployee(event.target.value));
    loadOverview().catch((error) => alert(`Could not load the dashboard: ${error.message}`));
});
