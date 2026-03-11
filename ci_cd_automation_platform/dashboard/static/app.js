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
        expandedPipelineId: null,
        refreshInterval: null,
        systemLogs: [],
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
                await Promise.all([loadMetrics(), loadActivePipelines()]);
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

    // ---- Build Pipeline Card HTML ----
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
    let chartInstances = {};

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
})();
