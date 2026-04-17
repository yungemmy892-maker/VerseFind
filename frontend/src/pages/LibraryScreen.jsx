import { useState, useEffect } from "react";
import { api } from "../services/api";
 
export default function LibraryScreen({ onOpenVerse }) {
  const [saved, setSaved] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
 
  useEffect(() => {
    api.getSaved()
      .then(setSaved)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);
 
  const handleDelete = async (id) => {
    try {
      await api.deleteSaved(id);
      setSaved((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      alert(err.message);
    }
  };
 
  if (loading) return <div className="library-screen loading">Loading your verses…</div>;
 
  return (
    <div className="library-screen">
      <h2 className="library-title">My Library</h2>
 
      {error && <p className="error-msg">{error}</p>}
 
      {saved.length === 0 ? (
        <div className="empty-library">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="1.5" strokeLinecap="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          <p>No saved verses yet.</p>
          <p className="empty-hint">Tap "Find" to identify and save verses.</p>
        </div>
      ) : (
        <div className="saved-list">
          {saved.map((s) => (
            <div key={s.id} className="saved-item">
              <div
                className="saved-item-content"
                onClick={() => onOpenVerse({ top_match: s.verse, results: [s.verse], query: "", found: true })}
                role="button"
                tabIndex={0}
              >
                <div className="saved-ref-row">
                  <span className="saved-ref">{s.verse.reference}</span>
                  <span className="saved-version">{s.verse.version}</span>
                </div>
                <p className="saved-text">{s.verse.text.slice(0, 100)}…</p>
                <p className="saved-date">{new Date(s.saved_at).toLocaleDateString()}</p>
              </div>
              <button
                className="delete-btn"
                onClick={() => handleDelete(s.id)}
                aria-label="Remove"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6"/>
                  <path d="M14 11v6"/>
                  <path d="M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}