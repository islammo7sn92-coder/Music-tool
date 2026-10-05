import React from 'react';

const FORMATS = [
  ['wav', 'WAV'],
  ['mp3_320', 'MP3 320 kbps'],
  ['mp3_192', 'MP3 192 kbps'],
  ['mp3_128', 'MP3 128 kbps'],
];

export default function ModeSelector({ t, mode, setMode, format, setFormat, isVideo, keepVideo, setKeepVideo }) {
  return (
    <section className="card">
      <h2>{t.chooseResult}</h2>
      <div className="modes" role="radiogroup">
        <button role="radio" aria-checked={mode === 'instrumental'}
          className={`mode ${mode === 'instrumental' ? 'on' : ''}`} onClick={() => setMode('instrumental')}>
          <span className="mode-emoji">🎵</span>
          <strong>{t.musicOnly}</strong>
          <small>{t.musicOnlyDesc}</small>
        </button>
        <button role="radio" aria-checked={mode === 'vocals'}
          className={`mode ${mode === 'vocals' ? 'on' : ''}`} onClick={() => setMode('vocals')}>
          <span className="mode-emoji">🎤</span>
          <strong>{t.voiceOnly}</strong>
          <small>{t.voiceOnlyDesc}</small>
        </button>
      </div>

      <div className="options">
        <label className="field">
          <span>{t.exportFormat}</span>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            {FORMATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        {isVideo && (
          <label className="check">
            <input type="checkbox" checked={keepVideo} onChange={(e) => setKeepVideo(e.target.checked)} />
            <span>
              <strong>{t.keepVideo}</strong>
              <small>{t.keepVideoDesc}</small>
            </span>
          </label>
        )}
      </div>
    </section>
  );
}
