/* ============================================
   CI/CD Operations Console — App Controller
   SPA Navigation, API Fetching, Dynamic Rendering
   ============================================ */

(function () {
    'use strict';

    // ---- State ----
    const state = {
        activePage: 'dashboard',
        metrics: {},
        activePipelines: [],
        historyPipelines: [],
        resourceHistory: { cpu: [], ram: [], labels: [] },
        expandedPipelineId: null,
        refreshInterval: null,
        metricsInterval: null,
        decisionInterval: null,
        systemLogs: [],
    };

    const chartInstances = {
        resource: null,
        waste: null,
        testAnalytics: null,
        stageTiming: null,
        frequency: null,
        durationTrend: null,
        successDonut: null
    };

    // ---- API Helpers ----
    async function fetchJSON(url) {
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Fetch error [${url}]:`, err);
            addSystemLog('error', `API call failed: ${url} — ${err.message}`);
            return null;
        }
    }

    // ---- System Logs ----
    function addSystemLog(level, message) {
        const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
        state.systemLogs.unshift({ ts, level, message });
        if (state.systemLogs.length > 200) state.systemLogs.length = 200;
        if (state.activePage === 'logs') renderSystemLogs();
    }

    // ---- Navigation ----
    function initNavigation() {
        document.querySelectorAll('.nav-link[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                navigateTo(link.dataset.page);
            });
        });
    }

    function navigateTo(page) {
        state.activePage = page;

        document.querySelectorAll('.nav-link[data-page]').forEach(l => l.classList.remove('active'));
        document.querySelector(`.nav-link[data-page="${page}"]`)?.classList.add('active');

        document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
        document.getElementById(`page-${page}`)?.classList.add('active');

        addSystemLog('info', `Navigated to ${page} page`);
        loadPageData(page);
    }

    // ---- Data Loading ----
    async function loadPageData(page) {
        switch (page) {
            case 'dashboard':
                await Promise.all([
                    loadMetrics(),
                    loadActivePipelines(),
                    loadActiveDeployments(),
                    loadSystemMetrics(),
                    loadDecision()
                ]);
                break;
            case 'history':
                await loadHistory();
                break;
            case 'metrics':
                await loadMetricsPage();
                break;
            case 'logs':
                renderSystemLogs();
                break;
        }
    }

    async function loadMetrics() {
        const data = await fetchJSON('/api/pipelines/metrics');
        if (data) {
            state.metrics = data;
            renderMetrics(data);
            addSystemLog('info', 'Metrics refreshed successfully');
        }
    }

    async function loadActivePipelines() {
        const data = await fetchJSON('/api/pipelines/active');
        if (data) {
            state.activePipelines = data;
            renderActivePipelines(data);
        }
        // Also load recent history for the dashboard
        const history = await fetchJSON('/api/pipelines/history');
        if (history) {
            state.historyPipelines = history;
            renderRecentPipelines(history.slice(0, 8));
        }
    }

    async function loadActiveDeployments() {
        const data = await fetchJSON('/api/deployments/active');
        if (data) {
            renderActiveDeployments(data);
        }
    }

    async function loadHistory() {
        const search = document.getElementById('history-search')?.value || '';
        const status = document.getElementById('history-filter-status')?.value || '';
        const repo = document.getElementById('history-filter-repo')?.value || '';

        let url = '/api/pipelines/history?';
        if (search) url += `search=${encodeURIComponent(search)}&`;
        if (status) url += `status=${encodeURIComponent(status)}&`;
        if (repo) url += `repo=${encodeURIComponent(repo)}&`;

        const data = await fetchJSON(url);
        if (data) {
            state.historyPipelines = data;
            renderHistoryTable(data);
            addSystemLog('info', `Build history loaded: ${data.length} pipelines`);
        }
    }

    async function loadMetricsPage() {
        const data = await fetchJSON('/api/pipelines/metrics');
        if (data) {
            state.metrics = data;
            renderMetricsCharts(data);
        }
        const history = await fetchJSON('/api/pipelines/history');
        if (history) {
            state.historyPipelines = history;
            renderDurationChart(history);
            renderStatusChart(history);
        }
    }

    async function loadSystemMetrics() {
        const data = await fetchJSON('/api/metrics');
        if (data) {
            renderSystemMetrics(data);
        }
    }

    async function loadDecision() {
        const data = await fetchJSON('/api/decision');
        if (data) {
            renderDecisionPanel(data);
        }
    }

    function renderResourceChart(cpu, ram) {
        const ctx = document.getElementById('resourceChart');
        if (!ctx) return;

        const maxPoints = 20;
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        state.resourceHistory.labels.push(now);
        state.resourceHistory.cpu.push(cpu);
        state.resourceHistory.ram.push(ram);

        if (state.resourceHistory.labels.length > maxPoints) {
            state.resourceHistory.labels.shift();
            state.resourceHistory.cpu.shift();
            state.resourceHistory.ram.shift();
        }

        if (chartInstances.resource) {
            chartInstances.resource.update('none');
        } else {
            chartInstances.resource = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: state.resourceHistory.labels,
                    datasets: [
                        {
                            label: 'CPU %',
                            data: state.resourceHistory.cpu,
                            borderColor: '#00f2ff',
                            backgroundColor: 'rgba(0, 242, 255, 0.1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'RAM %',
                            data: state.resourceHistory.ram,
                            borderColor: '#00ffa3',
                            backgroundColor: 'rgba(0, 255, 163, 0.1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            fill: true,
                            tension: 0.4
                        }
                    ]
                },
                options: getChartOptions({
                    interaction: { intersect: false, mode: 'index' },
                    scales: {
                        y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { display: false }
                    }
                })
            });
        }
    }

    function renderWasteChart(totalWaste) {
        const ctx = document.getElementById('wasteChart');
        if (!ctx) return;

        // Breakdown based on backend weights: CPU (40%), Memory (30%), Time (30%)
        // For visualization, we'll split the current waste score proportionally
        const cpuWaste = totalWaste * 0.4;
        const memWaste = totalWaste * 0.3;
        const timeWaste = totalWaste * 0.3;

        if (chartInstances.waste) {
            chartInstances.waste.data.datasets[0].data = [cpuWaste, memWaste, timeWaste];
            chartInstances.waste.update();
        } else {
            chartInstances.waste = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Resource (CPU)', 'Resource (RAM)', 'Execution Time'],
                    datasets: [{
                        data: [cpuWaste, memWaste, timeWaste],
                        backgroundColor: [
                            'rgba(0, 242, 255, 0.7)',
                            'rgba(0, 255, 163, 0.7)',
                            'rgba(255, 0, 85, 0.7)'
                        ],
                        borderWidth: 0,
                        hoverOffset: 15
                    }]
                },
                options: getChartOptions({
                    cutout: '70%',
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                    }
                })
            });
        }
    }

    // ---- Render: Background ----
    function initBackground() {
        const field = document.getElementById('star-field');
        if (!field) return;

        for (let i = 0; i < 120; i++) {
            const star = document.createElement('div');
            star.className = 'star';
            const size = Math.random() * 2.5 + 1;
            const x = Math.random() * 100;
            const y = Math.random() * 100;
            const duration = Math.random() * 4 + 1.5;
            const delay = Math.random() * 5;

            star.style.width = `${size}px`;
            star.style.height = `${size}px`;
            star.style.left = `${x}%`;
            star.style.top = `${y}%`;
            star.style.setProperty('--d', `${duration}s`);
            star.style.animationDelay = `${delay}s`;

            field.appendChild(star);
        }
    }

    // ---- Render: Global Metrics ----
    function renderMetrics(m) {
        const container = document.getElementById('metrics-grid');
        if (!container) return;

        container.innerHTML = `
            <div class="metric-card accent-blue">
                <div class="metric-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="metric-label">Total Builds</div>
                    <i data-lucide="bar-chart-2" size="16" class="text-muted"></i>
                </div>
                <div class="metric-value text-blue">${m.total_builds || 0}</div>
            </div>
            <div class="metric-card accent-green">
                <div class="metric-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="metric-label">Successful</div>
                    <i data-lucide="check-circle" size="16" class="text-green"></i>
                </div>
                <div class="metric-value text-green">${m.successful_builds || 0}</div>
            </div>
            <div class="metric-card accent-red">
                <div class="metric-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="metric-label">Failed</div>
                    <i data-lucide="x-circle" size="16" class="text-red"></i>
                </div>
                <div class="metric-value text-red">${m.failed_builds || 0}</div>
            </div>
            <div class="metric-card accent-orange">
                <div class="metric-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="metric-label">Blocked</div>
                    <i data-lucide="alert-octagon" size="16" class="text-orange"></i>
                </div>
                <div class="metric-value text-orange">${m.blocked_deployments || 0}</div>
            </div>
            <div class="metric-card accent-cyan">
                <div class="metric-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="metric-label">Avg Duration</div>
                    <i data-lucide="clock" size="16" class="text-muted"></i>
                </div>
                <div class="metric-value">${formatDuration(m.avg_pipeline_duration)}</div>
            </div>
            <div class="metric-card accent-blue">
                <div class="metric-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="metric-label">Active Pipelines</div>
                    <i data-lucide="activity" size="16" class="text-blue"></i>
                </div>
                <div class="metric-value text-blue">${m.active_pipelines || 0}</div>
            </div>
        `;
        refreshLucide();
    }

    // ---- Render: Active Pipelines ----
    function renderActivePipelines(pipelines) {
        const container = document.getElementById('active-pipelines');
        if (!container) return;

        if (!pipelines.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⏸️</div>
                    <div class="empty-state-text">No active pipelines at the moment</div>
                </div>`;
            return;
        }

        container.innerHTML = pipelines.map(p => buildPipelineCard(p)).join('');
        attachPipelineCardEvents(container);
        refreshLucide();
    }

    function renderActiveDeployments(deployments) {
        const container = document.getElementById('active-deployments');
        if (!container) return;

        if (!deployments.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🚢</div>
                    <div class="empty-state-text">No active project deployments</div>
                </div>`;
            return;
        }

        container.innerHTML = deployments.map(d => `
            <div class="pipeline-card" style="border-left: 4px solid var(--status-success);">
                <div class="pipeline-header">
                    <div class="pipeline-info">
                        <div class="pipeline-repo">
                            <i data-lucide="package" size="16" style="margin-right: 4px;"></i>
                            ${escapeHtml(d.repository || 'Unknown Project')}
                            <span class="status-badge status-success">
                                <i data-lucide="check-circle" size="11"></i>
                                LIVE
                            </span>
                        </div>
                        <div class="pipeline-meta">
                            <span class="pipeline-meta-item"><i data-lucide="hash" size="12"></i> Build #${d.pipeline_id.split('-').pop()}</span>
                            <span class="pipeline-meta-item text-mono"><i data-lucide="git-commit" size="12"></i> ${d.commit_id ? d.commit_id.substring(0, 8) : 'N/A'}</span>
                            <span class="pipeline-meta-item"><i data-lucide="calendar" size="12"></i> ${d.updated_at ? formatTimestamp(d.updated_at) : 'N/A'}</span>
                            <span class="pipeline-meta-item"><i data-lucide="link" size="12"></i> Port: ${d.deployed_port}</span>
                        </div>
                    </div>
                    <div class="pipeline-actions" style="margin-left: auto;">
                        <a href="${d.deployed_url}" target="_blank" class="log-viewer-btn" style="background: var(--status-success); color: white; border: none; text-decoration: none; display: flex; align-items: center; gap: 6px;">
                            <i data-lucide="external-link" size="14"></i> Open Application
                        </a>
                    </div>
                </div>
            </div>
        `).join('');
        refreshLucide();
    }

    // ---- Render: Recent Pipelines ----
    function renderRecentPipelines(pipelines) {
        const container = document.getElementById('recent-pipelines');
        if (!container) return;

        if (!pipelines.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-text">No pipeline runs recorded yet</div>
                </div>`;
            return;
        }

        container.innerHTML = pipelines.map(p => buildPipelineCard(p)).join('');
        attachPipelineCardEvents(container);
        refreshLucide();
    }
    function buildPipelineCard(p) {
        const stages = p.stages || [];
        const stageTimeline = stages.map(s => {
            const dur = s.duration ? ` (${s.duration}s)` : '';
            return `<div class="stage-node st-${s.status}" title="${escapeHtml(s.name)}: ${s.status}${dur}"></div>`;
        }).join('');
        const stageLabels = stages.map(s =>
            `<div class="stage-label">${s.name.split(' ')[0]}</div>`
        ).join('');

        const commitShort = (p.commit_id || '').substring(0, 8);
        const createdFormatted = p.created_at ? formatTimestamp(p.created_at) : '—';
        const duration = p.total_pipeline_duration ? formatDuration(p.total_pipeline_duration) : '—';

        // Build details section
        let detailsHTML = buildPipelineDetails(p);

        const statusIcons = {
            'success': 'check-circle',
            'failed': 'x-circle',
            'running': 'loader-2',
            'blocked': 'alert-octagon',
            'queued': 'clock',
            'pending': 'pause-circle'
        };
        const statusIcon = statusIcons[p.status] || 'circle';
        const statusIconAttr = p.status === 'running' ? 'class="spin"' : '';

        return `
        <div class="pipeline-card" data-pipeline-id="${p.id}">
            <div class="pipeline-header">
                <div class="pipeline-info">
                    <div class="pipeline-repo">
                        <i data-lucide="package" size="16" style="margin-right: 4px;"></i>
                        ${escapeHtml(p.repository || 'Unknown')}
                        <span class="status-badge status-${p.status}">
                            <i data-lucide="${statusIcon}" size="11" ${statusIconAttr}></i>
                            ${p.status}
                        </span>
                    </div>
                    <div class="pipeline-meta">
                        <span class="pipeline-meta-item"><i data-lucide="git-branch" size="12"></i> ${escapeHtml(p.branch || '—')}</span>
                        <span class="pipeline-meta-item text-mono"><i data-lucide="hash" size="12"></i> ${commitShort || '—'}</span>
                        <span class="pipeline-meta-item"><i data-lucide="user" size="12"></i> ${escapeHtml(p.commit_author || '—')}</span>
                        <span class="pipeline-meta-item"><i data-lucide="calendar" size="12"></i> ${createdFormatted}</span>
                        <span class="pipeline-meta-item"><i data-lucide="clock" size="12"></i> ${duration}</span>
                        <span class="pipeline-meta-item"><i data-lucide="zap" size="12"></i> Waste: ${p.waste_score !== null ? p.waste_score : '—'}</span>
                        ${p.cpu_usage > 0 ? `<span class="pipeline-meta-item"><i data-lucide="cpu" size="12"></i> CPU: ${p.cpu_usage}%</span>` : ''}
                        ${p.memory_usage > 0 ? `<span class="pipeline-meta-item"><i data-lucide="database" size="12"></i> RAM: ${p.memory_usage}%</span>` : ''}
                        <span class="pipeline-meta-item"><i data-lucide="shield" size="12"></i> ${p.governance_decision || '—'}</span>
                    </div>
                    <div class="pipeline-commit-msg">"${escapeHtml(p.commit_message || '')}"</div>
                </div>
            </div>
            <div class="stage-timeline">${stageTimeline}</div>
            <div class="stage-timeline-labels">${stageLabels}</div>
            <div class="pipeline-actions" style="padding: 0 16px 16px 16px; display: flex; gap: 8px;">
                <a href="/build/${p.id}" class="log-viewer-btn" style="text-decoration: none; display: inline-flex; align-items: center; justify-content: center;">
                    <i data-lucide="eye" size="12" style="margin-right: 4px;"></i> View Details
                </a>
                <button class="log-viewer-btn" onclick="window.AppController.downloadReport('${p.id}')" style="background: rgba(59, 130, 246, 0.1); color: #3b82f6; border-color: rgba(59, 130, 246, 0.2);">
                    <i data-lucide="file-text" size="12" style="margin-right: 4px;"></i> PDF Report
                </button>
            </div>
            <div class="pipeline-details">${detailsHTML}</div>
        </div>`;
    }

    // ---- Build Pipeline Details ----
    function buildPipelineDetails(p) {
        const stages = p.stages || [];

        // Stage details table
        let stageRows = stages.map(s => {
            const startFmt = s.start ? formatTime(s.start) : '—';
            const endFmt = s.end ? formatTime(s.end) : '—';
            const durFmt = s.duration ? `${s.duration}s` : '—';
            let extraMetrics = '';
            if (s.key === 'install' && s.dep_count) extraMetrics = `<br><span class="text-muted text-sm">${s.dep_count} dependencies</span>`;
            if (s.key === 'test') extraMetrics = `<br><span class="text-muted text-sm">✅${s.test_pass || 0} ❌${s.test_fail || 0} ⏭️${s.test_skip || 0}</span>`;
            if (s.key === 'build' && s.image_size) extraMetrics = `<br><span class="text-muted text-sm">Image: ${s.image_size}</span>`;
            if (s.key === 'deploy' && s.container_health) extraMetrics = `<br><span class="text-muted text-sm">Health: ${s.container_health}</span>`;

            const statusIcons = {
                'completed': 'check-circle',
                'failed': 'x-circle',
                'running': 'loader-2',
                'blocked': 'alert-octagon',
                'waiting': 'clock'
            };
            const sIcon = statusIcons[s.status] || 'circle';
            const sIconClass = s.status === 'running' ? 'class="spin"' : '';

            return `<tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px; font-weight: 600;">
                        <span class="stage-status-dot dot-${s.status}"></span>
                        <i data-lucide="${sIcon}" size="14" ${sIconClass}></i>
                        ${escapeHtml(s.name)}
                    </div>
                </td>
                <td>${startFmt}</td>
                <td>${endFmt}</td>
                <td>${durFmt}</td>
                <td><span class="status-badge status-${s.status}">${s.status}</span>${extraMetrics}</td>
            </tr>`;
        }).join('');

        let html = `
        <div class="detail-panel" style="grid-column: 1 / -1;">
            <div class="detail-panel-title">Stage Execution Details</div>
            <table class="stage-detail-table">
                <thead><tr><th>Stage</th><th>Start</th><th>End</th><th>Duration</th><th>Status</th></tr></thead>
                <tbody>${stageRows}</tbody>
            </table>
        </div>`;

        // Governance explanation
        if (p.governance_decision) {
            const isBlock = p.governance_decision === 'BLOCK';
            html += `
            <div class="explanation-box ${isBlock ? '' : 'explain-success'}">
                <div class="explanation-title">🛡️ Governance Decision: ${p.governance_decision}</div>
                <div class="explanation-text">${escapeHtml(p.governance_explanation || 'No explanation provided.')}</div>
            </div>`;
        }

        // Failure explanation
        if (p.failure_stage) {
            html += `
            <div class="explanation-box explain-failure">
                <div class="explanation-title">⚠️ Failure: ${escapeHtml(p.failure_stage)} stage</div>
                <div class="explanation-text">${escapeHtml(p.failure_explanation || '')}</div>
            </div>`;
        }

        // Log snippets
        if (p.failure_log_snippet) {
            html += `
            <div class="mt-12">
                <button class="log-viewer-btn" onclick="window.AppController.openLogModal('${escapeHtml(p.pipeline_id || '')}', \`${escapeJs(p.failure_log_snippet)}\`)">
                    📋 View Logs
                </button>
            </div>`;
        }

        return `<div class="detail-grid">${html}</div>`;
    }

    // ---- Attach Pipeline Card Events ----
    function attachPipelineCardEvents(container) {
        container.querySelectorAll('.pipeline-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't toggle if clicking a button
                if (e.target.closest('.log-viewer-btn')) return;
                card.classList.toggle('expanded');
            });
        });
    }

    // ---- Render: History Table ----
    function renderHistoryTable(pipelines) {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;

        if (!pipelines.length) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted);">No builds match your filters</td></tr>`;
            return;
        }

        tbody.innerHTML = pipelines.map(p => {
            const commitShort = (p.commit_id || '').substring(0, 8);
            const duration = p.total_pipeline_duration ? formatDuration(p.total_pipeline_duration) : '—';
            const createdFormatted = p.created_at ? formatTimestamp(p.created_at) : '—';

            const statusIcons = {
                'success': 'check-circle',
                'failed': 'x-circle',
                'running': 'loader-2',
                'blocked': 'alert-octagon',
                'queued': 'clock'
            };
            const statusIcon = statusIcons[p.status] || 'circle';

            return `<tr data-pipeline-id="${p.id}">
                <td><span class="pipeline-id-link"><i data-lucide="hash" size="12"></i> ${escapeHtml(p.pipeline_id || '')}</span></td>
                <td class="truncate" style="max-width:250px;">${escapeHtml(p.commit_message || '—')}</td>
                <td><i data-lucide="user" size="12"></i> ${escapeHtml(p.commit_author || '—')}</td>
                <td><i data-lucide="clock" size="12"></i> ${duration}</td>
                <td>
                    <span class="status-badge status-${p.status}">
                        <i data-lucide="${statusIcon}" size="11"></i>
                        ${p.status}
                    </span>
                </td>
                <td>${createdFormatted}</td>
            </tr>`;
        }).join('');

        // Click row to navigate to details
        tbody.querySelectorAll('tr[data-pipeline-id]').forEach(row => {
            row.addEventListener('click', () => {
                const pipelineId = row.dataset.pipelineId;
                openPipelineDetail(pipelineId);
            });
        });
        refreshLucide();
    }

    async function openPipelineDetail(dbId) {
        window.location.href = `/build/${dbId}`;
    }

    // ---- Render: Metrics Dashboard ----

    function renderMetricsCharts(m) {
        updateMetricCards(m);
        renderDurationTrendChart(m.history_trend);
        renderSuccessDonutChart(m.status_distribution);
        renderTestAnalyticsChart(m.history_trend);
        renderStageTimingChart(m.stage_averages);
        renderFrequencyGraph(m.build_frequency);
        renderHealthScore(m);
        renderTopContributors(m.top_authors, m.top_repositories);
        renderDeploymentStability(m.deployment_stats);
    }

    function updateMetricCards(m) {
        const container = document.getElementById('metrics-overview-cards');
        if (!container) return;

        container.innerHTML = `
            <div class="metric-card accent-blue">
                <div class="metric-icon"><i data-lucide="layers"></i></div>
                <div class="metric-content">
                    <div class="metric-label">Total Pipelines</div>
                    <div class="metric-value text-blue">${m.total_builds || 0}</div>
                    <div class="metric-trend"><i data-lucide="arrow-up-right"></i> +${m.active_pipelines} active</div>
                </div>
            </div>
            <div class="metric-card accent-green">
                <div class="metric-icon"><i data-lucide="check-circle-2"></i></div>
                <div class="metric-content">
                    <div class="metric-label">Reliability Score</div>
                    <div class="metric-value text-green">${m.health_score}%</div>
                    <div class="metric-trend">Success Rate: ${m.total_builds ? Math.round((m.successful_builds / m.total_builds) * 100) : 0}%</div>
                </div>
            </div>
            <div class="metric-card accent-purple">
                <div class="metric-icon"><i data-lucide="zap"></i></div>
                <div class="metric-content">
                    <div class="metric-label">Avg Pipeline Duration</div>
                    <div class="metric-value">${formatDuration(m.avg_pipeline_duration)}</div>
                </div>
            </div>
            <div class="metric-card accent-cyan">
                <div class="metric-icon"><i data-lucide="rocket"></i></div>
                <div class="metric-content">
                    <div class="metric-label">Deploy Success Rate</div>
                    <div class="metric-value text-cyan">${m.deployment_stats?.rate || 0}%</div>
                </div>
            </div>
        `;
        refreshLucide();
    }

    function renderDurationTrendChart(trend) {
        const ctx = document.getElementById('duration-trend-chart');
        if (!ctx) return;

        const labels = trend.map(t => t.id);
        const data = trend.map(t => t.duration);

        if (chartInstances.durationTrend) chartInstances.durationTrend.destroy();

        chartInstances.durationTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Duration (s)',
                    data,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#3b82f6',
                }]
            },
            options: getChartOptions({
                y: { title: { display: true, text: 'Seconds', color: '#9ca3af' } }
            })
        });
    }

    function renderSuccessDonutChart(dist) {
        const ctx = document.getElementById('success-donut-chart');
        if (!ctx) return;

        const dataValues = [
            dist.success || 0,
            dist.failed || 0,
            dist.blocked || 0,
            (dist.running || 0) + (dist.queued || 0)
        ];

        if (chartInstances.successDonut) chartInstances.successDonut.destroy();

        chartInstances.successDonut = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Success', 'Failed', 'Blocked', 'In-Progress'],
                datasets: [{
                    data: dataValues,
                    backgroundColor: ['#22c55e', '#ef4444', '#f59e0b', '#3b82f6'],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // Update Legend
        const colors = ['#22c55e', '#ef4444', '#f59e0b', '#3b82f6'];
        const labels = ['Success', 'Failed', 'Blocked', 'Active'];
        const legend = document.getElementById('success-legend');
        if (legend) {
            legend.innerHTML = labels.map((l, i) => `
                <div class="legend-item">
                    <span class="legend-color" style="background:${colors[i]}"></span>
                    <span>${l} (${dataValues[i]})</span>
                </div>
            `).join('');
        }
    }

    function renderTestAnalyticsChart(trend) {
        const ctx = document.getElementById('test-analytics-chart');
        if (!ctx) return;

        const labels = trend.map(t => t.id);
        const passData = trend.map(t => t.tests_pass);
        const failData = trend.map(t => t.tests_fail);

        if (chartInstances.testAnalytics) chartInstances.testAnalytics.destroy();

        chartInstances.testAnalytics = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { label: 'Passed', data: passData, backgroundColor: '#22c55e' },
                    { label: 'Failed', data: failData, backgroundColor: '#ef4444' }
                ]
            },
            options: getChartOptions({
                scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            })
        });
    }

    function renderStageTimingChart(stages) {
        const ctx = document.getElementById('stage-timing-chart');
        if (!ctx) return;

        const labels = Object.keys(stages).map(k => k.charAt(0).toUpperCase() + k.slice(1));
        const data = Object.values(stages);

        if (chartInstances.stageTiming) chartInstances.stageTiming.destroy();

        chartInstances.stageTiming = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: 'rgba(168, 85, 247, 0.6)',
                    borderColor: '#a855f7',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: getChartOptions({
                indexAxis: 'y',
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { grid: { display: false } }
                }
            })
        });
    }

    function renderFrequencyGraph(freq) {
        const ctx = document.getElementById('frequency-chart');
        if (!ctx) return;

        const labels = Object.keys(freq);
        const data = Object.values(freq);

        if (chartInstances.frequency) chartInstances.frequency.destroy();

        chartInstances.frequency = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Builds',
                    data,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: getChartOptions()
        });
    }

    function renderHealthScore(m) {
        const gauge = document.getElementById('health-gauge');
        const val = document.getElementById('health-value');
        const factors = document.getElementById('health-factors');
        if (!gauge || !val) return;

        val.textContent = `${m.health_score}%`;
        gauge.className = 'health-gauge';
        if (m.health_score > 80) gauge.classList.add('healthy');
        else if (m.health_score > 50) gauge.classList.add('moderate');
        else gauge.classList.add('unstable');

        const successRate = m.total_builds ? Math.round((m.successful_builds / m.total_builds) * 100) : 0;

        if (factors) {
            factors.innerHTML = `
                <div class="health-item"><span>Pipeline Stability</span><span>${successRate}%</span></div>
                <div class="health-item"><span>Deployment Reliability</span><span>${m.deployment_stats.rate}%</span></div>
                <div class="health-item"><span>Avg Duration Index</span><span>Stable</span></div>
            `;
        }
    }

    function renderTopContributors(authors, repos) {
        const container = document.getElementById('top-contributors');
        if (!container) return;

        let html = '<div style="font-size:11px; color:var(--text-secondary); margin-bottom:8px;">Authors</div>';
        html += authors.map(a => `
            <div class="list-item">
                <div class="item-info"><i data-lucide="user" size="12"></i> ${a.name}</div>
                <span class="item-value">${a.count} builds</span>
            </div>
        `).join('');

        html += '<div style="font-size:11px; color:var(--text-secondary); margin:12px 0 8px;">Repositories</div>';
        html += repos.map(r => `
            <div class="list-item">
                <div class="item-info"><i data-lucide="github" size="12"></i> ${r.name}</div>
                <span class="item-value">${r.count}</span>
            </div>
        `).join('');

        container.innerHTML = html;
        refreshLucide();
    }

    function renderDeploymentStability(stats) {
        const container = document.getElementById('deployment-stability');
        if (!container) return;

        container.innerHTML = `
            <div class="health-item"><span>Total Deployed</span><span>${stats.total}</span></div>
            <div class="health-item"><span>Success Rate</span><span class="text-green">${stats.rate}%</span></div>
            <div class="health-item"><span>Failed Configs</span><span class="text-red">${stats.failed}</span></div>
            <div style="margin-top:10px; height:6px; background:#1f2937; border-radius:3px; overflow:hidden;">
                <div style="width:${stats.rate}%; height:100%; background:var(--status-success); transition: width 1s ease;"></div>
            </div>
        `;
    }

    function getChartOptions(extra = {}) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 1000, easing: 'easeOutQuart' },
            plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1f2937', borderColor: '#374151', borderWidth: 1 } },
            ...extra,
            scales: {
                x: { ticks: { color: '#9ca3af', font: { size: 10 } }, grid: { display: false }, ...(extra.scales?.x || {}) },
                y: { ticks: { color: '#9ca3af', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' }, ...(extra.scales?.y || {}) }
            }
        };
    }

    // ---- Render: System Logs ----
    function renderSystemLogs() {
        const container = document.getElementById('system-log-output');
        if (!container) return;

        container.innerHTML = state.systemLogs.map(log => {
            const levelClass = `log-level-${log.level}`;
            return `<div class="log-line"><span class="log-ts">[${log.ts}]</span><span class="${levelClass}">[${log.level.toUpperCase()}]</span> ${escapeHtml(log.message)}</div>`;
        }).join('');
    }

    // ---- Log Modal ----
    function openLogModal(pipelineId, logContent) {
        const overlay = document.getElementById('log-modal-overlay');
        const title = document.getElementById('log-modal-title');
        const content = document.getElementById('log-modal-content');
        if (!overlay) return;

        title.textContent = `Logs — ${pipelineId}`;
        content.innerHTML = highlightLogs(logContent) || 'No log content available.';
        overlay.classList.add('open');
    }

    function highlightLogs(text) {
        if (!text) return '';
        return escapeHtml(text)
            .replace(/\[ERROR\]/g, '<span class="log-level-error">[ERROR]</span>')
            .replace(/\[WARN(ING)?\]/g, '<span class="log-level-warn">$&</span>')
            .replace(/\[INFO\]/g, '<span class="log-level-info">[INFO]</span>')
            .replace(/\[SUCCESS\]/g, '<span class="log-level-success">[SUCCESS]</span>')
            .replace(/(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})/g, '<span class="log-ts">$1</span>');
    }

    function closeLogModal() {
        const overlay = document.getElementById('log-modal-overlay');
        if (overlay) overlay.classList.remove('open');
    }

    function downloadReport(id) {
        window.location.href = `/api/pipelines/report/pdf/${id}`;
    }

    function copyLogContent() {
        const content = document.getElementById('log-modal-content');
        if (content) {
            navigator.clipboard.writeText(content.textContent)
                .then(() => addSystemLog('info', 'Logs copied to clipboard'))
                .catch(() => addSystemLog('error', 'Failed to copy logs'));
        }
    }

    // ---- Utilities ----
    function formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '0s';
        const s = Math.round(seconds);
        if (s < 60) return `${s}s`;
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return `${m}m ${rem}s`;
    }

    function formatTimestamp(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleString('en-US', {
                month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit',
                hour12: false
            });
        } catch {
            return iso;
        }
    }

    function formatTime(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleTimeString('en-US', { hour12: false });
        } catch {
            return iso;
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeJs(str) {
        if (!str) return '';
        return str.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
    }

    function refreshLucide() {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    // ---- Auto Refresh ----
    function startAutoRefresh() {
        state.refreshInterval = setInterval(() => {
            if (state.activePage === 'dashboard') {
                loadMetrics();
                loadActivePipelines();
            }
        }, 15000); // 15 seconds

        // System Metrics Refresh (5s)
        state.metricsInterval = setInterval(() => {
            if (state.activePage === 'dashboard') {
                loadSystemMetrics();
            }
        }, 5000);

        // Decision Refresh (10s)
        state.decisionInterval = setInterval(() => {
            if (state.activePage === 'dashboard') {
                loadDecision();
            }
        }, 10000);
    }

    // ---- History Controls ----
    function initHistoryControls() {
        const searchInput = document.getElementById('history-search');
        const statusFilter = document.getElementById('history-filter-status');
        const repoFilter = document.getElementById('history-filter-repo');

        let debounceTimer;
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => loadHistory(), 400);
            });
        }
        if (statusFilter) statusFilter.addEventListener('change', () => loadHistory());
        if (repoFilter) repoFilter.addEventListener('change', () => loadHistory());

        const cleanBtn = document.getElementById('btn-clean-history');
        if (cleanBtn) {
            cleanBtn.addEventListener('click', async () => {
                if (confirm('Are you sure you want to PERMANENTLY delete all build history? This cannot be undone.')) {
                    const res = await fetch('/api/admin/clean-db', { method: 'POST' });
                    const data = await res.json();
                    if (res.ok) {
                        addSystemLog('success', data.message);
                        loadHistory();
                        loadMetrics();
                    } else {
                        addSystemLog('error', `Failed to clean DB: ${data.error}`);
                    }
                }
            });
        }
    }

    // ---- Init ----
    function init() {
        addSystemLog('info', 'CI/CD Operations Console initialized');
        addSystemLog('info', 'Connecting to monitoring endpoints...');
        initNavigation();
        initHistoryControls();
        initBackground();
        navigateTo('dashboard');
        startAutoRefresh();
        addSystemLog('success', 'Dashboard ready — auto-refresh enabled (15s)');

        // Close modal on overlay click
        document.getElementById('log-modal-overlay')?.addEventListener('click', (e) => {
            if (e.target === e.currentTarget) closeLogModal();
        });
    }

    // Expose for inline event handlers
    window.AppController = {
        openLogModal,
        closeLogModal,
        copyLogContent,
        downloadReport,
    };

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function renderSystemMetrics(data) {
        const container = document.getElementById('system-metrics-grid');
        if (!container) return;

        const metrics = [
            { label: 'CPU Usage', val: data.cpu, unit: '%', icon: 'cpu', color: 'cyan', showProgress: true },
            { label: 'RAM Usage', val: data.memory, unit: '%', icon: 'memory-stick', color: 'emerald', showProgress: true },
            { label: 'Disk Space', val: data.disk, unit: '%', icon: 'hard-drive', color: 'amber', showProgress: true },
            { label: 'Build Time', val: data.build_time, unit: 's', icon: 'clock', color: 'crimson', showProgress: false }
        ];

        container.innerHTML = metrics.map(m => `
            <div class="metric-card glass-pane">
                <div class="metric-icon-bg"><i data-lucide="${m.icon}" size="18"></i></div>
                <div class="metric-label font-display">${m.label}</div>
                <div class="metric-value font-mono text-glow-${m.color}">${m.val}<span class="metric-unit">${m.unit}</span></div>
                ${m.showProgress ? `
                <div class="progress-bar-wrap">
                    <div class="progress-bar-fill" style="width: ${m.val}%; background-color: var(--color-neon-${m.color});"></div>
                </div>` : '<div class="metric-status-text font-display" style="font-size: 10px; margin-top: 8px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px;">Historical Average</div>'}
            </div>
        `).join('');
        renderResourceChart(data.cpu, data.memory);
        refreshLucide();
    }

    function renderDecisionPanel(data) {
        const container = document.getElementById('decision-panel-container');
        if (!container) return;

        const statusLower = (data.decision || 'N/A').toLowerCase();
        let statusClass = 'status-delayed';
        let icon = 'alert-triangle';

        if (statusLower === 'approved') {
            statusClass = 'status-approved';
            icon = 'check-circle-2';
        } else if (statusLower === 'blocked' || statusLower === 'block') {
            statusClass = 'status-blocked';
            icon = 'x-circle';
        }

        container.innerHTML = `
            <div class="decision-panel glass-pane ${statusClass}">
                <div class="decision-glow"></div>
                <div class="decision-icon-wrap">
                    <i data-lucide="${icon}" class="text-glow-${statusClass.split('-')[1]}"></i>
                </div>
                <div class="decision-content">
                    <div class="decision-status-badge">
                        <i data-lucide="${icon}" size="14"></i>
                        Status: ${data.decision || 'PENDING'}
                    </div>
                    <div class="decision-msg font-display">
                        ${data.decision === 'APPROVED' ? 'System Safe for Deployment' : 'Deployment Safeguards Triggered'}
                    </div>
                    <div class="waste-info">
                        <span class="waste-val font-mono">${data.waste_score || 0}</span>
                        <span class="waste-threshold font-mono">/ WASTE SCORE (THRESHOLD: 80.0)</span>
                    </div>
                    <div class="decision-explanation">
                        <strong>Insights:</strong> ${escapeHtml(data.ai_explanation || 'Awaiting metrics evaluation...')}
                    </div>
                </div>
            </div>
        `;
        renderWasteChart(data.waste_score || 0);
        refreshLucide();
    }
})();
