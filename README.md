# 🎵 فاصل الصوت والموسيقى — Vocal & Music Separator

تطبيق ويب كامل لفصل الصوت البشري عن الموسيقى باستخدام **الذكاء الاصطناعي (Demucs من Meta)** وليس بالفلاتر الترددية.
A full web app that separates vocals from music with real AI source separation (**Demucs / HT-Demucs**), for audio *and* video files.

* رفع MP3 / WAV / M4A / MP4 / MOV وأي صيغة يفهمها FFmpeg
* **الموسيقى فقط** (instrumental) أو **الصوت فقط** (vocals)
* فيديو: استخراج الصوت، أو خيار **الحفاظ على الفيديو** (استبدال المسار الصوتي بدون إعادة ترميز الصورة)
* تصدير WAV / MP3 320 / 192 / 128
* واجهة عربية (RTL) مع زر الإنجليزية، متجاوبة (iPhone / Android / Desktop)، سحب وإفلات، شريط تقدم، مشغّل معاينة، زر حفظ
* لا تخزين دائم: تُحذف الملفات بعد المعالجة أو بعد مدة قصيرة

## 1) البنية (Architecture)

```
المتصفح (React + Vite)                         الخادم (FastAPI)
  ├─ POST /api/jobs  (multipart, XHR + progress) ─▶  يكتب الملف على القرص على دفعات 1MB (بدون Base64 / بدون RAM)
  ├─ GET  /api/jobs/{id}  (polling كل ثانية)    ◀─  طابور مهام + عامل (Worker thread)
  ├─ GET  /api/jobs/{id}/preview  (Range)        ◀─  ffprobe ▶ ffmpeg (استخراج WAV 44.1k float) ▶
  └─ GET  /api/jobs/{id}/download (attachment)       Demucs (subprocess، تقدّم من tqdm) ▶ ffmpeg (WAV/MP3/mux فيديو)
                                                   └─ janitor: يحذف كل شيء بعد RETENTION_MINUTES
```

**لماذا Demucs (`htdemucs`)؟** أفضل نموذج مفتوح المصدر متوازن بين الجودة والسرعة (Hybrid Transformer Demucs)، يعمل على CPU وGPU، ويدعم وضع `--two-stems=vocals` الذي ينتج مباشرة `vocals` و`no_vocals`. للجودة الأعلى (أبطأ ~4×) اضبط `DEMUCS_MODEL=htdemucs_ft`.
**لماذا Subprocess؟** يبقي الـ API خفيفاً وغير متجمّد، ويسمح بقراءة التقدّم الحقيقي، وبإيقاف العملية عند الإلغاء أو انتهاء المهلة.
**لماذا FastAPI + Vite/React بدل Next.js؟** التطبيق صفحة واحدة بدون SEO/SSR، فالبناء يخرج ملفات ثابتة يخدمها الـ Backend نفسه (نشر بخادم واحد).

```
/frontend   واجهة React (Vite)
/backend    FastAPI + pipeline (app/), tests/, scripts/download_model.py
/models     أوزان Demucs (تُنزَّل تلقائياً أو بالسكربت)
/uploads    الملفات المرفوعة (مؤقتة، تُحذف فور الاستخراج)
/temp       ملفات وسيطة (تُحذف عند الانتهاء)
/outputs    النتائج (تُحذف بعد RETENTION_MINUTES)
```

## 2) التثبيت

المتطلبات: Python 3.10–3.12، Node.js 18+، FFmpeg.

### تثبيت FFmpeg
```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y ffmpeg libsndfile1
# macOS
brew install ffmpeg
# Windows
winget install Gyan.FFmpeg      # ثم أعد فتح الطرفية
ffmpeg -version && ffprobe -version
```

### Backend
```bash
python3 -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
# CPU فقط (موصى به لتوفير الحجم):
pip install "torch<2.9" "torchaudio<2.9" --index-url https://download.pytorch.org/whl/cpu
# أو لـ GPU (CUDA) اترك الافتراضي من PyPI:  pip install "torch<2.9" "torchaudio<2.9"
pip install -r backend/requirements.txt
```
> ⚠️ يجب أن يبقى `torchaudio < 2.9`؛ Demucs 4.0.1 يحفظ الصوت عبر `torchaudio.save` وقد أُزيل هذا المسار في الإصدارات الأحدث.

### تنزيل نموذج Demucs
```bash
python backend/scripts/download_model.py              # htdemucs (~80MB) إلى ./models
python backend/scripts/download_model.py htdemucs_ft  # اختياري: الأعلى جودة
```
إن لم تفعل ذلك سيُنزَّل النموذج تلقائياً عند أول معالجة (أبطأ مرة واحدة). يحتاج الخادم وصولاً إلى `dl.fbaipublicfiles.com` عند التنزيل.

### Frontend
```bash
cd frontend && npm install
```

## 3) التشغيل محلياً

```bash
./run-dev.sh                    # Backend :8000 + Frontend :5173  → افتح http://localhost:5173
```
أو يدوياً:
```bash
cd backend && uvicorn app.main:app --port 8000          # الطرفية 1
cd frontend && npm run dev                              # الطرفية 2
```
للاختبار من الهاتف على نفس الشبكة افتح `http://<ip-الكمبيوتر>:5173`.

الاختبارات (تستخدم Demucs وهمياً لفحص كامل الـ pipeline بدون تنزيل النموذج):
```bash
pip install -r backend/requirements-dev.txt && cd backend && pytest -q
```

## 4) النشر على Server

**خادم واحد (موصى به):**
```bash
cd frontend && npm ci && npm run build        # ينتج frontend/dist ويخدمه FastAPI تلقائياً
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000   # عامل واحد فقط (حالة المهام في الذاكرة)
```
**Docker:** `docker compose up --build -d` ثم افتح `http://localhost:8000`.

خلف Nginx (HTTPS مطلوب لتحميل الملفات بسلاسة على iOS):
```nginx
server {
  server_name example.com;
  client_max_body_size 600m;          # أكبر من MAX_UPLOAD_MB
  proxy_request_buffering off;        # تمرير الرفع مباشرة
  proxy_read_timeout 3600s;
  location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
}
```
> التطبيق يعمل بعملية واحدة (Uvicorn worker واحد). للتوسّع أفقياً استبدل مخزن المهام في `jobs.py` بـ Redis/Celery.

## 5) متطلبات العتاد

| | CPU | GPU |
|---|---|---|
| الحد الأدنى | 4 أنوية، 8GB RAM | NVIDIA ≥ 4GB VRAM |
| السرعة (htdemucs) | ≈ 1–2× زمن الأغنية (أغنية 4 د ≈ 4–8 د) | ≈ 10–30× أسرع من الزمن الحقيقي |
| `htdemucs_ft` | ≈ 4× أبطأ | ≈ 4× أبطأ |

ذاكرة قليلة؟ اضبط `DEMUCS_SEGMENT=7`. مساحة القرص: ≈ 12× حجم الملف أثناء المعالجة (يُفحص تلقائياً).

## 6) الإعدادات (متغيرات البيئة — انظر `.env.example`)

| المتغير | الافتراضي | الوصف |
|---|---|---|
| `MAX_UPLOAD_MB` | 500 | **الحد الأقصى لحجم الملف** (غيّر أيضاً `client_max_body_size` في Nginx) |
| `RETENTION_MINUTES` | 30 | **مدة الاحتفاظ بالنتائج المؤقتة** قبل الحذف التلقائي |
| `MAX_DURATION_MIN` | 60 | أقصى مدة للملف |
| `PROCESS_TIMEOUT_SEC` | 3600 | مهلة المعالجة لكل ملف |
| `CONCURRENT_JOBS` | 1 | عدد المهام المتزامنة (كل مهمة تستهلك CPU/GPU كاملاً) |
| `DEMUCS_MODEL` | htdemucs | `htdemucs` أو `htdemucs_ft` |
| `DEMUCS_DEVICE` | auto | `auto` / `cpu` / `cuda` |
| `DEMUCS_SHIFTS` | 1 | قيمة أعلى = جودة أعلى وبطء |
| `DEMUCS_SEGMENT` | — | ثوانٍ؛ أقل = ذاكرة أقل |

مثال: `MAX_UPLOAD_MB=1000 RETENTION_MINUTES=10 uvicorn app.main:app`

## 7) الجودة والخصوصية

* الاستخراج بـ 44.1kHz / 32-bit float ← النموذج ← تصدير WAV (16 أو 24-bit حسب المصدر) دون MP3 إلا إذا اخترته؛ يُشفَّر الناتج **مرة واحدة فقط**.
* الفيديو: الصورة تُنسخ بدون إعادة ترميز (`-c:v copy`) والصوت يُشفَّر AAC 320k (أو بمعدل MP3 المختار).
* الملف المرفوع يُحذف فور استخراج الصوت؛ الوسيط يُحذف عند الانتهاء؛ النتيجة تُحذف بعد `RETENTION_MINUTES` أو عند "معالجة ملف آخر"؛ وكل المجلدات تُفرَّغ عند إقلاع الخادم.

## واجهة API

| | |
|---|---|
| `POST /api/jobs` | multipart: `file`, `mode`=`instrumental`\|`vocals`, `format`=`wav`\|`mp3_320`\|`mp3_192`\|`mp3_128`, `keep_video` |
| `GET /api/jobs/{id}` | `status`, `stage`, `progress`, `queue_position`, `error` |
| `GET /api/jobs/{id}/preview` | معاينة (Range) |
| `GET /api/jobs/{id}/download` | تحميل (`Content-Disposition: attachment`) |
| `DELETE /api/jobs/{id}` | إلغاء/حذف فوري |

أكواد الأخطاء: `unsupported, too_large, too_long, corrupt, extract_failed, separation_failed, ffmpeg_failed, disk_full, timeout, internal`.

## النشر من الموبايل (بدون كمبيوتر) — Render

1. على render.com أنشئ حساباً واربطه بحساب GitHub.
2. **New + ← Blueprint** ← اختر المستودع `music-tool` ← **Apply** (يقرأ `render.yaml` تلقائياً).
3. انتظر البناء (≈10 دقائق، لأنه ينزّل torch والنموذج)، ثم افتح الرابط `https://….onrender.com` من Safari.

الخطة `standard` (2GB RAM) هي الأدنى الذي يتحمّل Demucs. التكلفة بالساعة، فيمكنك تجربتها ثم **Suspend/Delete** من لوحة Render. الخطط المجانية (512MB) لا تكفي.
