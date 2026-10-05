import React, { useRef, useState } from 'react';
import { formatSize, formatTime } from '../utils.js';

const ACCEPT = 'audio/*,video/*,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.wma,.mp4,.mov,.m4v,.mkv,.webm,.avi,.3gp';

export default function UploadZone({ t, cfg, file, duration, isVideo, onFile }) {
  const input = useRef(null);
  const [over, setOver] = useState(false);
  const pick = () => input.current?.click();

  const onDrop = (e) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  return (
    <section className="card">
      <input ref={input} type="file" accept={ACCEPT} hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ''; }} />

      {file ? (
        <div className="filecard">
          <div className="fileicon">{isVideo ? '🎬' : '🎵'}</div>
          <div className="fileinfo">
            <div className="filename" dir="auto" title={file.name}>{file.name}</div>
            <div className="filemeta">
              <bdi dir="ltr">{formatSize(file.size)}</bdi>
              <span>•</span>
              <bdi dir="ltr">{duration == null ? t.unknownDuration : formatTime(duration)}</bdi>
            </div>
          </div>
          <button className="chip" onClick={pick}>{t.change}</button>
        </div>
      ) : (
        <div className={`drop ${over ? 'over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}>
          <div className="drop-icon">⬆️</div>
          <button className="primary big" onClick={pick}>{t.upload}</button>
          <p className="hint desktop-only">{t.dropHere}</p>
          <p className="hint">{t.formats} · {t.maxSize(cfg.max_upload_mb)}</p>
        </div>
      )}
    </section>
  );
}
