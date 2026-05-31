from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .services.gif_converter import (
    MAX_SOURCE_DURATION_SECONDS,
    MAX_VIDEO_UPLOAD_BYTES,
    GifConversionError,
    GifConverter,
    parse_gif_settings,
)
from .services.gif_tasks import GifTaskStore


ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "application/octet-stream"}
GIF_WORKER_SEMAPHORE = threading.Semaphore(1)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_TEMP_DIR = PROJECT_ROOT / ".tmp"
DEFAULT_TASK_STORE = PROJECT_ROOT / "data" / "gif_tasks.json"
logger = logging.getLogger("gif_toolkit")


def _public_task_view(task: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "task_id",
        "status",
        "progress",
        "gif_url",
        "download_url",
        "file_size",
        "duration",
        "width",
        "height",
        "fps",
        "error",
        "attempts",
        "crop_mode",
        "crop",
        "created_at",
        "updated_at",
    ]
    return {key: task[key] for key in keys if key in task}


def _settings_crop(settings: Any) -> dict[str, float | str]:
    return {
        "mode": settings.crop_mode,
        "x": settings.crop_x,
        "y": settings.crop_y,
        "w": settings.crop_w,
        "h": settings.crop_h,
    }


def _gif_dimensions(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return 0, 0


def _validate_video_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Choose a video file")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only MP4, MOV, and WebM videos are supported")
    if file.content_type and file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Only MP4, MOV, and WebM videos are supported")
    return suffix


def _safe_output_file(output_dir: Path, filename: str) -> Path:
    safe_name = Path(filename).name
    path = (output_dir / safe_name).resolve()
    resolved_output = output_dir.resolve()
    if path != resolved_output and resolved_output not in path.parents:
        raise HTTPException(status_code=404, detail="File not found")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return path


def create_gif_router(
    *,
    output_dir: Path,
    temp_dir: Path,
    task_store: GifTaskStore,
    converter: GifConverter,
    uuid_hex: Callable[[], str],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/gif/status")
    def gif_runtime_status() -> dict[str, Any]:
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        ready = bool(ffmpeg_path and ffprobe_path)
        return {
            "ready": ready,
            "ffmpeg": bool(ffmpeg_path),
            "ffprobe": bool(ffprobe_path),
            "ffmpeg_path": ffmpeg_path or "",
            "ffprobe_path": ffprobe_path or "",
            "message": "" if ready else "Install FFmpeg and FFprobe before converting videos.",
        }

    def run_conversion_task(
        *,
        task_id: str,
        source_path: Path,
        task_dir: Path,
        settings: Any,
    ) -> None:
        acquired = GIF_WORKER_SEMAPHORE.acquire(timeout=1)
        if not acquired:
            task_store.update(task_id, {"status": "failed", "progress": 100, "error": "Server is busy. Try again soon."})
            shutil.rmtree(task_dir, ignore_errors=True)
            return
        try:
            task_store.update(task_id, {"status": "processing", "progress": 35})
            result = converter.convert(source_path, task_dir, settings)
            width, height = _gif_dimensions(result.output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / f"video_gif_{task_id}.gif"
            shutil.copyfile(result.output_path, final_path)
            gif_url = f"/outputs/{final_path.name}"
            task_store.update(
                task_id,
                {
                    "status": "success",
                    "progress": 100,
                    "gif_url": gif_url,
                    "download_url": gif_url,
                    "file_size": result.file_size,
                    "duration": result.duration,
                    "width": width or result.width,
                    "height": height,
                    "fps": result.fps,
                    "attempts": result.attempts,
                    "crop_mode": settings.crop_mode,
                    "crop": _settings_crop(settings),
                },
            )
        except Exception as exc:
            logger.exception("GIF conversion task failed: %s", task_id)
            message = str(exc) if isinstance(exc, GifConversionError) else "GIF generation failed. Lower the settings and try again."
            task_store.update(task_id, {"status": "failed", "progress": 100, "error": message})
        finally:
            GIF_WORKER_SEMAPHORE.release()
            shutil.rmtree(task_dir, ignore_errors=True)

    @router.post("/api/gif/create")
    async def create_gif_task(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        start_time: str = Form("0"),
        duration: str = Form("3"),
        width: str = Form("320"),
        fps: str = Form("8"),
        speed: str = Form("1"),
        target_size: str = Form("1048576"),
        quality_mode: str = Form("standard"),
        crop_mode: str = Form("full"),
        crop_x: str = Form("0"),
        crop_y: str = Form("0"),
        crop_w: str = Form("1"),
        crop_h: str = Form("1"),
    ) -> dict[str, Any]:
        suffix = _validate_video_upload(file)
        try:
            settings = parse_gif_settings(
                start_time=start_time,
                duration=duration,
                width=width,
                fps=fps,
                speed=speed,
                target_size=target_size,
                quality_mode=quality_mode,
                crop_mode=crop_mode,
                crop_x=crop_x,
                crop_y=crop_y,
                crop_w=crop_w,
                crop_h=crop_h,
            )
        except GifConversionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        task_id = uuid_hex()
        task_dir = temp_dir / f"gif_tmp_{task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)
        source_path = task_dir / f"source{suffix}"
        data = await file.read(MAX_VIDEO_UPLOAD_BYTES + 1)
        if not data:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Uploaded video is empty")
        if len(data) > MAX_VIDEO_UPLOAD_BYTES:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Video uploads are limited to 50MB")
        source_path.write_bytes(data)

        try:
            meta = converter.probe(source_path)
            source_duration = float(meta.get("duration", 0) or 0)
            if source_duration > MAX_SOURCE_DURATION_SECONDS:
                raise HTTPException(status_code=400, detail="Source video cannot exceed 180 seconds")
            if settings.start_time + settings.duration > source_duration + 0.001:
                raise HTTPException(status_code=400, detail="start_time + duration cannot exceed the source duration")
        except HTTPException:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise
        except GifConversionError as exc:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        task_store.create(
            {
                "task_id": task_id,
                "status": "processing",
                "progress": 10,
                "duration": settings.duration,
                "width": settings.width,
                "fps": settings.fps,
                "crop_mode": settings.crop_mode,
                "crop": _settings_crop(settings),
            }
        )
        background_tasks.add_task(
            run_conversion_task,
            task_id=task_id,
            source_path=source_path,
            task_dir=task_dir,
            settings=settings,
        )
        return {"task_id": task_id, "status": "processing"}

    @router.get("/api/gif/tasks/{task_id}")
    def get_gif_task(task_id: str) -> dict[str, Any]:
        task = task_store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return _public_task_view(task)

    return router


def create_app(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    temp_dir: Path = DEFAULT_TEMP_DIR,
    task_store: GifTaskStore | None = None,
    converter: GifConverter | None = None,
    uuid_hex: Callable[[], str] | None = None,
) -> FastAPI:
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    task_store = task_store or GifTaskStore(DEFAULT_TASK_STORE)
    converter = converter or GifConverter()
    uuid_hex = uuid_hex or (lambda: uuid.uuid4().hex)
    app = FastAPI(title="Video to Meme GIF", version="0.1.0")
    app.include_router(
        create_gif_router(
            output_dir=output_dir,
            temp_dir=temp_dir,
            task_store=task_store,
            converter=converter,
            uuid_hex=uuid_hex,
        )
    )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/outputs/{filename}")
    def outputs(filename: str) -> FileResponse:
        return FileResponse(_safe_output_file(output_dir, filename), media_type="image/gif")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
