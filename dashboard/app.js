document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('redact-form');
  const input = document.getElementById('prompt-input');
  const submitBtn = document.getElementById('submit-btn');
  const submitBtnText = submitBtn.querySelector('.btn-text');
  const spinner = submitBtn.querySelector('.spinner');
  
  const statusBanner = document.getElementById('status-banner');
  const bannerText = statusBanner.querySelector('.banner-text');
  
  const entitiesSection = document.getElementById('entities-section');
  const badgeList = document.getElementById('badge-list');
  
  const redactedContent = document.getElementById('redacted-content');
  const responseContent = document.getElementById('response-content');
  
  const statTotal = document.getElementById('stat-total');
  const statRedacted = document.getElementById('stat-redacted');
  const statBlocked = document.getElementById('stat-blocked');
  const logsTbody = document.getElementById('logs-tbody');
  const refreshLogsBtn = document.getElementById('refresh-logs-btn');

  // Regex to match uppercase bracketed placeholders like [NAME_1], [SSN_1], or [REDACTED_API_KEY_1]
  const PLACEHOLDER_REGEX = /(\[[A-Z0-9_]+\])/g;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const promptText = input.value.trim();
    if (!promptText) return;

    // Reset views and set loading state
    setLoading(true);
    hideStatus();
    
    try {
      const response = await fetch('/redact-and-ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: promptText })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();
      
      // Update the side-by-side content
      renderRedactedText(data.redacted_text || '');
      renderFinalResponse(data.final_response || '');
      
      // Update entity detection badges
      renderEntityBadges(data.entities_detected || []);
      
    } catch (error) {
      console.error('Request failed:', error);
      showStatus('error', `Connection failed: Could not connect to CLOAKWELL backend at http://localhost:8000. Please ensure the backend server is running and healthy.`);
      resetOutputs();
    } finally {
      setLoading(false);
      updateDashboardData();
    }
  });

  function setLoading(isLoading) {
    if (isLoading) {
      submitBtn.disabled = true;
      submitBtnText.textContent = 'Analyzing & Querying...';
      spinner.hidden = false;
      
      // Set skeleton loaders in outputs
      redactedContent.innerHTML = `
        <div class="skeleton-box" style="width: 80%"></div>
        <div class="skeleton-box" style="width: 90%"></div>
        <div class="skeleton-box" style="width: 45%"></div>
      `;
      responseContent.innerHTML = `
        <div class="skeleton-box" style="width: 75%"></div>
        <div class="skeleton-box" style="width: 85%"></div>
        <div class="skeleton-box" style="width: 90%"></div>
        <div class="skeleton-box" style="width: 60%"></div>
      `;
      
      entitiesSection.hidden = true;
    } else {
      submitBtn.disabled = false;
      submitBtnText.textContent = 'Redact & Ask AI';
      spinner.hidden = true;
    }
  }

  function renderRedactedText(text) {
    if (!text) {
      redactedContent.innerHTML = `<span class="placeholder-text">No data returned.</span>`;
      return;
    }

    // Escape HTML first to prevent XSS
    const escaped = escapeHtml(text);
    
    // Highlight all instances of [PLACEHOLDERS]
    const highlighted = escaped.replace(PLACEHOLDER_REGEX, '<span class="placeholder-highlight">$1</span>');
    
    redactedContent.innerHTML = highlighted;
  }

  function renderFinalResponse(text) {
    if (!text) {
      responseContent.innerHTML = `<span class="placeholder-text">No response received.</span>`;
      return;
    }

    // Set as textContent to safely render the response and prevent XSS (white-space handles wrapping)
    responseContent.textContent = text;
  }

  function renderEntityBadges(entities) {
    badgeList.innerHTML = '';
    
    if (!entities || entities.length === 0) {
      entitiesSection.hidden = false;
      badgeList.innerHTML = `
        <div class="entity-badge" style="background-color: var(--color-success-bg); border-color: rgba(99, 179, 146, 0.2); color: var(--color-success)">
          Clean — No PII Detected
        </div>
      `;
      return;
    }

    // Group entities by type to summarize (e.g. { NAME: 2, SSN: 1 })
    const summary = {};
    entities.forEach(ent => {
      const type = ent.type || 'UNKNOWN';
      summary[type] = (summary[type] || 0) + 1;
    });

    entitiesSection.hidden = false;
    
    // Create badge elements
    Object.entries(summary).forEach(([type, count]) => {
      const badge = document.createElement('div');
      badge.className = 'entity-badge';
      
      // Create text with count tag
      badge.innerHTML = `
        <span>${escapeHtml(type)}</span>
        <span class="badge-count">${count}</span>
      `;
      
      badgeList.appendChild(badge);
    });
  }

  function showStatus(type, message) {
    statusBanner.className = `status-banner ${type}`;
    bannerText.textContent = message;
    statusBanner.hidden = false;
  }

  function hideStatus() {
    statusBanner.hidden = true;
  }

  function resetOutputs() {
    redactedContent.innerHTML = `<span class="placeholder-text">Pending prompt submission...</span>`;
    responseContent.innerHTML = `<span class="placeholder-text">Pending prompt submission...</span>`;
    entitiesSection.hidden = true;
  }

  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  async function updateDashboardData() {
    try {
      await Promise.all([fetchStats(), fetchLogs()]);
    } catch (err) {
      console.error('Failed to update dashboard data:', err);
    }
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) throw new Error('Failed to fetch stats');
      const stats = await res.json();
      if (stats) {
        if (statTotal) statTotal.textContent = stats.total ?? 0;
        if (statRedacted) statRedacted.textContent = stats.by_action?.redact ?? 0;
        if (statBlocked) statBlocked.textContent = stats.by_action?.block ?? 0;
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  }

  async function fetchLogs() {
    try {
      const res = await fetch('/api/logs?limit=50');
      if (!res.ok) throw new Error('Failed to fetch logs');
      const logs = await res.json();
      
      if (!logsTbody) return;
      
      if (!logs || logs.length === 0) {
        logsTbody.innerHTML = `
          <tr>
            <td colspan="6" class="table-empty">No transaction history found. Submit a prompt to generate logs.</td>
          </tr>
        `;
        return;
      }

      logsTbody.innerHTML = logs.map(log => {
        const date = new Date(log.timestamp);
        const formattedDate = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
                             ' ' + date.toLocaleDateString();

        let labelClass = 'tag-clean';
        if (log.label === 'BLOCK') labelClass = 'tag-blocked';
        else if (log.label === 'ACTION_NEEDED') labelClass = 'tag-redacted';
        else if (log.label === 'WARN') labelClass = 'tag-warning';

        let actionText = 'Forwarded';
        if (log.action === 'block') actionText = 'Blocked';
        else if (log.action === 'redact') actionText = 'Redacted';

        const entityPills = log.entities && log.entities.length > 0 
          ? log.entities.map(e => `<code class="log-entity-badge">${escapeHtml(e.type)}</code>`).join(' ')
          : '<span class="log-no-entities">None</span>';

        const snippet = log.redacted_text.length > 80 
          ? escapeHtml(log.redacted_text.slice(0, 80)) + '...'
          : escapeHtml(log.redacted_text);

        return `
          <tr>
            <td class="cell-time">${escapeHtml(formattedDate)}</td>
            <td class="cell-source"><span class="source-pill ${log.source === 'extension' ? 'source-ext' : 'source-dash'}">${escapeHtml(log.source)}</span></td>
            <td><span class="badge-tag ${labelClass}">${escapeHtml(log.label)}</span></td>
            <td class="cell-action font-semibold">${escapeHtml(actionText)}</td>
            <td class="cell-snippet" title="${escapeHtml(log.redacted_text)}">${snippet}</td>
            <td class="cell-entities">${entityPills}</td>
          </tr>
        `;
      }).join('');

    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  }

  if (refreshLogsBtn) {
    refreshLogsBtn.addEventListener('click', updateDashboardData);
  }

  // Load initial stats & logs
  updateDashboardData();
});
