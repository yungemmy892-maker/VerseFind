import { useState, useCallback } from "react";
import IdentifyScreen from "./pages/IdentifyScreen";
import ResultScreen from "./pages/ResultScreen";
import LibraryScreen from "./pages/LibraryScreen";
import ChapterScreen from "./pages/ChapterScreen";
import "./App.css";

export default function App() {
  const [screen, setScreen] = useState("identify"); // identify | result | library | chapter
  const [result, setResult] = useState(null);
  const [chapterData, setChapterData] = useState(null);
  const [version, setVersion] = useState("KJV");

  const handleResult = useCallback((data) => {
    setResult(data);
    setScreen("result");
  }, []);

  const handleOpenChapter = useCallback((book, chapter) => {
    setChapterData({ book, chapter });
    setScreen("chapter");
  }, []);

  const handleBack = useCallback(() => {
    setScreen((prev) => {
      if (prev === "chapter") return "result";
      return "identify";
    });
  }, []);

  return (
    <div className="app">
      <nav className="nav">
        <button
          className={`nav-btn ${screen === "identify" ? "active" : ""}`}
          onClick={() => setScreen("identify")}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          Find
        </button>
        <button
          className={`nav-btn ${screen === "library" ? "active" : ""}`}
          onClick={() => setScreen("library")}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          Library
        </button>
      </nav>

      <main className="main">
        {screen === "identify" && (
          <IdentifyScreen
            version={version}
            onVersionChange={setVersion}
            onResult={handleResult}
          />
        )}
        {screen === "result" && result && (
          <ResultScreen
            result={result}
            onBack={handleBack}
            onOpenChapter={handleOpenChapter}
            onNewSearch={() => setScreen("identify")}
          />
        )}
        {screen === "library" && (
          <LibraryScreen onOpenVerse={(r) => { setResult(r); setScreen("result"); }} />
        )}
        {screen === "chapter" && chapterData && (
          <ChapterScreen
            book={chapterData.book}
            chapter={chapterData.chapter}
            version={version}
            onBack={handleBack}
          />
        )}
      </main>
    </div>
  );
}