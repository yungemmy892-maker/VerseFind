import { useState, useRef, useCallback } from "react";
 
/**
 * useVoiceRecorder
 * ----------------
 * Records audio via the browser MediaRecorder API and returns the blob.
 * Uses audio/webm;codecs=opus for best Whisper compatibility.
 */
export function useVoiceRecorder() {
  const [state, setState] = useState("idle"); // idle | requesting | recording | processing | error
  const [error, setError] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
 
  const start = useCallback(async () => {
    setError(null);
    setState("requesting");
 
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
 
      streamRef.current = stream;
      chunksRef.current = [];
 
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";
 
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
 
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
 
      recorder.start(250); // collect chunks every 250ms
      setState("recording");
    } catch (err) {
      setError(
        err.name === "NotAllowedError"
          ? "Microphone access denied. Please allow mic access and try again."
          : `Could not start recording: ${err.message}`
      );
      setState("error");
    }
  }, []);
 
  const stop = useCallback(() => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        reject(new Error("No active recording"));
        return;
      }
 
      setState("processing");
 
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        streamRef.current?.getTracks().forEach((t) => t.stop());
        setState("idle");
        resolve(blob);
      };
 
      recorder.onerror = (e) => {
        setState("error");
        setError(`Recording error: ${e.error?.message}`);
        reject(e.error);
      };
 
      recorder.stop();
    });
  }, []);
 
  const cancel = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    chunksRef.current = [];
    setState("idle");
    setError(null);
  }, []);
 
  return {
    state,       // "idle" | "requesting" | "recording" | "processing" | "error"
    error,
    isRecording: state === "recording",
    isProcessing: state === "processing",
    start,
    stop,
    cancel,
  };
}