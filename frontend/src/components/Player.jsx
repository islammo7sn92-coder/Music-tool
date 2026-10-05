import React, { useEffect, useRef, useState } from 'react';
import { formatTime } from '../utils.js';

// Custom player (play/pause, time, seek bar, volume) over a native <audio>/<video> element.
export default function Player({ t, src, kind }) {
  const el = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [cur, setCur] = useState(0);
  const [dur, setDur] = useState(0);
  const [vol, setVol] = useState(1);
  const [seeking, setSeeking] = useState(false);

  useEffect(() => { if (el.current) el.current.volume = vol; }, [vol]);

  const toggle = () => {
    const m = el.current;
    if (!m) return;
    if (m.paused) m.play().catch(() => {}); else m.pause();
  };
  const Tag = kind === 'video' ? 'video' : 'audio';

  return (
    <div className="player">
      <Tag ref={el} src={src} preload="metadata" playsInline className={kind === 'video' ? 'pvideo' : undefined}
        onClick={kind === 'video' ? toggle : undefined}
        onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
        onDurationChange={(e) => Number.isFinite(e.currentTarget.duration) && setDur(e.currentTarget.duration)}
        onTimeUpdate={(e) => !seeking && setCur(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
      <div className="prow">
        <button className="play" onClick={toggle} aria-label={playing ? t.pause : t.play}>
          {playing ? '⏸' : '▶'}
        </button>
        <span className="time" dir="ltr">{formatTime(cur)}</span>
        <input className="seek" type="range" dir="ltr" min={0} max={dur || 0} step="0.01" value={Math.min(cur, dur || 0)}
          aria-label={t.seek}
          onChange={(e) => { setCur(+e.target.value); setSeeking(true); }}
          onPointerUp={(e) => { if (el.current) el.current.currentTime = +e.currentTarget.value; setSeeking(false); }}
          onKeyUp={(e) => { if (el.current) el.current.currentTime = +e.currentTarget.value; setSeeking(false); }}
          style={{ '--pct': `${dur ? (cur / dur) * 100 : 0}%` }} />
        <span className="time" dir="ltr">{formatTime(dur)}</span>
      </div>
      <div className="prow vol">
        <span aria-hidden>{vol === 0 ? '🔈' : '🔊'}</span>
        <input type="range" dir="ltr" min={0} max={1} step="0.01" value={vol} aria-label={t.volume}
          onChange={(e) => setVol(+e.target.value)} style={{ '--pct': `${vol * 100}%` }} />
      </div>
    </div>
  );
}
