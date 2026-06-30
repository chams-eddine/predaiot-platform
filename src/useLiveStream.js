import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * PREDAIOT Live Stream Hook
 * Connects to ws://backend/ws/live and processes advisory steps.
 * Falls back to demo mode if no connection.
 */
export function useLiveStream(wsUrl) {
  const [connected, setConnected] = useState(false);
  const [step, setStep] = useState(null);
  const [history, setHistory] = useState([]);
  const cumRef = useRef({ opt: 0, act: 0, steps: 0 });
  const wsRef = useRef(null);

  const processStep = useCallback((raw) => {
    const d = { ...raw };

    // Accumulate if server doesn't send cumulative
    if (d.cumulative_opt != null) {
      cumRef.current.opt = d.cumulative_opt;
    } else {
      cumRef.current.opt += Math.max(0, ((d.price || 0) - 5) * (d.optimal_action || 0));
    }
    if (d.cumulative_act != null) {
      cumRef.current.act = d.cumulative_act;
    } else {
      cumRef.current.act += Math.max(0, ((d.price || 0) - 5) * (d.actual_action || 0));
    }
    cumRef.current.steps++;

    d.cumulative_gap = cumRef.current.opt - cumRef.current.act;
    d.dq_score_live = cumRef.current.opt > 0
      ? (cumRef.current.act / cumRef.current.opt * 100)
      : 100;

    // Rating
    const dq = d.dq_score_live / 100;
    if (dq >= 0.9) d.rating = 'AAA';
    else if (dq >= 0.8) d.rating = 'AA';
    else if (dq >= 0.7) d.rating = 'A';
    else if (dq >= 0.6) d.rating = 'BBB';
    else if (dq >= 0.5) d.rating = 'BB';
    else if (dq >= 0.4) d.rating = 'B';
    else d.rating = 'CCC';

    setStep(d);
    setHistory(prev => [d, ...prev].slice(0, 60));
  }, []);

  const connect = useCallback((url) => {
    if (wsRef.current) wsRef.current.close();
    try {
      const ws = new WebSocket(url);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => {
        try { processStep(JSON.parse(e.data)); } catch (err) { console.error(err); }
      };
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setConnected(false);
      wsRef.current = ws;
    } catch (e) {
      console.error('WS connection error', e);
      setConnected(false);
    }
  }, [processStep]);

  const disconnect = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setConnected(false);
  }, []);

  // Auto-connect if URL provided
  useEffect(() => {
    if (wsUrl) connect(wsUrl);
    return () => disconnect();
  }, [wsUrl, connect, disconnect]);

  const reset = useCallback(() => {
    cumRef.current = { opt: 0, act: 0, steps: 0 };
    setStep(null);
    setHistory([]);
  }, []);

  return { connected, step, history, connect, disconnect, reset, processStep };
}