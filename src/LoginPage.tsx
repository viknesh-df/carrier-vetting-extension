import React, { useEffect, useState } from "react";
import "./login.css";

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // Check chrome.storage, not localStorage
    chrome.storage.local.get(["authToken"], (data) => {
      if (data.authToken) {
        onLogin();
      }
      setChecking(false);
    });

    // Listen for updates from content.js → background.js
    const listener = (changes: { [key: string]: chrome.storage.StorageChange }) => {
      if (changes.authToken?.newValue) {
        onLogin();
      } else if (changes.authToken?.oldValue && !changes.authToken?.newValue) {
        // logged out
        setChecking(false);
      }
    };

    chrome.storage.onChanged.addListener(listener);

    return () => {
      chrome.storage.onChanged.removeListener(listener);
    };
  }, [onLogin]);

  const handleLogin = () => {
    // Open Pangents login page in a new tab
    chrome.tabs.create({ url: "https://pangents.deepfrog.ai/auth" });
  };

  if (checking) {
    return (
      <div className="login-container">
        <p>Checking login status...</p>
      </div>
    );
  }

  return (
    <div className="login-container">
      <h1 className="login-title">Login to use Carrier Vetting Agent</h1>
      <button className="login-button" onClick={handleLogin}>
        Login
      </button>
    </div>
  );
}
