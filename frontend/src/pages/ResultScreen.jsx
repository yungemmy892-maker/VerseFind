import { useState } from "react";
import { api } from "../services/api";

export default function ResultScreen({ result, onBack, onOpenChapter, onNewSearch }) {
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [activeTab, setActiveTab] = useState("match"); // match | alternatives

  const top = result.top_match;
  const alternatives = result.results.slice(1);

  const handleSave = async () => {
    try {
      // Pass id if present (direct verse fetch), else pass lookup fields
      // (identify endpoint returns book/chapter/verse_number/version)
      await api.saveVerse({
        verse_id:     top.id          || null,
        book:         top.book        || null,
        chapter:      top.chapter     || null,
        verse_number: top.verse_number || null,
        version:      top.version     || "KJV",
      });
      setSaved(true);
    } catch (err) {
      setSaveError(err.message);
    }
  };

  const handleShare = () => {
    const text = `${top.text}\n— ${top.reference} (${top.version})`;
    if (navigator.share) {
      navigator.share({ title: top.reference, text });
    } else {
      navigator.clipboard.writeText(text).then(() => alert("Copied to clipboard!"));
    }
  };

  if (!top) {
    return (
      <div className="result-screen">
        <button className="back-btn" onClick={onBack}>← Back</button>
        <p className="no-result">No match found. Try again with more of the verse.</p>
        <button className="search-btn" onClick={onNewSearch}>New Search</button>
      </div>
    );
  }

  // Highlight matching words in verse text
  function highlightText(text, query) {
    if (!query) return text;
    const words = query.toLowerCase().split(/\s+/).filter(w => w.length > 3);
    let result = text;
    words.forEach(word => {
      const regex = new RegExp(`(${word})`, "gi");
      result = result.replace(regex, '<mark>$1</mark>');
    });
    return result;
  }

  return (
    <div className="result-screen">
      <div className="result-header">
        <button className="back-btn" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          Back
        </button>

        <div className="confidence-badge" data-level={top.score >= 80 ? "high" : top.score >= 60 ? "mid" : "low"}>
          {top.score}% match
        </div>
      </div>

      {/* Main verse card */}
      <div className="verse-card">
        <div className="verse-ref-row">
          <span className="verse-ref">{top.reference}</span>
          <span className="verse-version">{top.version}</span>
        </div>

        <p
          className="verse-text"
          dangerouslySetInnerHTML={{
            __html: `"${highlightText(top.text, result.query)}"`,
          }}
        />

        <div className="testament-tag">
          {top.testament === "NT" ? "New Testament" : "Old Testament"}
        </div>
      </div>

      {/* Action buttons */}
      <div className="action-row">
        <button
          className="action-btn"
          onClick={() => onOpenChapter(top.book, top.chapter)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
          Full chapter
        </button>

        <button className="action-btn" onClick={handleShare}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
          </svg>
          Share
        </button>

        <button
          className={`action-btn ${saved ? "saved" : ""}`}
          onClick={handleSave}
          disabled={saved}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill={saved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
          </svg>
          {saved ? "Saved!" : "Save"}
        </button>
      </div>

      {saveError && <p className="error-msg">{saveError}</p>}

      {/* Alternatives */}
      {alternatives.length > 0 && (
        <div className="alternatives">
          <p className="alt-label">Other possible matches</p>
          {alternatives.map((alt, i) => (
            <div key={i} className="alt-row">
              <span className="alt-ref">{alt.reference}</span>
              <span className="alt-score">{alt.score}%</span>
              <p className="alt-text">{alt.text.slice(0, 80)}…</p>
            </div>
          ))}
        </div>
      )}

      <button className="new-search-btn" onClick={onNewSearch}>
        Search another verse
      </button>
    </div>
  );
}