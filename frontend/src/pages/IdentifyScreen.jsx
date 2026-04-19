import { useState, useRef, useCallback } from "react";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import { api } from "../services/api";

// ── Web Speech API (browser built-in, no API key needed) ────────────────── //
function useBrowserSpeech() {
  const recognitionRef = useRef(null);

  const listen = useCallback(() => {
    return new Promise((resolve, reject) => {
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

      if (!SpeechRecognition) {
        reject(new Error("Browser speech not supported. Use text mode."));
        return;
      }

      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onresult = (e) => {
        const text = e.results[0][0].transcript;
        resolve(text);
      };
      recognition.onerror = (e) => {
        reject(new Error(e.error === "not-allowed"
          ? "Microphone access denied. Allow mic in browser settings."
          : `Speech error: ${e.error}`));
      };
      recognition.onend = () => {};
      recognition.start();
    });
  }, []);

  return { listen };
}

export default function IdentifyScreen({ version, onVersionChange, onResult }) {
  const [textInput, setTextInput] = useState("");
  const [mode, setMode] = useState("voice"); // voice | text
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState("");
  const recorder = useVoiceRecorder();
  const browser = useBrowserSpeech();

  const handleMicPress = async () => {
    setError(null);

    // ── If already recording (Whisper mode), stop it ── //
    if (recorder.isRecording) {
      try {
        const blob = await recorder.stop();
        setLoading(true);
        setTranscript("");
        const { text, warning } = await api.transcribe(blob);
        if (warning) {
          // Whisper not configured — fall back to browser speech silently
          setLoading(false);
          await handleBrowserSpeech();
          return;
        }
        if (!text) {
          setError("Could not hear anything. Please try again.");
          setLoading(false);
          return;
        }
        await identifyText(text);
      } catch (err) {
        setLoading(false);
        setError(err.message);
      }
      return;
    }

    // ── Try browser speech first (no API key needed) ── //
    await handleBrowserSpeech();
  };

  const handleBrowserSpeech = async () => {
    setListening(true);
    setError(null);
    try {
      const text = await browser.listen();
      setListening(false);
      if (!text) {
        setError("Could not hear anything. Please try again.");
        return;
      }
      setTranscript(text);
      await identifyText(text);
    } catch (err) {
      setListening(false);
      // Browser speech failed — fall back to Whisper recorder
      if (err.message.includes("not supported")) {
        recorder.start();
      } else {
        setError(err.message);
      }
    }
  };

  const identifyText = async (text) => {
    setLoading(true);
    try {
      const result = await api.identify(text, version);
      setLoading(false);
      if (result.found) {
        onResult(result);
      } else {
        setError(`No match found for "${text}". Try speaking more of the verse.`);
      }
    } catch (err) {
      setLoading(false);
      setError(err.message);
    }
  };

  const handleTextSearch = async (e) => {
    e.preventDefault();
    if (!textInput.trim()) return;

    setError(null);
    setLoading(true);
    try {
      const result = await api.identify(textInput, version);
      setLoading(false);
      if (result.found) {
        onResult(result);
      } else {
        setError(`No match found for "${textInput}". Try typing more of the verse.`);
      }
    } catch (err) {
      setLoading(false);
      setError(err.message);
    }
  };

  const micState = (recorder.isRecording || listening) ? "recording" : loading ? "loading" : "idle";

  return (
    <div className="identify-screen">
      <div className="app-header">
        <h1 className="app-title">VerseFind</h1>
        <p className="app-subtitle">Speak or type a Bible verse to identify it</p>
      </div>

      {/* Version selector */}
      <div className="version-select-wrap">
        <select
          className="version-select"
          value={version}
          onChange={(e) => onVersionChange(e.target.value)}
        >
          <option value="KJV">KJV</option>
          <option value="NIV">NIV</option>
          <option value="ESV">ESV</option>
          <option value="NKJV">NKJV</option>
        </select>
      </div>

      {/* Mode tabs */}
      <div className="mode-tabs">
        <button
          className={`mode-tab ${mode === "voice" ? "active" : ""}`}
          onClick={() => setMode("voice")}
        >
          Voice
        </button>
        <button
          className={`mode-tab ${mode === "text" ? "active" : ""}`}
          onClick={() => setMode("text")}
        >
          Text
        </button>
      </div>

      {mode === "voice" && (
        <div className="voice-area">
          <div className="mic-wrap">
            {recorder.isRecording && (
              <>
                <div className="pulse-ring ring-1" />
                <div className="pulse-ring ring-2" />
              </>
            )}
            <button
              className={`mic-btn ${micState}`}
              onClick={handleMicPress}
              disabled={loading || recorder.state === "requesting" || recorder.state === "processing"}
              style={listening ? {background: "var(--accent)", color: "white"} : {}}
              aria-label={recorder.isRecording ? "Stop recording" : "Start recording"}
            >
              {loading ? (
                <svg className="spinner" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
              ) : (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <rect x="9" y="2" width="6" height="11" rx="3"/>
                  <path d="M5 10a7 7 0 0 0 14 0"/>
                  <line x1="12" y1="19" x2="12" y2="22"/>
                  <line x1="8" y1="22" x2="16" y2="22"/>
                </svg>
              )}
            </button>
          </div>

          <p className="mic-label">
            {recorder.state === "requesting" && "Requesting microphone…"}
            {(recorder.isRecording || listening) && "Listening — speak now…"}
            {recorder.state === "processing" && "Processing audio…"}
            {loading && transcript && `Matching: "${transcript}"`}
            {loading && !transcript && "Identifying verse…"}
            {!recorder.isRecording && !listening && !loading && recorder.state === "idle" && "Tap to identify verse"}
          </p>

          {recorder.error && <p className="error-msg">{recorder.error}</p>}
        </div>
      )}

      {mode === "text" && (
        <form className="text-area" onSubmit={handleTextSearch}>
          <textarea
            className="verse-input"
            placeholder="Type part of a verse… e.g. For God so loved the world"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            rows={4}
            autoFocus
          />
          <button
            type="submit"
            className="search-btn"
            disabled={loading || !textInput.trim()}
          >
            {loading ? "Searching…" : "Find Verse"}
          </button>
        </form>
      )}

      {error && (
        <div className="error-card">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error}
        </div>
      )}

      <div className="tips">
        <p className="tip"> You can quote just a few words — e.g. "the Lord is my shepherd"</p>
      </div>
    </div>
  );
}