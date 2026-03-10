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
                <div class="metric-label">Total Builds</div>
                <div class="metric-value text-blue">${m.total_builds || 0}</div>
            </div>
            <div class="metric-card accent-green">
                <div class="metric-label">Successful</div>
                <div class="metric-value text-green">${m.successful_builds || 0}</div>
            </div>
            <div class="metric-card accent-red">
                <div class="metric-label">Failed</div>
                <div class="metric-value text-red">${m.failed_builds || 0}</div>
            </div>
            <div class="metric-card accent-orange">
                <div class="metric-label">Blocked</div>
                <div class="metric-value text-orange">${m.blocked_deployments || 0}</div>
            </div>
            <div class="metric-card accent-cyan">
                <div class="metric-label">Avg Build Duration</div>
                <div class="metric-value">${formatDuration(m.avg_pipeline_duration)}</div>
            </div>
            <div class="metric-card accent-purple">
                <div class="metric-label">Avg Test Duration</div>
                <div class="metric-value">${formatDuration(m.avg_test_duration)}</div>
            </div>
            <div class="metric-card accent-blue">
                <div class="metric-label">Active Pipelines</div>
                <div class="metric-value text-blue">${m.active_pipelines || 0}</div>
            </div>
        `;
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
    }

    // ---- Build Pipeline Card HTML ----
    function buildPipelineCard(p) {
        const stages = p.stages || [];
        const stageTimeline = stages.map(s =>
            `<div class="stage-node st-${s.status}" title="${s.name}: ${s.status}"></div>`
        ).join('');
        const stageLabels = stages.map(s =>
            `<div class="stage-label">${s.name.split(' ')[0]}</div>`
        ).join('');

        const commitShort = (p.commit_id || '').substring(0, 8);
        const createdFormatted = p.created_at ? formatTimestamp(p.created_at) : '—';
        const duration = p.total_pipeline_duration ? formatDuration(p.total_pipeline_duration) : '—';

        // Build details section
        let detailsHTML = buildPipelineDetails(p);

        return `
        <div class="pipeline-card" data-pipeline-id="${p.id}">
            <div class="pipeline-header">
                <div class="pipeline-info">
                    <div class="pipeline-repo">
                        📦 ${escapeHtml(p.repository || 'Unknown')}
                        <span class="status-badge status-${p.status}">${p.status}</span>
                    </div>
                    <div class="pipeline-meta">
                        <span class="pipeline-meta-item">🔀 ${escapeHtml(p.branch || '—')}</span>
                        <span class="pipeline-meta-item text-mono">#${commitShort || '—'}</span>
                        <span class="pipeline-meta-item">👤 ${escapeHtml(p.commit_author || '—')}</span>
                        <span class="pipeline-meta-item">🕐 ${createdFormatted}</span>
                        <span class="pipeline-meta-item">⏱️ ${duration}</span>
                    </div>
                    <div class="pipeline-commit-msg">"${escapeHtml(p.commit_message || '')}"</div>
                </div>
            </div>
            <div class="stage-timeline">${stageTimeline}</div>
            <div class="stage-timeline-labels">${stageLabels}</div>
            <div class="pipeline-actions" style="padding: 0 16px 16px 16px; display: flex; gap: 8px;">
                <a href="/build/${p.id}" class="log-viewer-btn" style="text-decoration: none; display: inline-flex; align-items: center; justify-content: center;">
                    🔍 View Details
                </a>
                <button class="log-viewer-btn" onclick="window.AppController.downloadReport('${p.id}')" style="background: rgba(59, 130, 246, 0.1); color: #3b82f6; border-color: rgba(59, 130, 246, 0.2);">
                    📄 PDF Report
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

            return `<tr>
                <td><span class="stage-status-dot dot-${s.status}"></span>${escapeHtml(s.name)}</td>
                <td>${startFmt}</td>
                <td>${endFmt}</td>
                <td>${durFmt}</td>
                <td>${s.status}${extraMetrics}</td>
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

            return `<tr data-pipeline-id="${p.id}">
                <td><span class="pipeline-id-link">${escapeHtml(p.pipeline_id || '')}</span></td>
                <td class="truncate" style="max-width:250px;">${escapeHtml(p.commit_message || '—')}</td>
                <td>${escapeHtml(p.commit_author || '—')}</td>
                <td>${duration}</td>
                <td><span class="status-badge status-${p.status}">${p.status}</span></td>
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
    }

    async function openPipelineDetail(dbId) {
        window.location.href = `/build/${dbId}`;
    }

    // ---- Render: Metrics Charts ----
    let chartInstances = {};

    function renderMetricsCharts(m) {
        const container = document.getElementById('metrics-overview-cards');
        if (!container) return;

        container.innerHTML = `
            <div class="metric-card accent-blue">
                <div class="metric-label">Total Pipelines</div>
                <div class="metric-value text-blue">${m.total_builds || 0}</div>
            </div>
            <div class="metric-card accent-green">
                <div class="metric-label">Success Rate</div>
                <div class="metric-value text-green">${m.total_builds ? Math.round((m.successful_builds / m.total_builds) * 100) : 0}%</div>
            </div>
            <div class="metric-card accent-purple">
                <div class="metric-label">Avg Pipeline Duration</div>
                <div class="metric-value">${formatDuration(m.avg_pipeline_duration)}</div>
            </div>
            <div class="metric-card accent-cyan">
                <div class="metric-label">Avg Build Duration</div>
                <div class="metric-value">${formatDuration(m.avg_build_duration)}</div>
            </div>
        `;
    }

    function renderDurationChart(pipelines) {
        const ctx = document.getElementById('duration-chart');
        if (!ctx) return;

        const recent = pipelines.slice(0, 12).reverse();
        const labels = recent.map(p => (p.pipeline_id || '').substring(0, 10));
        const durations = recent.map(p => p.total_pipeline_duration || 0);

        if (chartInstances.duration) chartInstances.duration.destroy();

        chartInstances.duration = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Pipeline Duration (s)',
                    data: durations,
                    backgroundColor: durations.map(d => d > 150 ? 'rgba(239,68,68,0.6)' : 'rgba(59,130,246,0.6)'),
                    borderColor: durations.map(d => d > 150 ? '#ef4444' : '#3b82f6'),
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ticks: { color: '#64748b', font: { size: 10 } },
                        grid: { color: 'rgba(255,255,255,0.03)' }
                    },
                    y: {
                        ticks: { color: '#64748b' },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });
    }

    function renderStatusChart(pipelines) {
        const ctx = document.getElementById('status-chart');
        if (!ctx) return;

        const counts = { success: 0, failed: 0, blocked: 0, running: 0, queued: 0 };
        pipelines.forEach(p => {
            if (counts.hasOwnProperty(p.status)) counts[p.status]++;
        });

        if (chartInstances.status) chartInstances.status.destroy();

        chartInstances.status = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Success', 'Failed', 'Blocked', 'Running', 'Queued'],
                datasets: [{
                    data: [counts.success, counts.failed, counts.blocked, counts.running, counts.queued],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b', '#3b82f6', '#475569'],
                    borderColor: '#0a0e1a',
                    borderWidth: 3,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8', padding: 16, usePointStyle: true, pointStyleWidth: 10 }
                    }
                }
            }
        });
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
        content.textContent = logContent || 'No log content available.';
        overlay.classList.add('open');
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
