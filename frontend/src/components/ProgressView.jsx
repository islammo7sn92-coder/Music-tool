import React, { useEffect, useState } from 'react';
import { formatTime } from '../utils.js';

// Overall bar: upload = 0-10 %, server work (0-100) = 10-100 %.
export default function ProgressView({ t, file, stage, percent, queuePos, onCancel }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const i = setInterval(() => setElapsed((Date.now() - start) / 1000), 500);
    return () => clearInterval(i);
  }, []);

  const overall = stage === 'uploading' ? percent * 0.1 : 10 + percent * 0.9;
  const shown = Math.min(99, Math.round(overall));
  const label = stage === 'queued' && queuePos > 0 ? `${t.stages.queued} — ${t.queuePos(queuePos)}` : t.stages[stage] || t.stages.analyzing;
  const order = ['uploading', 'analyzing', 'separating', 'finalizing'];

  return (
    <section className="card progress" aria-live="polite">
      <div className="spinner" aria-hidden />
      <div className="pname" dir="auto">{file?.name}</div>
      <div className="plabel">{label}</div>
      <div className="bar" role="progressbar" aria-valuenow={shown} aria-valuemin={0} aria-valuemax={100}>
        <div className="fill" style={{ width: `${Math.max(2, overall)}%` }} />
        <div className="shine" />
      </div>
      <div className="pmeta"><span>{shown}%</span><span>{t.elapsed} {formatTime(elapsed)}</span></div>
      <ol className="steps">
        {order.map((s) => (
          <li key={s} className={s === stage ? 'cur' : order.indexOf(s) < order.indexOf(stage === 'queued' ? 'analyzing' : stage) ? 'past' : ''}>
            {t.stages[s]}
          </li>
        ))}
      </ol>
      <p className="hint">{t.keepOpen}</p>
      <button className="ghost" onClick={onCancel}>{t.cancel}</button>
    </section>
  );
}
