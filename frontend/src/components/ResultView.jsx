import React from 'react';
import Player from './Player.jsx';
import { downloadUrl, previewUrl } from '../api.js';

export default function ResultView({ t, cfg, job, onReset }) {
  return (
    <section className="card result">
      <div className="okmark" aria-hidden>✓</div>
      <h2>{t.resultReady}</h2>
      <div className="pname" dir="auto">{job.filename}</div>
      <h3>{t.listen}</h3>
      <Player t={t} src={previewUrl(job.id)} kind={job.kind} />
      {/* A plain link with Content-Disposition: attachment is the most reliable way to save on iOS, Android and desktop. */}
      <a className="primary big" href={downloadUrl(job.id)} download={job.filename}>⬇️ {t.save}</a>
      <p className="hint">{t.expires(cfg.retention_minutes)}</p>
      <button className="ghost" onClick={onReset}>{t.again}</button>
    </section>
  );
}
