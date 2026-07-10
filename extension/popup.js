// CLOAKWELL Popup UI Controller

document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('protection-toggle');
  const indicatorDot = document.getElementById('indicator-dot');
  const indicatorText = document.getElementById('indicator-text');
  const statsBlockedCount = document.getElementById('stats-blocked-count');
  const openDashboardBtn = document.getElementById('open-dashboard-btn');

  // 1. Load active settings from Chrome storage
  chrome.storage.local.get(['disabled', 'stats_blocked'], (result) => {
    // If 'disabled' is true, protection is OFF (unchecked)
    const isEnabled = !result.disabled;
    toggle.checked = isEnabled;
    updateStatusUI(isEnabled);
    
    // Load blocked stats count
    statsBlockedCount.textContent = result.stats_blocked || 0;
  });

  // 2. Handle protection switch state change
  toggle.addEventListener('change', () => {
    const isEnabled = toggle.checked;
    
    // Store disabled status (disabled = true when checked is false)
    chrome.storage.local.set({ disabled: !isEnabled }, () => {
      updateStatusUI(isEnabled);
    });
  });

  // 3. Open audit dashboard link
  openDashboardBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: 'http://localhost:8000/' });
  });

  // Helper: Update Popup header status indicator
  function updateStatusUI(isEnabled) {
    if (isEnabled) {
      indicatorDot.className = 'dot dot-active';
      indicatorText.textContent = 'Active';
      indicatorText.style.color = '#63b392';
    } else {
      indicatorDot.className = 'dot dot-inactive';
      indicatorText.textContent = 'Shield Paused';
      indicatorText.style.color = '#5e6d82';
    }
  }
});
