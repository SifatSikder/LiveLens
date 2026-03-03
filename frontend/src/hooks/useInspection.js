/**
 * useInspection — Core hook for LiveLens bidi-streaming session.
 *
 * Manages:
 * - WebSocket connection to /ws/{userId}/{sessionId}
 * - Audio capture (16-bit PCM, 16kHz) and playback (24kHz)
 * - Camera frame capture (JPEG, 1 FPS)
 * - Event parsing from ADK runner
 */
import { useState, useRef, useCallback, useEffect } from 'react';

const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;

export function useInspection() {
  const [connected, setConnected] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [events, setEvents] = useState([]);
  const [findings, setFindings] = useState([]);
  const [transcript, setTranscript] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [sessionError, setSessionError] = useState(null);
  // Task 3.1: report generation state exposed to InspectionView
  const [reportUrl, setReportUrl] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState(sessionIdRef.current);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const playContextRef = useRef(null);
  const videoRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const sessionIdRef = useRef('session-' + Math.random().toString(36).substring(2, 9));
  const activeSourcesRef = useRef([]);
  const agentSpeakingTimerRef = useRef(null);

  // Connect WebSocket
  const connect = useCallback(() => {
    const userId = 'inspector-1';
    const sessionId = sessionIdRef.current;
    const url = `${WS_BASE}/ws/${userId}/${sessionId}`;

    console.log(`[WS] Connecting to ${url}`);
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('[WS] Connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Special control message: backend signals a Gemini API error
        if (data?.type === 'session_error') {
          console.error('[WS] Session error from backend:', data);
          setSessionError({ code: data.code, message: data.message });
          return;
        }
        handleEvent(data);
      } catch (e) {
        console.warn('[WS] Failed to parse event:', e);
      }
    };

    ws.onclose = (e) => {
      console.log(`[WS] Closed: code=${e.code}`);
      setConnected(false);
      setInspecting(false);
      // Unexpected close (not triggered by user disconnect) — surface an error
      if (e.code !== 1000 && e.code !== 1001) {
        setSessionError(prev =>
          prev ?? { code: e.code, message: 'Connection lost unexpectedly. Start a new inspection to reconnect.' }
        );
      }
    };

    ws.onerror = (e) => {
      console.error('[WS] Error:', e);
    };

    wsRef.current = ws;
  }, []);

  // Disconnect
  const disconnect = useCallback(() => {
    stopCamera();
    stopAudio();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
    setInspecting(false);
  }, []);

  // Reconnect (clear error, fresh session ID, reconnect)
  const reconnect = useCallback(() => {
    setSessionError(null);
    setReportUrl(null);
    setGenerating(false);
    // Generate a new session ID so backend creates a fresh ADK session
    sessionIdRef.current = 'session-' + Math.random().toString(36).substring(2, 9);
    setSessionId(sessionIdRef.current);
    disconnect();
  }, [disconnect]);

  // Send text message
  const sendText = useCallback((text) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'text', content: text }));
    }
  }, []);

  // Audio Capture (16-bit PCM, 16kHz)
  const startAudio = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });
      mediaStreamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);

      // ScriptProcessor for PCM capture (simple, works everywhere)
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;

        const float32 = e.inputBuffer.getChannelData(0);
        // Convert Float32 → Int16 PCM
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        // Send as binary
        wsRef.current.send(int16.buffer);
      };

      source.connect(processor);
      processor.connect(ctx.destination); // Required for ScriptProcessor to fire
      console.log('[Audio] Capture started');
    } catch (err) {
      console.error('[Audio] Failed to start:', err);
    }
  }, []);

  const stopAudio = useCallback(() => {
    activeSourcesRef.current.forEach(source => {
      try { source.stop(); } catch (_) {}
    });
    activeSourcesRef.current = [];
    playNextAtRef.current = 0;

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
    if (playContextRef.current) {
      playContextRef.current.close();
      playContextRef.current = null;
      playNextAtRef.current = 0;
    }
    console.log('[Audio] Capture stopped');
  }, []);

  const flushAudioPlayback = useCallback(() => {
    console.log(`[Interruption] Flushing ${activeSourcesRef.current.length} scheduled audio chunks`);
    activeSourcesRef.current.forEach(source => {
      try { source.stop(); } catch (_) {}
    });
    activeSourcesRef.current = [];
    playNextAtRef.current = 0;
  }, []);

  const playNextAtRef = useRef(0);

  // Audio Playback (24kHz PCM from agent)
  const playAudioChunk = useCallback((base64Data, mimeType) => {
    try {
      if (!playContextRef.current) {
        playContextRef.current = new AudioContext({ sampleRate: 24000 });
        playNextAtRef.current = 0;
      }
      const ctx = playContextRef.current;

      // Normalize: URL-safe base64 → standard base64, strip whitespace, add padding
      const normalized = base64Data
        .replace(/\s/g, '')
        .replace(/-/g, '+')
        .replace(/_/g, '/');
      const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
      const raw = atob(padded);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

      // Int16 PCM → Float32
      const int16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 0x7FFF;
      }

      const buffer = ctx.createBuffer(1, float32.length, 24000);
      buffer.getChannelData(0).set(float32);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      activeSourcesRef.current.push(source);
      source.onended = () => {
        activeSourcesRef.current = activeSourcesRef.current.filter(s => s !== source);
      };

      // Schedule chunks back-to-back to avoid gaps/overlap
      const startAt = Math.max(ctx.currentTime, playNextAtRef.current);
      source.start(startAt);
      playNextAtRef.current = startAt + buffer.duration;

      // Pulse agentSpeaking indicator (debounced 400ms after last chunk)
      setAgentSpeaking(true);
      clearTimeout(agentSpeakingTimerRef.current);
      agentSpeakingTimerRef.current = setTimeout(() => setAgentSpeaking(false), 400);
    } catch (err) {
      console.warn('[Audio] Playback error:', err);
    }
  }, []);

  // Camera Capture (1 FPS JPEG frames)
  const startCamera = useCallback(async (videoElement) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 768, height: 768, facingMode: 'environment' }
      });
      videoElement.srcObject = stream;
      videoRef.current = videoElement;

      // Capture frames at 1 FPS and send to backend
      const canvas = document.createElement('canvas');
      frameIntervalRef.current = setInterval(() => {
        if (!videoElement.videoWidth || wsRef.current?.readyState !== WebSocket.OPEN) return;

        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(videoElement, 0, 0);

        // Convert to JPEG base64 and send
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
        const base64 = dataUrl.split(',')[1];
        wsRef.current.send(JSON.stringify({
          type: 'image',
          data: base64,
          mime_type: 'image/jpeg',
        }));
      }, 1000); // 1 FPS

      console.log('[Camera] Started');
    } catch (err) {
      console.error('[Camera] Failed to start:', err);
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      videoRef.current.srcObject = null;
    }
    console.log('[Camera] Stopped');
  }, []);

  // Event Handler
  const handleEvent = useCallback((event) => {
    // Add to raw events log
    setEvents(prev => [...prev.slice(-100), event]);

    if (event?.interrupted === true) {
      console.log('[Interruption] Agent interrupted by user — flushing audio playback');
      flushAudioPlayback();
      return; // Nothing else to process in this event
    }

    const content = event?.content;
    const parts = content?.parts || [];

    // Debug: log non-audio events so we can see the full structure
    const hasAudio = parts.some(p => p.inline_data || p.inlineData);
    if (!hasAudio) {
      console.log('[Event]', JSON.stringify(event).substring(0, 400));
    }

    for (const part of parts) {
      // Text response from agent (text-mode models)
      if (part.text) {
        setTranscript(prev => [...prev, {
          role: content.role || 'model',
          text: part.text,
          timestamp: Date.now(),
        }]);
      }

      // Audio response from agent → play it
      if (part.inline_data?.mime_type?.startsWith('audio/') || part.inlineData?.mimeType?.startsWith('audio/')) {
        const data = part.inline_data?.data || part.inlineData?.data;
        const mime = part.inline_data?.mime_type || part.inlineData?.mimeType;
        console.log('[Audio] Received chunk, key style:', part.inline_data ? 'snake_case' : 'camelCase', 'data length:', data?.length);
        if (data) playAudioChunk(data, mime);
      }

      // ✅ FIX 1: Function call from agent — correct ADK path is content.parts[].function_call
      if (part.function_call) {
        const fc = part.function_call;
        console.log('[Tool] Function call:', fc.name, fc.args);
        if (fc.name === 'log_finding') {
          const args = fc.args || {};
          setFindings(prev => [...prev, {
            ...args,
            id: args.finding_id || `F-${String(prev.length + 1).padStart(3, '0')}`,
            timestamp: Date.now(),
          }]);
        }
      }

      if (part.function_response) {
        const fr = part.function_response;
        console.log('[Tool] Function response:', fr.name);
        if (fr.name === 'search_web') {
          const results = fr.response?.results || [];
          const valid = results.filter(r => r.url && r.title);
          if (valid.length > 0) {
            console.log(`[Search] Surfacing ${valid.length} result(s) to UI`);
            setSearchResults(prev => {
              const existingUrls = new Set(prev.map(r => r.url));
              const newOnes = valid.filter(r => !existingUrls.has(r.url));
              return newOnes.length > 0 ? [...prev, ...newOnes] : prev;
            });
          }
        }
        // Task 2.3/3.1: capture pdf_url from generate_report tool response
        if (fr.name === 'generate_report') {
          setGenerating(false);
          const url = fr.response?.pdf_url;
          if (url) {
            console.log('[Report] PDF ready:', url);
            setReportUrl(url);
          }
        }
      }
    }

    // ✅ FIX 2: Transcription — only read from partial:false events.
    // The API emits two kinds of transcription events:
    //   partial:true  → streaming chunks (incomplete, used for audio sync)
    //   partial:false → the final complete text for the full utterance
    // Processing both caused every message to appear twice. We only want the final.
    if (event?.partial === false) {
      const inputTrans = event?.input_transcription;
      if (inputTrans?.text?.trim()) {
        console.log('[Transcription] User:', inputTrans.text);
        setTranscript(prev => [...prev, {
          role: 'user',
          text: inputTrans.text.trim(),
          timestamp: Date.now(),
          isTranscription: true,
        }]);
      }

      const outputTrans = event?.output_transcription;
      if (outputTrans?.text?.trim()) {
        console.log('[Transcription] Agent:', outputTrans.text);
        setTranscript(prev => [...prev, {
          role: 'model',
          text: outputTrans.text.trim(),
          timestamp: Date.now(),
          isTranscription: true,
        }]);
      }
    }
  }, [playAudioChunk, flushAudioPlayback]);

  // Start/Stop Inspection
  const startInspection = useCallback(async (videoElement) => {
    if (!connected) connect();

    // Wait for connection
    await new Promise(resolve => {
      const check = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });

    await startAudio();
    if (videoElement) {
      await startCamera(videoElement);
    }
    setInspecting(true);
  }, [connected, connect, startAudio, startCamera]);

  const stopInspection = useCallback(() => {
    stopCamera();
    stopAudio();
    setInspecting(false);
  }, [stopCamera, stopAudio]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Task 3.1: Trigger report generation via agent voice/text flow
  const triggerReport = useCallback(() => {
    setGenerating(true);
    sendText('Generate the inspection report');
  }, [sendText]);

  return {
    // State
    connected,
    inspecting,
    events,
    findings,
    transcript,
    searchResults,
    sessionError,
    // Task 3.1: new state
    reportUrl,
    generating,
    agentSpeaking,
    sessionId,

    // Actions
    connect,
    disconnect,
    reconnect,
    sendText,
    startInspection,
    stopInspection,
    startCamera,
    stopCamera,
    triggerReport,
  };
}