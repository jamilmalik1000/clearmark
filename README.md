# ClearMark

ClearMark is a local web application for removing an unwanted watermark or overlay from an image or video you are authorized to edit. Paint over the unwanted area, preview the mask, and let OpenCV reconstruct the marked pixels using image inpainting.

The app uses a React/Vite frontend and a FastAPI backend. It stores temporary job files on disk and does not use a database.

## Features

- Drag-and-drop image and video uploads
- Brush, eraser, undo, redo, and clear controls
- Adjustable brush size and inpainting radius
- OpenCV Telea and Navier-Stokes inpainting modes
- Fixed-mask video processing with live progress
- Original audio preservation when FFmpeg is installed
- Automatic cleanup of old temporary jobs
- Downloadable PNG/JPEG/MP4 results

## Requirements

- Python 3.10+
- Node.js 18+
- FFmpeg (optional, used to preserve video audio)

## Run locally

### One-click Windows launch

After completing the installation, double-click `Start ClearMark.bat` in the project folder. It starts the local server and opens ClearMark in your default browser. Keep the server window open while using the app; press `Ctrl+C` in that window to stop it.

### Development mode

Open two terminals.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173. The Vite development server proxies `/api` and `/media` requests to FastAPI.

## Production build

Build the frontend, then start FastAPI:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
cd ..\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI detects `frontend/dist` and serves the built app at http://localhost:8000.

## How video processing works

The browser displays the first decodable frame of the video. The mask painted on that frame is resized to the original video dimensions and applied to every frame. This works best for a stationary watermark. Moving watermarks need tracking or a frame-by-frame mask and are outside the current scope.

Uploaded and generated files are stored under `backend/data/jobs`. Jobs older than 24 hours are removed when the API starts. The retention period and upload limit can be changed with `JOB_TTL_HOURS` and `MAX_UPLOAD_MB` environment variables.

## API summary

- `POST /api/jobs` — upload an image or video
- `GET /api/jobs/{job_id}` — read metadata and processing status
- `POST /api/jobs/{job_id}/process` — submit a PNG mask and processing options
- `GET /media/{job_id}/source` — original image or video
- `GET /media/{job_id}/preview` — representative frame used by the editor
- `GET /media/{job_id}/result` — processed output
- `DELETE /api/jobs/{job_id}` — delete a job and its files

Use this application only on media you own or have permission to modify.

