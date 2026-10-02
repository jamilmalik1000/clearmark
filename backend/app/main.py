from __future__ import annotations

import os
import re
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .processing import process_image, process_video
from .schemas import JobResponse, ProcessRequest
from .store import Job, JobStore


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BASE_DIR.parent
JOBS_DIR = BASE_DIR / "data" / "jobs"
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "500")) * 1024 * 1024
JOB_TTL_HOURS = int(os.getenv("JOB_TTL_HOURS", "24"))
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

store = JobStore(JOBS_DIR)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.cleanup(JOB_TTL_HOURS)
    yield


app = FastAPI(
    title="ClearMark API",
    description="Local OpenCV image and video inpainting service.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def response_for(job: Job) -> JobResponse:
    result = store.directory(job.id) / job.result_name
    return JobResponse(
        id=job.id,
        media_type=job.media_type,
        filename=job.filename,
        width=job.width,
        height=job.height,
        duration=job.duration,
        status=job.status,
        progress=round(job.progress, 1),
        error=job.error,
        source_url=f"/media/{job.id}/source",
        preview_url=f"/media/{job.id}/preview",
        result_url=f"/media/{job.id}/result" if job.status == "complete" and result.exists() else None,
    )


def clean_filename(filename: str | None) -> str:
    raw = Path(filename or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", raw).strip(" .")
    return cleaned[:160] or "upload"


async def save_upload(upload: UploadFile, destination: Path) -> None:
    total = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit.")
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def inspect_media(source: Path, media_type: str, preview: Path) -> tuple[int, int, float | None]:
    if media_type == "image":
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("This image format is unsupported or the file is damaged.")
        if not cv2.imwrite(str(preview), image):
            raise ValueError("A preview could not be created for this image.")
        return image.shape[1], image.shape[0], None

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError("This video format is unsupported or the file is damaged.")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, frame = capture.read()
        if not ok or frame is None or width <= 0 or height <= 0:
            raise ValueError("A preview frame could not be decoded from this video.")
        if not cv2.imwrite(str(preview), frame):
            raise ValueError("The video preview could not be saved.")
        duration = frames / fps if fps and fps > 0 and frames > 0 else None
        return width, height, duration
    finally:
        capture.release()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", response_model=JobResponse, status_code=201)
async def create_job(file: UploadFile = File(...)) -> JobResponse:
    filename = clean_filename(file.filename)
    extension = Path(filename).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        media_type = "image"
    elif extension in VIDEO_EXTENSIONS:
        media_type = "video"
    else:
        supported = ", ".join(sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS))
        raise HTTPException(415, f"Unsupported file type. Accepted extensions: {supported}")

    job_id = uuid.uuid4().hex
    directory = store.directory(job_id)
    directory.mkdir(parents=True, exist_ok=False)
    source_name = f"source{extension}"
    source = directory / source_name
    preview = directory / "preview.jpg"
    try:
        await save_upload(file, source)
        width, height, duration = inspect_media(source, media_type, preview)
        result_name = "result.png" if media_type == "image" else "result.mp4"
        job = Job(
            id=job_id,
            media_type=media_type,
            filename=filename,
            source_name=source_name,
            result_name=result_name,
            width=width,
            height=height,
            duration=duration,
            created_at=time.time(),
        )
        store.add(job)
        return response_for(job)
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except ValueError as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(500, "The upload could not be prepared.") from exc


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return response_for(job)


@app.post("/api/jobs/{job_id}/process", response_model=JobResponse, status_code=202)
def start_processing(job_id: str, request: ProcessRequest) -> JobResponse:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status == "processing":
        raise HTTPException(409, "This job is already processing.")

    job.status = "processing"
    job.progress = 0
    job.error = None
    store.save(job)

    thread = threading.Thread(
        target=run_processing,
        args=(job_id, request),
        daemon=True,
        name=f"process-{job_id[:8]}",
    )
    thread.start()
    return response_for(job)


def run_processing(job_id: str, request: ProcessRequest) -> None:
    job = store.get(job_id)
    if not job:
        return
    directory = store.directory(job.id)
    source = directory / job.source_name
    output = directory / job.result_name
    output.unlink(missing_ok=True)

    def progress(value: float) -> None:
        job.progress = max(job.progress, min(100.0, value))
        store.save(job)

    try:
        processor = process_image if job.media_type == "image" else process_video
        processor(source, output, request.mask_data_url, request.method, request.radius, progress)
        job.status = "complete"
        job.progress = 100
    except Exception as exc:
        output.unlink(missing_ok=True)
        job.status = "failed"
        job.error = str(exc) or "Processing failed."
    finally:
        store.save(job)


@app.delete("/api/jobs/{job_id}", status_code=204, response_class=Response)
def delete_job(job_id: str) -> Response:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status == "processing":
        raise HTTPException(409, "Wait for processing to finish before deleting this job.")
    store.delete(job_id)
    return Response(status_code=204)


@app.get("/media/{job_id}/{kind}")
def media(job_id: str, kind: str) -> FileResponse:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if kind == "source":
        path = store.directory(job.id) / job.source_name
    elif kind == "preview":
        path = store.directory(job.id) / "preview.jpg"
    elif kind == "result" and job.status == "complete":
        path = store.directory(job.id) / job.result_name
    else:
        raise HTTPException(404, "Media not found.")
    if not path.exists():
        raise HTTPException(404, "Media not found.")
    return FileResponse(path, filename=path.name if kind == "result" else None)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        requested = FRONTEND_DIST / path
        if path and requested.is_file() and FRONTEND_DIST in requested.resolve().parents:
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")

