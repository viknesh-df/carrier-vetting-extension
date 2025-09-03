import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import LoginPage from "./LoginPage";
import "./index.css";

function Root() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    // Check on startup
    chrome.storage.local.get(["authToken"], (data) => {
      if (data.authToken) setLoggedIn(true);
    });

    // Listen for changes
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.authToken?.newValue) {
        setLoggedIn(true);
      } else if (changes.authToken?.oldValue && !changes.authToken?.newValue) {
        setLoggedIn(false);
      }
    });
  }, []);

  return loggedIn ? <App /> : <LoginPage onLogin={() => setLoggedIn(true)} />;
}


ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
