export function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatTime(sec) {
  if (!Number.isFinite(sec) || sec < 0) return '--:--';
  const s = Math.floor(sec);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, '0'), rr = String(r).padStart(2, '0');
  return h ? `${h}:${mm}:${rr}` : `${mm}:${rr}`;
}

// Read the duration locally in the browser (works for most audio/video the browser can decode).
export function readDuration(file) {
  return new Promise((resolve) => {
    const isVideo = file.type.startsWith('video') || /\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(file.name);
    const el = document.createElement(isVideo ? 'video' : 'audio');
    const url = URL.createObjectURL(file);
    const done = (v) => { URL.revokeObjectURL(url); el.removeAttribute('src'); el.load(); resolve(v); };
    const timer = setTimeout(() => done(null), 8000);
    el.preload = 'metadata';
    el.onloadedmetadata = () => { clearTimeout(timer); done(Number.isFinite(el.duration) ? el.duration : null); };
    el.onerror = () => { clearTimeout(timer); done(null); };
    el.src = url;
  });
}

export const isVideoFile = (file) =>
  file.type.startsWith('video') || /\.(mp4|mov|m4v|webm|mkv|avi|3gp|wmv|flv|mts|m2ts)$/i.test(file.name);
