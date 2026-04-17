 
const BASE_URL = "/api"; // Vite proxy handles forwarding to http://localhost:8000
 
async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}
 
export const api = {
  /** Identify a verse from text */
  identify(text, version = "KJV") {
    return request("/identify/", {
      method: "POST",
      body: JSON.stringify({ text, version }),
    });
  },
 
  /** Transcribe audio blob to text */
  async transcribe(audioBlob) {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    const res = await fetch(`${BASE_URL}/transcribe/`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: "Transcription failed" }));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return res.json();
  },
 
  /** Get verse + surrounding context */
  getVerse(book, chapter, verse, version = "KJV", context = 3) {
    const params = new URLSearchParams({ book, chapter, verse, version, context });
    return request(`/verse/?${params}`);
  },
 
  /** Get full chapter */
  getChapter(book, chapter, version = "KJV") {
    const params = new URLSearchParams({ book, chapter, version });
    return request(`/chapter/?${params}`);
  },
 
  /** Saved verses */
  getSaved() {
    return request("/saved/");
  },
 
  saveVerse(verseId, note = "") {
    return request("/saved/", {
      method: "POST",
      body: JSON.stringify({ verse_id: verseId, note }),
    });
  },
 
  deleteSaved(id) {
    return request(`/saved/${id}/`, { method: "DELETE" });
  },
 
  /** Bible versions */
  getVersions() {
    return request("/versions/");
  },
};