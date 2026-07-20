/* ==========================================
   AUDITOR PRO - DYNAMIC DASHBOARD ENGINE
   Interactivity, API integrations, and ApexCharts rendering
   ========================================== */

document.addEventListener('DOMContentLoaded', () => {
    // Initializer calls
    initializeDate();
    initNavigation();
    initAudioUploader();
    initSubTabs();
    loadDashboardData();
    initEmailPanel();
    initAgentDeepDivePanel();
    initThemeToggle();
    initUserInfo();
});


// Global state for charts to allow updates
let agentCompareChart = null;
let leaderboardScatterChart = null;
let globalData = null; // Stored stats data

/* ================= Set Current Date Helper ================= */
function initializeDate() {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('header-date-text').textContent = new Date().toLocaleDateString('en-US', options);
}

/* ================= Single Page Application Navigation ================= */
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const panels = document.querySelectorAll('.content-panel');
    const titleText = document.getElementById('panel-title-text');
    const subtitleText = document.getElementById('panel-subtitle-text');

    const panelMeta = {
        'home-panel': { title: 'Home Dashboard', subtitle: 'Quality & compliance metrics aggregates' },
        'reports-panel': { title: 'Reports & Analytics', subtitle: 'Advanced agent analytics & coaching roadmap' },
        'email-panel': { title: 'Email Quality Auditor', subtitle: 'Analyze email communications for quality guidelines' },
        'agent-panel': { title: 'Agent Deep-Dive', subtitle: 'Individual scorecard and historical transcripts' }
    };

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const target = item.getAttribute('data-target');
            
            // Toggle active navigation items
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Toggle active content panel
            panels.forEach(p => p.classList.remove('active'));
            document.getElementById(target).classList.add('active');

            // Set Title & Subtitle text
            if (panelMeta[target]) {
                titleText.textContent = panelMeta[target].title;
                subtitleText.textContent = panelMeta[target].subtitle;
            }

            // Perform specific panel reload actions if necessary
            if (target === 'home-panel') {
                loadDashboardData();
            } else if (target === 'reports-panel') {
                renderLeaderboard();
            } else if (target === 'agent-panel') {
                loadAgentDropdown();
            }
        });
    });
}

/* ================= Audio File Uploader & Processing Logic ================= */
function initAudioUploader() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('audioFile');
    const fileInfoText = document.getElementById('fileInfoText');
    const processBtn = document.getElementById('processAudioBtn');

    // Trigger click on click
    dropzone.addEventListener('click', () => fileInput.click());

    // Drag events
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--primary)';
        dropzone.style.background = 'rgba(88, 166, 255, 0.04)';
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = 'var(--border-color)';
        dropzone.style.background = 'rgba(8, 11, 17, 0.4)';
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--border-color)';
        dropzone.style.background = 'rgba(8, 11, 17, 0.4)';
        
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            updateFileInfoLabel(fileInput.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            updateFileInfoLabel(fileInput.files[0]);
        }
    });

    function updateFileInfoLabel(file) {
        fileInfoText.textContent = file.name.length > 25 ? file.name.substring(0, 22) + '...' : file.name;
    }

    // Process & Score audio button click
    processBtn.addEventListener('click', () => {
        const agentName = document.getElementById('audioAgent').value.trim();
        const language = document.getElementById('audioLang').value;
        const file = fileInput.files[0];

        if (!agentName) {
            alert('Please assign an Agent Name for this audio audit.');
            return;
        }
        if (!file) {
            alert('Please upload an MP3 conversation file first.');
            return;
        }

        // Show Progress Bar
        const progressContainer = document.getElementById('uploadProgressContainer');
        const progressBarFill = document.getElementById('progressBarFill');
        const progressStatus = document.getElementById('progressStatusText');
        const progressPercent = document.getElementById('progressPercentText');

        progressContainer.style.display = 'block';
        processBtn.disabled = true;
        processBtn.style.opacity = '0.5';

        // Prepare FormData
        const formData = new FormData();
        formData.append('audioFile', file);
        formData.append('agentName', agentName);
        formData.append('language', language);

        // Upload audio
        fetch('/api/upload-audio', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Task created, start status polling
                pollTaskStatus(data.task_id);
            } else {
                throw new Error(data.error || 'Failed to start processing');
            }
        })
        .catch(err => {
            alert('Error starting audit: ' + err.message);
            resetUploaderState();
        });

        // Polling status
        function pollTaskStatus(taskId) {
            const interval = setInterval(() => {
                fetch(`/api/task-status/${taskId}`)
                .then(res => res.json())
                .then(task => {
                    progressStatus.textContent = task.status;
                    progressPercent.textContent = task.progress + '%';
                    progressBarFill.style.width = task.progress + '%';

                    if (task.complete) {
                        clearInterval(interval);
                        alert('Audio Conversation Audited Successfully!');
                        resetUploaderState();
                        loadDashboardData();
                    } else if (task.error) {
                        clearInterval(interval);
                        alert('Auditing failed: ' + task.error);
                        resetUploaderState();
                    }
                })
                .catch(() => {
                    clearInterval(interval);
                    resetUploaderState();
                });
            }, 1000);
        }

        function resetUploaderState() {
            processBtn.disabled = false;
            processBtn.style.opacity = '1';
            progressContainer.style.display = 'none';
            progressBarFill.style.width = '0%';
            fileInput.value = '';
            fileInfoText.textContent = 'No file chosen';
        }
    });
}

/* ================= Load Core Dashboard Averages & Tables ================= */
function loadDashboardData() {
    fetch('/api/stats')
    .then(res => res.json())
    .then(data => {
        globalData = data;
        
        // Populate stats cards
        document.getElementById('teamEmpathyVal').textContent = data.team_empathy_avg.toFixed(2);
        document.getElementById('teamProfessionalismVal').textContent = data.team_prof_avg.toFixed(2);
        document.getElementById('teamAuditsVal').textContent = data.total_audits;

        // Render Quality Comparison Chart
        renderQualityChart(data.agent_performances);

        // Populate Violations alert box
        const violationsContainer = document.getElementById('globalViolationsList');
        violationsContainer.innerHTML = '';
        if (data.top_violations && data.top_violations.length) {
            data.top_violations.forEach((v, index) => {
                const item = document.createElement('div');
                item.className = 'violation-alert-card';
                item.innerHTML = `
                    <div class="violation-alert-title">${index + 1}. ${v.violation}</div>
                    <div class="violation-alert-meta">Identified in ${v.count} audit logs</div>
                `;
                violationsContainer.appendChild(item);
            });
        } else {
            violationsContainer.innerHTML = '<div class="badge-pass" style="padding: 16px; width: 100%; border-radius: 8px; justify-content: center;">✓ No major policy violations recorded.</div>';
        }

        // Populate Recent Audits Table
        const tableBody = document.getElementById('recentAuditsTableBody');
        tableBody.innerHTML = '';
        if (data.recent_audits && data.recent_audits.length) {
            data.recent_audits.forEach(row => {
                const tr = document.createElement('tr');
                
                const avgScore = (row.empathy + row.professionalism) / 2;
                const statusClass = row.compliance === 'PASS' ? 'badge-pass' : row.compliance === 'WARN' ? 'badge-warn' : 'badge-fail';
                const sourceIcon = row.Source === 'Audio' ? '📞 Audio' : '📧 Email';

                tr.innerHTML = `
                    <td style="font-weight: 700;">${row.Agent}</td>
                    <td>${row.empathy.toFixed(1)}</td>
                    <td>${row.professionalism.toFixed(1)}</td>
                    <td><span style="font-size:12.5px; opacity:0.8;">${sourceIcon}</span></td>
                    <td><span class="${statusClass}">${row.compliance}</span></td>
                `;
                tableBody.appendChild(tr);
            });
        } else {
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No compliance data index found. Please upload calls.</td></tr>';
        }
    })
    .catch(err => console.error('Failed to load stats: ', err));
}

/* ================= Render ApexCharts Bar Chart (Comparison) ================= */
function renderQualityChart(agentPerformanceList) {
    const chartDiv = document.getElementById('agentCompareChart');
    if (!chartDiv) return;

    if (!agentPerformanceList || !agentPerformanceList.length) {
        chartDiv.innerHTML = '<div class="no-data-msg">No agent comparison records available.</div>';
        return;
    }

    chartDiv.innerHTML = '';

    const categories = agentPerformanceList.map(a => a.Agent);
    const empathyData = agentPerformanceList.map(a => parseFloat(a.empathy.toFixed(1)));
    const profData = agentPerformanceList.map(a => parseFloat(a.professionalism.toFixed(1)));

    const options = {
        series: [{
            name: 'Empathy',
            data: empathyData
        }, {
            name: 'Professionalism',
            data: profData
        }],
        chart: {
            type: 'bar',
            height: 350,
            background: 'transparent',
            toolbar: { show: false },
            foreColor: '#8b949e'
        },
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '55%',
                borderRadius: 4
            },
        },
        dataLabels: {
            enabled: false
        },
        colors: ['#58a6ff', '#3fb950'],
        stroke: {
            show: true,
            width: 2,
            colors: ['transparent']
        },
        xaxis: {
            categories: categories,
            axisBorder: { color: 'rgba(255,255,255,0.08)' },
            axisTicks: { color: 'rgba(255,255,255,0.08)' }
        },
        yaxis: {
            min: 0,
            max: 100,
            title: { text: 'Score' }
        },
        fill: {
            opacity: 1
        },
        grid: {
            borderColor: 'rgba(255, 255, 255, 0.05)',
            strokeDashArray: 4
        },
        legend: {
            position: 'top',
            horizontalAlign: 'right'
        },
        tooltip: {
            theme: 'dark',
            y: {
                formatter: function (val) {
                    return val + "/100"
                }
            }
        }
    };

    agentCompareChart = new ApexCharts(chartDiv, options);
    agentCompareChart.render();
}

/* ================= Sub tabs controller (Emails Auditor Panel) ================= */
function initSubTabs() {
    const tabs = document.querySelectorAll('.sub-tab');
    const bodies = document.querySelectorAll('.tab-body');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const target = tab.getAttribute('data-sub');
            bodies.forEach(b => {
                if (b.id === target) {
                    b.classList.add('active');
                } else {
                    b.classList.remove('active');
                }
            });
        });
    });
}

/* ================= Reports Scatter Leaderboard & Roadmap ================= */
function renderLeaderboard() {
    const scatterDiv = document.getElementById('leaderboardScatterChart');
    if (!scatterDiv) return;

    if (!globalData || !globalData.agent_performances || !globalData.agent_performances.length) {
        scatterDiv.innerHTML = '<div class="no-data-msg">Upload call logs first to draw classifications.</div>';
        return;
    }

    scatterDiv.innerHTML = '';

    // Calculate classifications
    let stars = 0, robots = 0, charmers = 0, risks = 0;
    const scatterSeries = [];

    globalData.agent_performances.forEach(a => {
        const x = parseFloat(a.empathy.toFixed(1));
        const y = parseFloat(a.professionalism.toFixed(1));
        
        let category = '⚠️ Risk';
        if (x >= 70 && y >= 70) {
            category = '⭐ Star';
            stars++;
        } else if (y >= 70 && x < 70) {
            category = '🤖 Robot';
            robots++;
        } else if (x >= 70 && y < 70) {
            category = '✨ Charmer';
            charmers++;
        } else {
            risks++;
        }

        scatterSeries.push({
            name: category,
            data: [[x, y]],
            agent: a.Agent
        });
    });

    // Populate classifications numbers
    document.getElementById('starsCount').textContent = stars + ' Agent' + (stars === 1 ? '' : 's');
    document.getElementById('robotsCount').textContent = robots + ' Agent' + (robots === 1 ? '' : 's');
    document.getElementById('charmersCount').textContent = charmers + ' Agent' + (charmers === 1 ? '' : 's');
    document.getElementById('risksCount').textContent = risks + ' Agent' + (risks === 1 ? '' : 's');

    // Group series by category to color code
    const categoriesMap = {
        '⭐ Star': { color: '#3fb950', data: [] },
        '🤖 Robot': { color: '#58a6ff', data: [] },
        '✨ Charmer': { color: '#d29922', data: [] },
        '⚠️ Risk': { color: '#f85149', data: [] }
    };

    scatterSeries.forEach(item => {
        categoriesMap[item.name].data.push({
            x: item.data[0][0],
            y: item.data[0][1],
            agentName: item.agent
        });
    });

    const series = Object.keys(categoriesMap).map(key => ({
        name: key,
        data: categoriesMap[key].data
    })).filter(s => s.data.length > 0);

    const options = {
        series: series,
        chart: {
            height: 350,
            type: 'scatter',
            background: 'transparent',
            toolbar: { show: false },
            foreColor: '#8b949e'
        },
        xaxis: {
            tickAmount: 5,
            min: 0,
            max: 100,
            title: { text: 'Empathy Score' },
            axisBorder: { color: 'rgba(255,255,255,0.08)' },
            axisTicks: { color: 'rgba(255,255,255,0.08)' }
        },
        yaxis: {
            min: 0,
            max: 100,
            title: { text: 'Professionalism Score' }
        },
        grid: {
            borderColor: 'rgba(255, 255, 255, 0.05)',
            strokeDashArray: 4
        },
        colors: ['#3fb950', '#58a6ff', '#d29922', '#f85149'],
        markers: {
            size: 10,
            strokeWidth: 2,
            strokeColors: '#0c0f16'
        },
        annotations: {
            xaxis: [{
                x: 70,
                borderColor: '#8b949e',
                strokeDashArray: 4,
                label: {
                    text: 'Empathy Threshold',
                    style: { color: '#8b949e', background: '#161b22' }
                }
            }],
            yaxis: [{
                y: 70,
                borderColor: '#8b949e',
                strokeDashArray: 4,
                label: {
                    text: 'Professionalism Threshold',
                    style: { color: '#8b949e', background: '#161b22' }
                }
            }]
        },
        tooltip: {
            theme: 'dark',
            custom: function({series, seriesIndex, dataPointIndex, w}) {
                const point = w.config.series[seriesIndex].data[dataPointIndex];
                return `<div class="chart-tooltip" style="padding:12px; background:#161b22; border:1px solid rgba(255,255,255,0.1); border-radius:6px;">
                    <div style="font-weight:700; color:#fff;">Agent: ${point.agentName}</div>
                    <div style="margin-top:4px; font-size:12px; color:#8b949e;">Empathy: ${point.x}</div>
                    <div style="font-size:12px; color:#8b949e;">Professionalism: ${point.y}</div>
                </div>`;
            }
        }
    };

    leaderboardScatterChart = new ApexCharts(scatterDiv, options);
    leaderboardScatterChart.render();
}

// Generate Coaching Roadmap Button click
const generateRoadmapBtn = document.getElementById('generateRoadmapBtn');
const downloadRoadmapPdfBtn = document.getElementById('downloadRoadmapPdfBtn');
const coachingRoadmapContent = document.getElementById('coachingRoadmapContent');
const roadmapLoading = document.getElementById('roadmapLoading');

if (generateRoadmapBtn) {
    generateRoadmapBtn.addEventListener('click', () => {
        roadmapLoading.style.display = 'flex';
        coachingRoadmapContent.style.display = 'none';
        downloadRoadmapPdfBtn.style.display = 'none';

        fetch('/api/generate-roadmap', {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            roadmapLoading.style.display = 'none';
            coachingRoadmapContent.style.display = 'block';
            
            if (data.success) {
                // Parse markdown into HTML and display
                coachingRoadmapContent.innerHTML = marked.parse(data.roadmap);
                downloadRoadmapPdfBtn.style.display = 'inline-flex';
            } else {
                coachingRoadmapContent.innerHTML = `<div class="badge-fail" style="padding: 16px; border-radius: 8px;">Error generating roadmap: ${data.error}</div>`;
            }
        })
        .catch(err => {
            roadmapLoading.style.display = 'none';
            coachingRoadmapContent.style.display = 'block';
            coachingRoadmapContent.innerHTML = `<div class="badge-fail" style="padding: 16px; border-radius: 8px;">Failed to reach Groq server: ${err.message}</div>`;
        });
    });
}

// Download PDF buttons click
if (downloadRoadmapPdfBtn) {
    downloadRoadmapPdfBtn.addEventListener('click', () => {
        // Send a post request to download PDF roadmap
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/download-roadmap-pdf';
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    });
}

const downloadSummaryPdfBtn = document.getElementById('downloadSummaryPdfBtn');
if (downloadSummaryPdfBtn) {
    downloadSummaryPdfBtn.addEventListener('click', () => {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/download-summary-pdf';
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    });
}


/* ================= Email Quality Auditor Panel ================= */
function initEmailPanel() {
    const agentSelect = document.getElementById('emailAgentSelect');
    const agentInput = document.getElementById('emailAgentInput');
    const fetchEmailBtn = document.getElementById('fetchEmailBtn');
    const scoreManualEmailBtn = document.getElementById('scoreManualEmailBtn');
    const resultsLoading = document.getElementById('emailResultsLoading');
    const resultsDisplay = document.getElementById('emailResultsDisplay');
    const noDataMsg = document.getElementById('emailNoDataMsg');

    // Load defaults for IMAP email uploader (fetched from server)
    fetch('/api/default-imap')
    .then(res => res.json())
    .then(config => {
        if (config.server) document.getElementById('imapServer').value = config.server;
        if (config.port) document.getElementById('imapPort').value = config.port;
        if (config.email) document.getElementById('imapEmail').value = config.email;
        if (config.password) document.getElementById('imapPassword').placeholder = 'Configured in server env';
    })
    .catch(() => {});

    // Manage Agent Select change
    agentSelect.addEventListener('change', () => {
        if (agentSelect.value === 'new_agent') {
            agentInput.style.display = 'block';
        } else {
            agentInput.style.display = 'none';
        }
    });

    // Populate dropdown selection
    fetch('/api/stats')
    .then(res => res.json())
    .then(data => {
        agentSelect.innerHTML = '<option value="">-- Choose Agent --</option>';
        if (data.agents && data.agents.length) {
            data.agents.forEach(agentName => {
                const opt = document.createElement('option');
                opt.value = agentName;
                opt.textContent = agentName;
                agentSelect.appendChild(opt);
            });
        }
        
        const newOpt = document.createElement('option');
        newOpt.value = 'new_agent';
        newOpt.textContent = 'New Agent...';
        agentSelect.appendChild(newOpt);
    });

    // Fetch and audit IMAP emails
    fetchEmailBtn.addEventListener('click', () => {
        const agent = getSelectedAgentName();
        if (!agent) {
            alert('Please assign this audit to an Agent.');
            return;
        }

        const server = document.getElementById('imapServer').value.trim();
        const port = document.getElementById('imapPort').value.trim();
        const emailVal = document.getElementById('imapEmail').value.trim();
        const passwordVal = document.getElementById('imapPassword').value;
        const folder = document.getElementById('imapFolder').value.trim();

        resultsLoading.style.display = 'flex';
        resultsDisplay.style.display = 'none';
        noDataMsg.style.display = 'none';

        fetch('/api/extract-imap-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agentName: agent,
                server,
                port,
                email: emailVal,
                password: passwordVal,
                folder
            })
        })
        .then(res => res.json())
        .then(data => {
            resultsLoading.style.display = 'none';
            if (data.success) {
                renderAssessmentResults(data.result);
                // Clear inputs and reload statistics dynamically
                loadDashboardData();
            } else {
                noDataMsg.style.display = 'block';
                noDataMsg.innerHTML = `<div class="badge-fail" style="padding: 16px; border-radius: 8px; width:100%;">IMAP Sync Error: ${data.error}</div>`;
            }
        })
        .catch(err => {
            resultsLoading.style.display = 'none';
            noDataMsg.style.display = 'block';
            noDataMsg.innerHTML = `<div class="badge-fail" style="padding: 16px; border-radius: 8px; width:100%;">Connection error: ${err.message}</div>`;
        });
    });

    // Manual scoring trigger
    scoreManualEmailBtn.addEventListener('click', () => {
        const agent = getSelectedAgentName();
        if (!agent) {
            alert('Please assign this audit to an Agent.');
            return;
        }

        const emailText = document.getElementById('pastedEmailContent').value.trim();
        if (!emailText) {
            alert('Please paste the email content first.');
            return;
        }

        resultsLoading.style.display = 'flex';
        resultsDisplay.style.display = 'none';
        noDataMsg.style.display = 'none';

        fetch('/api/manual-score-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agentName: agent,
                emailText
            })
        })
        .then(res => res.json())
        .then(data => {
            resultsLoading.style.display = 'none';
            if (data.success) {
                renderAssessmentResults(data.result);
                loadDashboardData();
            } else {
                noDataMsg.style.display = 'block';
                noDataMsg.innerHTML = `<div class="badge-fail" style="padding: 16px; border-radius: 8px; width:100%;">Audit Error: ${data.error}</div>`;
            }
        })
        .catch(err => {
            resultsLoading.style.display = 'none';
            noDataMsg.style.display = 'block';
            noDataMsg.innerHTML = `<div class="badge-fail" style="padding: 16px; border-radius: 8px; width:100%;">Connection error: ${err.message}</div>`;
        });
    });

    function getSelectedAgentName() {
        if (agentSelect.value === 'new_agent') {
            return agentInput.value.trim();
        }
        return agentSelect.value;
    }

    function renderAssessmentResults(result) {
        resultsDisplay.style.display = 'block';
        
        // Empathy card
        document.getElementById('emailEmpathyVal').textContent = result.empathy + '/100';
        // Professionalism card
        document.getElementById('emailProfessionalismVal').textContent = result.professionalism + '/100';
        
        // Compliance outcome
        const outcomeCard = document.getElementById('emailOutcomeCard');
        const outcomeVal = document.getElementById('emailOutcomeVal');
        outcomeVal.textContent = result.compliance.toUpperCase();

        outcomeCard.className = 'result-metric-card';
        if (result.compliance.toUpperCase() === 'PASS') {
            outcomeCard.style.borderLeft = '4px solid var(--success)';
            outcomeVal.style.color = 'var(--success)';
        } else if (result.compliance.toUpperCase() === 'WARN') {
            outcomeCard.style.borderLeft = '4px solid var(--warning)';
            outcomeVal.style.color = 'var(--warning)';
        } else {
            outcomeCard.style.borderLeft = '4px solid var(--error)';
            outcomeVal.style.color = 'var(--error)';
        }

        // Reason Text
        document.getElementById('emailReasonText').textContent = result.reason;

        // Violations bullet point lists
        const violationsContainer = document.getElementById('emailViolationsList');
        violationsContainer.innerHTML = '';
        if (result.violations && result.violations.length && result.violations[0] !== 'None') {
            result.violations.forEach(v => {
                if (v && v.trim()) {
                    const li = document.createElement('li');
                    li.textContent = v;
                    violationsContainer.appendChild(li);
                }
            });
        } else {
            violationsContainer.innerHTML = '<li style="color: var(--success); font-weight:700;">✓ No policy violations</li>';
        }

        // Suggestions bullet point lists
        const suggestionsContainer = document.getElementById('emailSuggestionsList');
        suggestionsContainer.innerHTML = '';
        if (result.suggestions && result.suggestions.length && result.suggestions[0] !== 'None') {
            result.suggestions.forEach(s => {
                if (s && s.trim()) {
                    const li = document.createElement('li');
                    li.textContent = s;
                    suggestionsContainer.appendChild(li);
                }
            });
        } else {
            suggestionsContainer.innerHTML = '<li>No suggestions recorded.</li>';
        }
    }
}

/* ================= Agent Deep-Dive Panel ================= */
function initAgentDeepDivePanel() {
    const agentSelect = document.getElementById('agentSelectDropdown');
    
    agentSelect.addEventListener('change', () => {
        const agentName = agentSelect.value;
        if (!agentName) {
            document.getElementById('agentDeepDiveContainer').style.display = 'none';
            document.getElementById('agentNoDataMsg').style.display = 'block';
            return;
        }

        // Fetch metrics for selected agent
        fetch(`/api/agent-metrics/${encodeURIComponent(agentName)}`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                document.getElementById('agentNoDataMsg').style.display = 'none';
                document.getElementById('agentDeepDiveContainer').style.display = 'block';

                // Update Empathy and Professionalism values
                document.getElementById('agentAvgEmpathy').textContent = data.empathy.toFixed(1);
                document.getElementById('agentAvgProf').textContent = data.professionalism.toFixed(1);

                // Update Compliance block status
                const complianceVal = document.getElementById('agentComplianceStatus');
                const complianceCard = complianceVal.parentElement;
                complianceVal.textContent = data.compliance;

                complianceCard.className = 'metric-container';
                if (data.compliance === 'PASS') {
                    complianceCard.classList.add('pastel-green');
                } else if (data.compliance === 'WARN') {
                    complianceCard.classList.add('pastel-yellow');
                } else {
                    complianceCard.classList.add('pastel-purple');
                }

                // Total PII masked
                document.getElementById('agentTotalMasking').textContent = data.total_pii_masked;

                // Total conversations counts
                document.getElementById('agentTotalConvos').textContent = data.total_convos;
                document.getElementById('agentSourceBreakdown').textContent = `Audio: ${data.total_audio} | Email: ${data.total_email}`;

                // Major violations Top 5 lists
                const vList = document.getElementById('agentViolationsList');
                vList.innerHTML = '';
                if (data.top_violations && data.top_violations.length) {
                    data.top_violations.forEach(v => {
                        const li = document.createElement('li');
                        li.innerHTML = `• <strong>${v[0]}</strong> (${v[1]} times)`;
                        vList.appendChild(li);
                    });
                } else {
                    vList.innerHTML = '<div class="badge-pass" style="padding: 8px; width: 100%; border-radius: 6px; justify-content: center;">✓ No violations recorded.</div>';
                }

                // Major suggestions Top 5 lists
                const sList = document.getElementById('agentSuggestionsList');
                sList.innerHTML = '';
                if (data.top_suggestions && data.top_suggestions.length) {
                    data.top_suggestions.forEach(s => {
                        const li = document.createElement('li');
                        li.innerHTML = `• <strong>${s[0]}</strong> (${s[1]} times)`;
                        sList.appendChild(li);
                    });
                } else {
                    sList.innerHTML = '<li>No suggestions recorded.</li>';
                }

                // Masked conversation history accordions
                const accordionContainer = document.getElementById('agentHistoryAccordionList');
                accordionContainer.innerHTML = '';
                if (data.history && data.history.length) {
                    data.history.forEach((h, index) => {
                        const sourceIcon = h.Source === 'Audio' ? '📞 Audio' : '📧 Email';
                        const statusEmoji = h.compliance === 'PASS' ? '✅' : h.compliance === 'WARN' ? '⚠️' : '❌';
                        const complianceClass = h.compliance === 'PASS' ? 'badge-pass' : h.compliance === 'WARN' ? 'badge-warn' : 'badge-fail';

                        const div = document.createElement('div');
                        div.className = 'accordion-item';
                        div.innerHTML = `
                            <div class="accordion-header" onclick="toggleAccordion(this)">
                                <div class="accordion-title-block">
                                    <span style="opacity:0.8;">${sourceIcon} Analysis</span>
                                    <span class="${complianceClass}" style="padding: 2px 6px; font-size:10.5px;">${h.compliance} ${statusEmoji}</span>
                                </div>
                                <div class="accordion-scores">
                                    <span>Empathy: ${h.empathy.toFixed(0)}</span>
                                    <span>|</span>
                                    <span>Professionalism: ${h.professionalism.toFixed(0)}</span>
                                    <i data-lucide="chevron-down" style="width: 16px; height: 16px;"></i>
                                </div>
                            </div>
                            <div class="accordion-content">
                                <p style="margin-bottom: 12px; font-size:13.5px;"><strong style="color: var(--primary);">Evaluation Details:</strong> ${h.reason}</p>
                                <div class="transcript-display">${h.Transcript}</div>
                                <span class="masking-analysis-lbl">
                                    <i data-lucide="shield-alert" style="width: 14px; height: 14px;"></i>
                                    <span>PII Assessment: ${h.masking_analysis || 'No sensitive fields detected.'}</span>
                                </span>
                            </div>
                        `;
                        accordionContainer.appendChild(div);
                    });
                    lucide.createIcons();
                } else {
                    accordionContainer.innerHTML = '<div class="no-data-msg">No transcripts logged.</div>';
                }

            } else {
                alert('Failed to retrieve agent statistics.');
            }
        });
    });
}

// Custom Accordion Toggle Trigger Helper
window.toggleAccordion = function(headerElement) {
    const parent = headerElement.parentElement;
    const icon = headerElement.querySelector('[data-lucide="chevron-down"]');
    
    if (parent.classList.contains('open')) {
        parent.classList.remove('open');
        if (icon) icon.style.transform = 'rotate(0deg)';
    } else {
        parent.classList.add('open');
        if (icon) icon.style.transform = 'rotate(180deg)';
    }
};

function loadAgentDropdown() {
    const agentSelect = document.getElementById('agentSelectDropdown');
    fetch('/api/stats')
    .then(res => res.json())
    .then(data => {
        const currentVal = agentSelect.value;
        agentSelect.innerHTML = '<option value="">-- Choose Agent --</option>';
        if (data.agents && data.agents.length) {
            data.agents.forEach(agentName => {
                const opt = document.createElement('option');
                opt.value = agentName;
                opt.textContent = agentName;
                if (agentName === currentVal) opt.selected = true;
                agentSelect.appendChild(opt);
            });
        }
    });
}

/* ================= Theme Toggle Logic ================= */
function initThemeToggle() {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeIcon = document.getElementById('themeIcon');
    
    if (!themeToggleBtn || !themeIcon) return;
    
    function updateThemeIcon(theme) {
        if (theme === 'light') {
            themeIcon.setAttribute('data-lucide', 'moon');
        } else {
            themeIcon.setAttribute('data-lucide', 'sun');
        }
        lucide.createIcons();
    }
    
    // Initial setup based on current theme attribute
    const savedTheme = localStorage.getItem('theme') || 'dark';
    updateThemeIcon(savedTheme);
    
    themeToggleBtn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        const targetTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', targetTheme);
        localStorage.setItem('theme', targetTheme);
        updateThemeIcon(targetTheme);
    });
}

/* ================= Dynamic User Info Initialization ================= */
function initUserInfo() {
    fetch('/api/user-info', { credentials: 'include' })
        .then(res => res.json())
        .then(data => {
            if (data && data.logged_in) {
                const avatarEl = document.querySelector('.user-avatar');
                const nameEl = document.querySelector('.user-name');
                const roleEl = document.querySelector('.user-role');
                if (avatarEl && (avatarEl.textContent.includes('{{') || !avatarEl.textContent.trim())) {
                    avatarEl.textContent = data.initials;
                }
                if (nameEl && (nameEl.textContent.includes('{{') || !nameEl.textContent.trim())) {
                    nameEl.textContent = data.username;
                    nameEl.title = data.username;
                }
                if (roleEl && (roleEl.textContent.includes('{{') || !roleEl.textContent.trim())) {
                    roleEl.textContent = data.organization;
                    roleEl.title = data.organization;
                }
            }
        })
        .catch(err => console.log('User info fetch note:', err));
}

