import React, { useState } from "react";
import { Search, Bot, ArrowLeft } from "lucide-react";

type CarrierData = {
  card: {
    status: string;
    status_color: string;
    safety_score: number;
    issues: string[];
    reviews: string[];
  };
  carrier_summary?: any;
  safety_overview?: any;
  insurance_compliance?: any;
  authority_status?: any;
  recommendation?: any;
  scores?: any;
};

export default function App() {
  const [dotNumber, setDotNumber] = useState<string>("");
  const [carrierData, setCarrierData] = useState<CarrierData | null>(null);
  const [question, setQuestion] = useState<string>("");
  const [answers, setAnswers] = useState<{ q: string; a: string }[]>([]);
  const [expanded, setExpanded] = useState(false);

  const handleVetCarrier = async () => {
    try {
      const res = await fetch("http://localhost:8000/fmsca/dot_parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dot_number: dotNumber,
          tenant_id: "demo-tenant",
          user_id: "demo-user",
          mock: false,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to fetch carrier data");
      }

      const data = await res.json();
      setCarrierData(data);
    } catch (err) {
      console.error(err);
      alert("Error fetching carrier data");
    }
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
      {/* Header */}
      <div className="header-row">
        <h1 className="header-title">Auto Vetting</h1>
        <label className="switch">
          <input type="checkbox" />
          <span className="slider"></span>
        </label>
      </div>

      {/* DOT Input Section */}
      {!expanded && (
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
      )}

      {/* Carrier Report Section */}
      {carrierData && !expanded && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Carrier Report</h2>
            <button className="close-btn" onClick={() => setCarrierData(null)}>
              ×
            </button>
          </div>
          <p>
            <b>Status:</b>{" "}
            <span
              className="status-dot"
              style={{ backgroundColor: carrierData.card.status_color }}
            ></span>
            {carrierData.card.status}
          </p>
          <p>
            <b>Safety Score:</b> {carrierData.card.safety_score}
          </p>
          <p>
            <b>Issues:</b>{" "}
            {carrierData.card.issues.length
              ? carrierData.card.issues.join(", ")
              : "None"}
          </p>
          <p>
            <b>Reviews:</b>
          </p>
          <ul>
            {carrierData.card.reviews.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>

          <button
            className="link-button"
            onClick={() => setExpanded(true)}
          >
            Show More
          </button>
        </div>
      )}

      {/* Expanded Full-Screen View */}
      {carrierData && expanded && (
        <div className="overlay">
          <div className="overlay-header">
            <button className="back-btn" onClick={() => setExpanded(false)}>
              <ArrowLeft /> Show Less
            </button>
          </div>
          <div className="overlay-content">
            <h2>Carrier Summary</h2>
            <pre>{JSON.stringify(carrierData.carrier_summary, null, 2)}</pre>

            <h2>Safety Overview</h2>
            <pre>{JSON.stringify(carrierData.safety_overview, null, 2)}</pre>

            <h2>Insurance Compliance</h2>
            <pre>{JSON.stringify(carrierData.insurance_compliance, null, 2)}</pre>

            <h2>Authority Status</h2>
            <pre>{JSON.stringify(carrierData.authority_status, null, 2)}</pre>

            <h2>Recommendation</h2>
            <pre>{JSON.stringify(carrierData.recommendation, null, 2)}</pre>

            <h2>Scores</h2>
            <pre>{JSON.stringify(carrierData.scores, null, 2)}</pre>
          </div>
        </div>
      )}

      {/* Q&A Bot */}
      {!expanded && (
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
      )}
    </div>
  );
}
