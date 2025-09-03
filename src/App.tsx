import React, { useState } from "react";
import { Search, Bot } from "lucide-react";

type CarrierData = {
  status: string;
  safety_score: number;
  issues: string[];
  reviews: string[];
};

export default function App() {
  const [dotNumber, setDotNumber] = useState<string>("");
  const [carrierData, setCarrierData] = useState<CarrierData | null>(null);
  const [question, setQuestion] = useState<string>("");
  const [answers, setAnswers] = useState<{ q: string; a: string }[]>([]);

  const handleVetCarrier = () => {
    // Mocked response
    setCarrierData({
      status: "approved",
      safety_score: 90,
      issues: [],
      reviews: ["On-time deliveries", "Good communication"],
    });
  };

  const handleScrape = () => {
    alert("Scraping carrier info from page...");
  };

  const handleAsk = () => {
    if (!question.trim()) return;
    setAnswers([...answers, { q: question, a: "(Mock answer for now)" }]);
    setQuestion("");
  };

  return (
    <div className="app-container">
      {/* DOT Input Section */}
      <div className="header-row">
        <h1 className="header-title">Auto Vetting</h1>
        <label className="switch">
          <input type="checkbox" />
          <span className="slider"></span>
        </label>
      </div>
      <div className="card">
        <h2 className="card-title">Carrier Vetting</h2>
        <input
          className="input"
          placeholder="Enter DOT number"
          value={dotNumber}
          onChange={(e) => setDotNumber(e.target.value)}
        />
        <div className="button-row">
          <button className="button" onClick={handleVetCarrier}>
            Vet Carrier
          </button>
          <button className="button secondary" onClick={handleScrape}>
            <Search className="icon" /> Scrape Page
          </button>
        </div>
      </div>

      {/* Carrier Report Section */}
      {carrierData && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Carrier Report</h2>
            <button className="close-btn" onClick={() => setCarrierData(null)}>×</button>
          </div>
          <p><b>Status:</b> 
            <span 
              className="status-dot" 
              style={{ backgroundColor: carrierData.status === "approved" ? "#00C853" : "#D32F2F" }}
            ></span> 
            {carrierData.status}
          </p>
          <p><b>Safety Score:</b> {carrierData.safety_score}</p>
          <p><b>Issues:</b> {carrierData.issues.length ? carrierData.issues.join(", ") : "None"}</p>
          <p><b>Reviews:</b></p>
          <ul>
            {carrierData.reviews.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Q&A Bot */}
      <div className="card">
        <h2 className="card-title">
          <Bot className="icon" /> Ask Vetting Assistant
        </h2>
        <textarea
          className="textarea"
          placeholder="Ask a question about the carrier..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="button primary" onClick={handleAsk}>
          Ask
        </button>

        <div className="qa-section">
          {answers.map((qa, i) => (
            <div key={i} className="qa-item">
              <p>
                <b>Q:</b> {qa.q}
              </p>
              <p>
                <b>A:</b> {qa.a}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
