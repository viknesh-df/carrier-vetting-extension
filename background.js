chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "AUTH_SYNC") {
    if (message.token) {
      chrome.storage.local.set({
        authToken: message.token,
        userEmail: message.email,
      });
    } else {
      chrome.storage.local.remove(["authToken", "userEmail"]);
    }
  }
});
