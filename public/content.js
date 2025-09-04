(function () {
  let lastToken = null;

  function syncAuth() {
    const token = localStorage.getItem("authToken");
    const email = localStorage.getItem("userEmail");

    if (token !== lastToken) {
      lastToken = token;
      chrome.runtime.sendMessage({
        type: "AUTH_SYNC",
        token,
        email
      });
    }
  }

  // Initial sync
  syncAuth();

  // Poll every 2s
  setInterval(syncAuth, 2000);
})();
