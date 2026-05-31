from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


MAX_VIDEO_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_SOURCE_DURATION_SECONDS = 180
MAX_CLIP_DURATION_SECONDS = 5
DEFAULT_TARGET_BYTES = 1024 * 1024
QUALITY_COLORS = {
    "small": 96,
    "standard": 128,
    "high": 192,
}
FALLBACK_ATTEMPTS = [
    {"width": 480, "fps": 12, "colors": 128},
    {"width": 360, "fps": 10, "colors": 96},
    {"width": 320, "fps": 8, "colors": 96},
    {"width": 240, "fps": 8, "colors": 64},
    {"width": 200, "fps": 6, "colors": 64},
]


class GifConversionError(ValueError):
    pass


@dataclass(frozen=True)
class GifSettings:
    start_time: float
    duration: float
    width: int
    fps: int
    speed: float
    target_size: int
    quality_mode: str
    crop_mode: str = "full"
    crop_x: float = 0.0
    crop_y: float = 0.0
    crop_w: float = 1.0
    crop_h: float = 1.0


@dataclass(frozen=True)
class GifConversionResult:
    output_path: Path
    file_size: int
    duration: float
    width: int
    fps: int
    colors: int
    attempts: int


def _float_value(value: Any, fallback: float, label: str) -> float:
    try:
        return float(value if value not in {None, ""} else fallback)
    except (TypeError, ValueError) as exc:
        raise GifConversionError(f"{label} must be a number") from exc


def _int_value(value: Any, fallback: int, label: str) -> int:
    try:
        return int(float(value if value not in {None, ""} else fallback))
    except (TypeError, ValueError) as exc:
        raise GifConversionError(f"{label} must be an integer") from exc


def parse_gif_settings(
    *,
    start_time: Any = 0,
    duration: Any = 3,
    width: Any = 320,
    fps: Any = 8,
    speed: Any = 1,
    target_size: Any = DEFAULT_TARGET_BYTES,
    quality_mode: str = "standard",
    crop_mode: str = "full",
    crop_x: Any = 0,
    crop_y: Any = 0,
    crop_w: Any = 1,
    crop_h: Any = 1,
) -> GifSettings:
    clean_quality = str(quality_mode or "standard").strip().lower()
    if clean_quality not in QUALITY_COLORS:
        raise GifConversionError("quality_mode must be small, standard, or high")

    clean_start = _float_value(start_time, 0, "start_time")
    clean_duration = _float_value(duration, 3, "duration")
    clean_width = _int_value(width, 320, "width")
    clean_fps = _int_value(fps, 8, "fps")
    clean_speed = _float_value(speed, 1, "speed")
    clean_target = _int_value(target_size, DEFAULT_TARGET_BYTES, "target_size")

    if clean_start < 0:
        raise GifConversionError("start_time cannot be below 0")
    if clean_duration <= 0:
        raise GifConversionError("duration must be greater than 0")
    if clean_duration > MAX_CLIP_DURATION_SECONDS:
        raise GifConversionError("duration cannot exceed 5 seconds")
    if clean_width < 160 or clean_width > 720:
        raise GifConversionError("width must be between 160 and 720")
    if clean_fps < 4 or clean_fps > 20:
        raise GifConversionError("fps must be between 4 and 20")
    if clean_speed < 0.5 or clean_speed > 2:
        raise GifConversionError("speed must be between 0.5 and 2")
    if clean_target <= 0 or clean_target > 5 * 1024 * 1024:
        raise GifConversionError("target_size must be between 1 byte and 5MB")

    clean_crop_mode = str(crop_mode or "full").strip().lower()
    if clean_crop_mode not in {"full", "square", "custom"}:
        raise GifConversionError("crop_mode must be full, square, or custom")
    clean_crop_x = _float_value(crop_x, 0, "crop_x")
    clean_crop_y = _float_value(crop_y, 0, "crop_y")
    clean_crop_w = _float_value(crop_w, 1, "crop_w")
    clean_crop_h = _float_value(crop_h, 1, "crop_h")
    if clean_crop_mode == "custom":
        if clean_crop_x < 0 or clean_crop_x >= 1:
            raise GifConversionError("crop_x must be between 0 and 1")
        if clean_crop_y < 0 or clean_crop_y >= 1:
            raise GifConversionError("crop_y must be between 0 and 1")
        if clean_crop_w < 0.05 or clean_crop_w > 1:
            raise GifConversionError("crop_w must be between 0.05 and 1")
        if clean_crop_h < 0.05 or clean_crop_h > 1:
            raise GifConversionError("crop_h must be between 0.05 and 1")
        if clean_crop_x + clean_crop_w > 1.000001:
            raise GifConversionError("crop region cannot exceed the right edge")
        if clean_crop_y + clean_crop_h > 1.000001:
            raise GifConversionError("crop region cannot exceed the bottom edge")
    else:
        clean_crop_x, clean_crop_y, clean_crop_w, clean_crop_h = 0.0, 0.0, 1.0, 1.0

    return GifSettings(
        start_time=clean_start,
        duration=clean_duration,
        width=clean_width,
        fps=clean_fps,
        speed=clean_speed,
        target_size=clean_target,
        quality_mode=clean_quality,
        crop_mode=clean_crop_mode,
        crop_x=clean_crop_x,
        crop_y=clean_crop_y,
        crop_w=clean_crop_w,
        crop_h=clean_crop_h,
    )


def _fmt_number(value: float | int) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _video_filter(settings: GifSettings) -> str:
    parts = []
    if abs(settings.speed - 1) > 0.001:
        parts.append(f"setpts=PTS/{_fmt_number(settings.speed)}")
    if settings.crop_mode == "square":
        parts.append("crop=min(iw\\,ih):min(iw\\,ih):(iw-min(iw\\,ih))/2:(ih-min(iw\\,ih))/2")
    elif settings.crop_mode == "custom":
        parts.append(
            "crop="
            f"iw*{_fmt_number(settings.crop_w)}:"
            f"ih*{_fmt_number(settings.crop_h)}:"
            f"iw*{_fmt_number(settings.crop_x)}:"
            f"ih*{_fmt_number(settings.crop_y)}"
        )
    parts.extend([f"fps={settings.fps}", f"scale={settings.width}:-1:flags=lanczos"])
    return ",".join(parts)


def build_ffmpeg_commands(
    input_path: Path,
    palette_path: Path,
    output_path: Path,
    settings: GifSettings,
    *,
    colors: int,
) -> tuple[list[str], list[str]]:
    filter_chain = _video_filter(settings)
    palette_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        _fmt_number(settings.start_time),
        "-t",
        _fmt_number(settings.duration),
        "-i",
        str(input_path),
        "-vf",
        f"{filter_chain},palettegen=max_colors={int(colors)}",
        str(palette_path),
    ]
    gif_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        _fmt_number(settings.start_time),
        "-t",
        _fmt_number(settings.duration),
        "-i",
        str(input_path),
        "-i",
        str(palette_path),
        "-filter_complex",
        f"{filter_chain}[x];[x][1:v]paletteuse=dither=bayer",
        str(output_path),
    ]
    return palette_cmd, gif_cmd


def compression_attempts(settings: GifSettings) -> list[dict[str, int]]:
    requested = {
        "width": settings.width,
        "fps": settings.fps,
        "colors": QUALITY_COLORS[settings.quality_mode],
    }
    attempts: list[dict[str, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for item in [requested, *FALLBACK_ATTEMPTS]:
        clean = {
            "width": max(160, min(720, int(item["width"]))),
            "fps": max(4, min(20, int(item["fps"]))),
            "colors": max(32, min(256, int(item["colors"]))),
        }
        key = (clean["width"], clean["fps"], clean["colors"])
        if key in seen:
            continue
        seen.add(key)
        attempts.append(clean)
    return attempts


class GifConverter:
    def __init__(self, *, run_command: Callable[..., Any] | None = None, timeout_seconds: int = 60) -> None:
        self.run_command = run_command or subprocess.run
        self.timeout_seconds = timeout_seconds

    def _run(self, command: list[str]) -> Any:
        try:
            return self.run_command(command, check=True, capture_output=True, text=True, timeout=self.timeout_seconds)
        except FileNotFoundError as exc:
            raise GifConversionError("FFmpeg or FFprobe is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise GifConversionError("GIF generation timed out; shorten the clip or lower the settings") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise GifConversionError(f"FFmpeg failed: {detail[:300] or exc}") from exc

    def probe(self, source_path: Path) -> dict[str, float | int]:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration:format=duration",
            "-of",
            "json",
            str(source_path),
        ]
        result = self._run(command)
        try:
            payload = json.loads(getattr(result, "stdout", "") or "{}")
        except json.JSONDecodeError as exc:
            raise GifConversionError("Could not read video metadata") from exc
        streams = payload.get("streams") if isinstance(payload, dict) else []
        stream = streams[0] if isinstance(streams, list) and streams else {}
        fmt = payload.get("format") if isinstance(payload, dict) else {}
        duration = float(stream.get("duration") or fmt.get("duration") or 0)
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        if duration <= 0:
            raise GifConversionError("Could not read video duration")
        return {"duration": duration, "width": width, "height": height}

    def convert(self, source_path: Path, output_dir: Path, settings: GifSettings) -> GifConversionResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        last_path: Path | None = None
        for index, attempt in enumerate(compression_attempts(settings), start=1):
            attempt_settings = GifSettings(
                start_time=settings.start_time,
                duration=settings.duration,
                width=attempt["width"],
                fps=attempt["fps"],
                speed=settings.speed,
                target_size=settings.target_size,
                quality_mode=settings.quality_mode,
                crop_mode=settings.crop_mode,
                crop_x=settings.crop_x,
                crop_y=settings.crop_y,
                crop_w=settings.crop_w,
                crop_h=settings.crop_h,
            )
            palette_path = output_dir / f"palette_{index}.png"
            output_path = output_dir / f"clip_{index}.gif"
            palette_cmd, gif_cmd = build_ffmpeg_commands(
                source_path,
                palette_path,
                output_path,
                attempt_settings,
                colors=attempt["colors"],
            )
            self._run(palette_cmd)
            self._run(gif_cmd)
            if not output_path.exists():
                raise GifConversionError("FFmpeg did not create a GIF file")
            size = output_path.stat().st_size
            if last_path and last_path.exists() and last_path != output_path:
                last_path.unlink(missing_ok=True)
            last_path = output_path
            if size <= settings.target_size:
                return GifConversionResult(
                    output_path=output_path,
                    file_size=size,
                    duration=settings.duration,
                    width=attempt["width"],
                    fps=attempt["fps"],
                    colors=attempt["colors"],
                    attempts=index,
                )

        raise GifConversionError(
            "The clip is too complex to compress under the target size. "
            "Shorten the duration, reduce width, or lower FPS."
        )

