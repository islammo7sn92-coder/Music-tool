import React, { useCallback, useEffect, useRef, useState } from 'react';
import { STRINGS, errorMessage } from './i18n.js';
import { ApiError, deleteJob, getConfig, getJob, uploadJob } from './api.js';
import { isVideoFile, readDuration } from './utils.js';
import UploadZone from './components/UploadZone.jsx';
import ModeSelector from './components/ModeSelector.jsx';
import ProgressView from './components/ProgressView.jsx';
import ResultView from './components/ResultView.jsx';

const DEFAULT_CFG = { max_upload_mb: 500, max_duration_min: 60, retention_minutes: 30 };
const MAX_POLL_FAILURES = 8;
const JOB_KEY = 'activeJob';

const saveJob = (v) => { try { localStorage.setItem(JOB_KEY, JSON.stringify(v)); } catch { /* private mode */ } };
const clearJob = () => { try { localStorage.removeItem(JOB_KEY); } catch { /* private mode */ } };
const loadJob = () => { try { return JSON.parse(localStorage.getItem(JOB_KEY)); } catch { return null; } };

export default function App() {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('lang') || 'ar'; } catch { return 'ar'; }
  });
  const t = STRINGS[lang];
  const [cfg, setCfg] = useState(DEFAULT_CFG);

  const [file, setFile] = useState(null);
  const [duration, setDuration] = useState(null);
  const [mode, setMode] = useState(null);
  const [format, setFormat] = useState('wav');
  const [keepVideo, setKeepVideo] = useState(false);

  // phase: idle | working | done | error
  const [phase, setPhase] = useState('idle');
  const [stage, setStage] = useState('uploading');
  const [percent, setPercent] = useState(0);
  const [queuePos, setQueuePos] = useState(0);
  const [errCode, setErrCode] = useState(null);
  const [result, setResult] = useState(null);

  const run = useRef({ id: null, abort: null, cancelled: false });
  const wakeLock = useRef(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = t.dir;
    document.title = t.title;
    try { localStorage.setItem('lang', lang); } catch { /* private mode */ }
  }, [lang, t]);

  useEffect(() => { getConfig().then(setCfg).catch(() => {}); }, []);

  const video = file instanceof File ? isVideoFile(file) : false;

  const onFile = useCallback(async (f) => {
    setErrCode(null);
    setPhase('idle');
    setFile(f);
    setDuration(null);
    if (!isVideoFile(f)) setKeepVideo(false);
    setDuration(await readDuration(f));
  }, []);

  const acquireWake = async () => {
    try { wakeLock.current = await navigator.wakeLock?.request('screen'); } catch { /* unsupported */ }
  };
  const releaseWake = () => { try { wakeLock.current?.release(); } catch { /* noop */ } wakeLock.current = null; };

  const fail = (code) => {
    setFile((f) => (f instanceof File ? f : null)); // a resumed job has no real File to retry with
    releaseWake(); setErrCode(code); setPhase('error'); };

  const start = async () => {
    if (!file || !mode) return;
    if (file.size > cfg.max_upload_mb * 1024 * 1024) return fail('too_large');
    run.current = { id: null, abort: null, cancelled: false };
    const me = run.current;
    setPhase('working'); setStage('uploading'); setPercent(0); setQueuePos(0); setErrCode(null);
    acquireWake();

    const up = uploadJob({ file, mode, format, keepVideo: keepVideo && video },
      (f) => setPercent(f * 100));
    me.abort = up.abort;
    let id;
    try { id = await up.promise; } catch (e) { return me.cancelled ? undefined : fail(e.code || 'internal'); }
    me.id = id;
    if (me.cancelled) return deleteJob(id);
    saveJob({ id, name: file.name });
    track(id, me);
  };

  // Poll a job until it finishes. Also used to resume a job after the page was closed/reloaded.
  const track = async (id, me) => {
    let failures = 0;
    while (!me.cancelled) {
      try {
        const j = await getJob(id);
        failures = 0;
        if (j.status === 'error') { clearJob(); return fail(j.error || 'internal'); }
        if (j.status === 'done') { releaseWake(); setResult(j); setPhase('done'); return; }
        setStage(j.stage); setPercent(j.progress); setQueuePos(j.queue_position);
      } catch (e) {
        if (e.code === 'expired') { clearJob(); return fail('expired'); }
        if (++failures >= MAX_POLL_FAILURES) return fail(e.code || 'network');
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  };

  // On load: resume an unfinished job (or show a finished one that has not expired yet).
  useEffect(() => {
    const saved = loadJob();
    if (!saved?.id) return;
    getJob(saved.id).then((j) => {
      if (j.status === 'error') return clearJob();
      run.current = { id: saved.id, abort: null, cancelled: false };
      setFile({ name: saved.name || '', size: 0 });
      if (j.status === 'done') { setResult(j); setPhase('done'); return; }
      setPhase('working'); setStage(j.stage); setPercent(j.progress); setQueuePos(j.queue_position);
      acquireWake();
      track(saved.id, run.current);
    }).catch((e) => { if (e.code === 'expired') clearJob(); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cancel = () => {
    const me = run.current;
    me.cancelled = true;
    me.abort?.();
    if (me.id) deleteJob(me.id);
    clearJob();
    releaseWake();
    setPhase('idle');
  };

  const reset = () => {
    if (run.current.id) deleteJob(run.current.id);
    clearJob();
    run.current = { id: null, abort: null, cancelled: false };
    setFile(null); setDuration(null); setMode(null); setKeepVideo(false);
    setResult(null); setErrCode(null); setPhase('idle');
  };

  const busy = phase === 'working';

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 64 64" width="28" height="28"><path d="M20 40V24m8 22V18m8 20V26m8 14V22" stroke="#fff" strokeWidth="6" strokeLinecap="round" fill="none" /></svg>
          </span>
          <div>
            <h1>{t.title}</h1>
            <p>{t.subtitle}</p>
          </div>
        </div>
        <button className="chip" onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')} aria-label="Language">
          🌐 {t.langBtn}
        </button>
      </header>

      <main>
        {phase === 'done' && result ? (
          <ResultView t={t} cfg={cfg} job={result} onReset={reset} />
        ) : busy ? (
          <ProgressView t={t} file={file} stage={stage} percent={percent} queuePos={queuePos} onCancel={cancel} />
        ) : (
          <>
            <UploadZone t={t} cfg={cfg} file={file} duration={duration} isVideo={video} onFile={onFile} />
            {phase === 'error' && (
              <div className="error" role="alert">
                <strong>⚠️ {t.errorTitle}</strong>
                <p>{errorMessage(t, errCode, cfg)}</p>
              </div>
            )}
            {file && (
              <ModeSelector t={t} mode={mode} setMode={setMode} format={format} setFormat={setFormat}
                isVideo={video} keepVideo={keepVideo} setKeepVideo={setKeepVideo} />
            )}
            {file && (
              <button className="primary big" disabled={!mode} onClick={start}>
                {phase === 'error' ? t.retry : t.start}
              </button>
            )}
          </>
        )}
      </main>

      <footer className="privacy">{t.privacy(cfg.retention_minutes)}</footer>
    </div>
  );
}
