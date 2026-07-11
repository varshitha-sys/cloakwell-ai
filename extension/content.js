// CLOAKWELL Prompt Interceptor Content Script
// Automatically runs on ChatGPT, Claude, and Gemini

(function() {
  let isChecking = false;
  let bypassNext = false;

  // CSS Styles for injected modals
  const MODAL_STYLES = `
    .cloakwell-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background-color: rgba(7, 12, 22, 0.75);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999999999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    .cloakwell-modal {
      background-color: #0d1627;
      border: 1px solid rgba(114, 164, 194, 0.3);
      border-radius: 12px;
      padding: 24px;
      width: 500px;
      max-width: 90%;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
      color: #f0f4f8;
      animation: cloakwell-scale-up 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    
    .cloakwell-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      border-bottom: 1px solid rgba(114, 164, 194, 0.15);
      padding-bottom: 12px;
    }
    
    .cloakwell-icon {
      width: 28px;
      height: 28px;
      color: #72a4c2;
    }
    
    .cloakwell-title {
      font-size: 18px;
      font-weight: 700;
      color: #f0f4f8;
      margin: 0;
      letter-spacing: -0.02em;
    }
    
    .cloakwell-body {
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 20px;
      color: #9aa8b9;
    }
    
    .cloakwell-preview-box {
      background-color: #050a11;
      border: 1px solid rgba(114, 164, 194, 0.15);
      border-radius: 6px;
      padding: 12px;
      font-family: "JetBrains Mono", monospace;
      font-size: 13px;
      max-height: 150px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
      margin: 12px 0;
      color: #e2f0fc;
    }

    .cloakwell-highlight {
      background: rgba(114, 164, 194, 0.15);
      border: 1px solid rgba(114, 164, 194, 0.4);
      color: #72a4c2;
      padding: 0 4px;
      border-radius: 4px;
      font-weight: 600;
    }
    
    .cloakwell-actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }
    
    .cloakwell-btn {
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
    }
    
    .cloakwell-btn-primary {
      background: linear-gradient(135deg, #4c86ac 0%, #134670 100%);
      color: #f0f4f8;
      box-shadow: 0 4px 12px rgba(19, 70, 112, 0.3);
    }
    
    .cloakwell-btn-primary:hover {
      filter: brightness(1.1);
      transform: translateY(-1px);
    }
    
    .cloakwell-btn-secondary {
      background-color: transparent;
      border: 1px solid rgba(114, 164, 194, 0.25);
      color: #9aa8b9;
    }
    
    .cloakwell-btn-secondary:hover {
      background-color: rgba(114, 164, 194, 0.1);
      color: #f0f4f8;
    }
    
    @keyframes cloakwell-scale-up {
      from {
        opacity: 0;
        transform: scale(0.95);
      }
      to {
        opacity: 1;
        transform: scale(1);
      }
    }
  `;

  // Inject Styles
  const styleEl = document.createElement('style');
  styleEl.textContent = MODAL_STYLES;
  document.head.appendChild(styleEl);

  // Helper: Get text from textarea or contenteditable element
  function getElementText(el) {
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      return el.value;
    }
    return el.innerText || el.textContent;
  }

  // Helper: Set text on textarea or contenteditable element
  function setElementText(el, text) {
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      el.value = text;
    } else {
      el.innerText = text;
    }
    // Dispatch input/change events to alert frameworks (React/Vue)
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Helper: Locate input elements on page
  function findInputField() {
    // Try common input fields on ChatGPT, Claude, and Gemini
    return document.querySelector('#prompt-textarea, #textarea, [contenteditable="true"], textarea');
  }

  // Helper: Detect send buttons on chat interfaces
  function isSendButton(button) {
    if (!button) return false;
    const label = (button.getAttribute('aria-label') || button.getAttribute('title') || '').toLowerCase();
    const isSvgIcon = button.querySelector('svg');
    const isTestId = button.getAttribute('data-testid') === 'send-button';
    
    return label.includes('send') || label.includes('submit') || isSvgIcon || isTestId;
  }

  // Helper: Programmatically trigger prompt submission
  function triggerSubmit(inputElement) {
    bypassNext = true;
    
    // Find send button and click it
    const buttons = document.querySelectorAll('button, [role="button"]');
    for (const btn of buttons) {
      if (isSendButton(btn)) {
        btn.click();
        return;
      }
    }

    // Fallback: Dispatch Enter event
    const enterEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true,
      cancelable: true
    });
    inputElement.dispatchEvent(enterEvent);
  }

  // Intercept Keydown Event
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      const target = event.target;
      const editable = target.closest('[contenteditable="true"]');
      
      if (target.tagName === 'TEXTAREA' || editable) {
        if (bypassNext) {
          return;
        }

        // Intercept and prevent ChatGPT from receiving the enter key
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        if (isChecking) return;

        const inputEl = editable || target;
        const text = getElementText(inputEl).trim();
        if (!text) return;

        checkPrompt(text, inputEl);
      }
    }
  }, true);

  // Intercept Click/Mousedown Event
  function handleTrigger(event) {
    const button = event.target.closest('button, [role="button"]');
    if (button && isSendButton(button)) {
      if (bypassNext) {
        // Let it pass through to ChatGPT
        return;
      }
      
      // Stop event from reaching ChatGPT
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      if (isChecking) return;
      
      const input = findInputField();
      if (input) {
        const text = getElementText(input).trim();
        if (!text) return;

        checkPrompt(text, input);
      }
    }
  }

  document.addEventListener('click', handleTrigger, true);
  document.addEventListener('mousedown', handleTrigger, true);

  // Call background.js to perform local classification check
  function checkPrompt(text, inputElement) {
    isChecking = true;
    
    // Fetch toggle state from chrome storage
    chrome.storage.local.get(['disabled'], (result) => {
      if (result.disabled) {
        isChecking = false;
        bypassNext = true;
        triggerSubmit(inputElement);
        return;
      }

      chrome.runtime.sendMessage({ action: 'classify', text: text }, (response) => {
        isChecking = false;
        
        if (response && response.success) {
          const verdict = response.data;
          handleVerdict(verdict, text, inputElement);
        } else {
          // If connection fails, bypass to avoid breaking the chat app
          console.warn('CLOAKWELL classification offline, bypassing check.');
          bypassNext = true;
          triggerSubmit(inputElement);
        }
      });
    });
  }

  // Handle classification verdict
  function handleVerdict(verdict, originalText, inputElement) {
    const label = verdict.label || 'INFO';
    
    if (label === 'BLOCK' || label === 'ACTION_NEEDED' || label === 'WARN') {
      showBlockModal(verdict, originalText, inputElement);
    } else {
      // INFO -> proceed untouched
      bypassNext = true;
      triggerSubmit(inputElement);
    }
  }

  // Modal 1: Blocked/Sensitive (Answered Locally)
  function showBlockModal(verdict, originalText, inputElement) {
    chrome.storage.local.get(['stats_blocked'], (data) => {
      const current = data.stats_blocked || 0;
      chrome.storage.local.set({ stats_blocked: current + 1 });
    });

    const overlay = document.createElement('div');
    overlay.className = 'cloakwell-overlay';
    
    const modal = document.createElement('div');
    modal.className = 'cloakwell-modal';
    
    modal.innerHTML = `
      <div class="cloakwell-header">
        <svg class="cloakwell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        <h2 class="cloakwell-title">CLOAKWELL Safety Intercept</h2>
      </div>
      <div class="cloakwell-body">
        <p>This prompt contains sensitive data. To comply with organization policy, this request has been blocked from leaving your network and is being answered locally by your **private AMD Instinct GPU**.</p>
        <div class="cloakwell-preview-box" id="cloakwell-local-response">
          🔄 Contacting private local model (Google Gemma 2 on AMD Instinct GPU)...
        </div>
      </div>
      <div class="cloakwell-actions">
        <button class="cloakwell-btn cloakwell-btn-primary" id="cloakwell-close-btn" disabled>Waiting for GPU...</button>
      </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    const closeBtn = document.getElementById('cloakwell-close-btn');
    closeBtn.addEventListener('click', () => {
      overlay.remove();
    });

    // Query the local model via background script
    chrome.runtime.sendMessage({ action: 'redact-and-ask', text: originalText }, (response) => {
      const responseBox = document.getElementById('cloakwell-local-response');
      if (response && response.success) {
        // Strip out the custom routing header since we are already inside the local intercept UI
        let cleanResponse = response.data.final_response || '';
        cleanResponse = cleanResponse.replace(/🤖 \*\*\[Secure Local Mode:.*\]\*\*\n\n/, '');
        responseBox.innerText = cleanResponse;
      } else {
        responseBox.innerText = "❌ Local inference failed or proxy is offline.";
      }
      closeBtn.innerText = "Close";
      closeBtn.removeAttribute('disabled');
    });
  }
})();
