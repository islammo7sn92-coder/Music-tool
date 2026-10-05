// Thin client for the backend. Upload uses XHR because fetch cannot report upload progress.

export class ApiError extends Error {
  constructor(code) { super(code); this.code = code; }
}

export async function getConfig() {
  const r = await fetch('/api/config');
  if (!r.ok) throw new ApiError('network');
  return r.json();
}

export function uploadJob({ file, mode, format, keepVideo }, onProgress) {
  const xhr = new XMLHttpRequest();
  const promise = new Promise((resolve, reject) => {
    const form = new FormData();           // multipart: the browser streams the file, no base64
    form.append('file', file, file.name);
    form.append('mode', mode);
    form.append('format', format);
    form.append('keep_video', keepVideo ? 'true' : 'false');
    xhr.open('POST', '/api/jobs');
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onerror = () => reject(new ApiError('network'));
    xhr.onabort = () => reject(new ApiError('cancelled'));
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* not json */ }
      if (xhr.status >= 200 && xhr.status < 300 && body.id) resolve(body.id);
      else reject(new ApiError(body.error || (xhr.status === 413 ? 'too_large' : 'internal')));
    };
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
}

export async function getJob(id) {
  let r;
  try { r = await fetch(`/api/jobs/${id}`, { cache: 'no-store' }); }
  catch { throw new ApiError('network'); }
  if (r.status === 404) throw new ApiError('expired');
  if (!r.ok) throw new ApiError('internal');
  return r.json();
}

export const previewUrl = (id) => `/api/jobs/${id}/preview`;
export const downloadUrl = (id) => `/api/jobs/${id}/download`;
export const deleteJob = (id) => fetch(`/api/jobs/${id}`, { method: 'DELETE', keepalive: true }).catch(() => {});
