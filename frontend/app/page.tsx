'use client';

import { useRef, useState } from 'react';
import Vapi from '@vapi-ai/web';

type Status = 'idle' | 'connecting' | 'live' | 'ended' | 'error';

const PHASES = [
  { n: 'Phase 1', t: 'Live Baat', d: 'Farmer taps the button — a real-time Saraiki voice call opens via Vapi Web SDK. No forms, no typing.' },
  { n: 'Phase 2', t: 'Suno aur Samjho', d: 'Speech-to-speech in Saraiki/Punjabi/Urdu. Symptoms extracted live; optional photo for breed + weight CV hook.' },
  { n: 'Phase 3', t: 'Diagnostic Dialogue', d: 'The AI asks follow-up questions like a vet, then classifies risk: EMERGENCY / HIGH / MEDIUM / LOW.' },
  { n: 'Phase 4', t: 'Consent', d: 'On EMERGENCY the AI asks live: "Kya qareeb tareen doctor ko bhej doon?" — the farmer decides by voice.' },
  { n: 'Phase 5', t: 'Helpline Proxy', d: 'Autonomous Voice-AI call to the Punjab Livestock Helpline in professional Urdu — files the complaint, captures the tracking number.' },
  { n: 'Phase 6', t: 'Closing the Loop', d: 'Tracking number (e.g. LIV-2026-9912) is reported back to the farmer on the same live call.' },
];

export default function Home() {
  const [status, setStatus] = useState<Status>('idle');
  const [lines, setLines] = useState<string[]>([]);
  const [err, setErr] = useState('');
  const vapiRef = useRef<Vapi | null>(null);

  async function startCall() {
    setErr('');
    setLines([]);
    try {
      const key = process.env.NEXT_PUBLIC_VAPI_PUBLIC_KEY;
      const assistant = process.env.NEXT_PUBLIC_VAPI_ASSISTANT_ID;
      if (!key || !assistant) {
        setErr('Vapi keys missing — .env.local mein NEXT_PUBLIC_VAPI_PUBLIC_KEY aur ASSISTANT_ID set karo.');
        setStatus('error');
        return;
      }
      const vapi = new Vapi(key);
      vapiRef.current = vapi;
      setStatus('connecting');

      vapi.on('call-start', () => setStatus('live'));
      vapi.on('call-end', () => setStatus('ended'));
      vapi.on('error', () => {
        setStatus('error');
        setErr('Call mein error aaya — keys aur assistant ID check karo.');
      });
      vapi.on('message', (m: any) => {
        if (m?.type === 'transcript' && m.transcriptType === 'final' && m.transcript) {
          const who = m.role === 'user' ? 'کسان' : 'PLDHE';
          setLines((prev) => [...prev.slice(-49), `${who}: ${m.transcript}`]);
        }
      });

      await vapi.start(assistant);
    } catch (e: any) {
      setStatus('error');
      setErr(e?.message || 'Call start nahi ho saki.');
    }
  }

  function endCall() {
    vapiRef.current?.stop();
    setStatus('ended');
  }

  const live = status === 'live';
  const busy = status === 'connecting' || live;

  return (
    <div className="wrap">
      <header>
        <div className="kicker">Punjab Livestock Digital Health Ecosystem</div>
        <h1>PLDHE Veterinary Helpline</h1>
        <p>
          Saraiki-first AI helpline for Layyah&apos;s farmers. Tap the button,
          speak naturally — triage, vet dispatch and government complaints
          happen on the live call.
        </p>
      </header>

      <div className="call-card">
        <div>
          <span className={`status-pill ${status}`}>
            {status === 'idle' && '● Ready'}
            {status === 'connecting' && '● Connecting…'}
            {status === 'live' && '● LIVE — baat karein'}
            {status === 'ended' && '● Call khatam'}
            {status === 'error' && '● Error'}
          </span>
        </div>

        {!live ? (
          <button className="talk-btn" onClick={startCall} disabled={busy}>
            {status === 'connecting' ? 'Milaya ja raha hai…' : 'Live Baat Karein'}
          </button>
        ) : (
          <button className="talk-btn stop" onClick={endCall}>
            Call Khatam Karein
          </button>
        )}

        <div className="hint">Microphone ki ijazat dein — Saraiki, Punjabi ya Urdu mein bolein.</div>
        {err && <div className="error">{err}</div>}

        <div className="transcript">
          <h3>Live guftagu</h3>
          {lines.length === 0 && <div className="empty">Call shuru hote hi yahan live transcript nazar aayega…</div>}
          {lines.map((l, i) => (
            <div className="line" key={i}>{l}</div>
          ))}
        </div>
      </div>

      <div className="phases">
        {PHASES.map((p) => (
          <div className="phase" key={p.n}>
            <span className="n">{p.n}</span>
            <h4>{p.t}</h4>
            <p>{p.d}</p>
          </div>
        ))}
      </div>

      <footer>
        PLDHE — FYP, University of Layyah · Backend API docs:{' '}
        <a href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/docs`} target="_blank" rel="noreferrer">
          /docs
        </a>
      </footer>
    </div>
  );
}
