// CLOAKWELL Background Service Worker
// Proxies classification requests to local backend to handle CORS

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'classify') {
    fetch('http://localhost:8000/api/classify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: request.text,
        source: 'extension',
        session_id: request.sessionId || 'default'
      })
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      sendResponse({ success: true, data: data });
    })
    .catch(error => {
      console.error('Classification request failed:', error);
      sendResponse({ success: false, error: error.message });
    });
    
    return true; // Keep communication channel open for asynchronous reply
  }
});
