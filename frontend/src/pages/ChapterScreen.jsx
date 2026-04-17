import { useState, useEffect } from "react";
import { api } from "../services/api";

export default function ChapterScreen({ book, chapter, version, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentChapter, setCurrentChapter] = useState(chapter);
 
  useEffect(() => {
    setLoading(true);
    api.getChapter(book, currentChapter, version)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [book, currentChapter, version]);
 
  return (
    <div className="chapter-screen">
      <div className="chapter-header">
        <button className="back-btn" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          Back
        </button>
        <span className="chapter-title">{book} {currentChapter}</span>
        <span className="chapter-version">{version}</span>
      </div>
 
      <div className="chapter-nav">
        <button
          className="chapter-nav-btn"
          disabled={currentChapter <= 1}
          onClick={() => setCurrentChapter((c) => c - 1)}
        >← Prev</button>
        <button
          className="chapter-nav-btn"
          onClick={() => setCurrentChapter((c) => c + 1)}
        >Next →</button>
      </div>
 
      {loading && <div className="loading-text">Loading chapter…</div>}
      {error && <p className="error-msg">{error}</p>}
 
      {data && !loading && (
        <div className="verse-list">
          {data.verses.map((v) => (
            <div
              key={v.verse_number}
              className={`chapter-verse ${v.verse_number === chapter ? "highlight" : ""}`}
              id={`v${v.verse_number}`}
            >
              <sup className="verse-sup">{v.verse_number}</sup>
              {v.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}