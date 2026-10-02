from __future__ import annotations

import base64
import binascii
import shutil
import subprocess
from pathlib import Path
from typing import Callable

import cv2
import numpy as np


ProgressCallback = Callable[[float], None]


def decode_mask(data_url: str, width: int, height: int) -> np.ndarray:
    """Decode a browser canvas data URL into a binary OpenCV mask."""
    if "," not in data_url:
        raise ValueError("The mask is not a valid data URL.")

    header, encoded = data_url.split(",", 1)
    if "base64" not in header or "image/png" not in header:
        raise ValueError("The mask must be a base64-encoded PNG.")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The mask data is invalid.") from exc

    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("The mask image could not be decoded.")

    if image.ndim == 3 and image.shape[2] == 4:
        # The editor exports red paint on a transparent background, so alpha is
        # the most accurate source for the selected area.
        mask = image[:, :, 3]
    elif image.ndim == 3:
        mask = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        mask = image

    mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
    _, mask = cv2.threshold(mask, 8, 255, cv2.THRESH_BINARY)
    if cv2.countNonZero(mask) == 0:
        raise ValueError("Paint over at least one area before processing.")
    return mask


def inpaint_frame(frame: np.ndarray, mask: np.ndarray, method: str, radius: float) -> np.ndarray:
    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    return cv2.inpaint(frame, mask, radius, flag)


def process_image(
    source: Path,
    output: Path,
    mask_data_url: str,
    method: str,
    radius: float,
    progress: ProgressCallback,
) -> None:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded image could not be read.")
    mask = decode_mask(mask_data_url, image.shape[1], image.shape[0])
    progress(25)
    result = inpaint_frame(image, mask, method, radius)
    progress(80)
    if not cv2.imwrite(str(output), result):
        raise RuntimeError("The processed image could not be saved.")
    progress(100)


def process_video(
    source: Path,
    output: Path,
    mask_data_url: str,
    method: str,
    radius: float,
    progress: ProgressCallback,
) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError("The uploaded video could not be opened.")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if width <= 0 or height <= 0:
        capture.release()
        raise ValueError("The video dimensions are invalid.")
    if not fps or fps <= 0 or fps > 240:
        fps = 30.0

    mask = decode_mask(mask_data_url, width, height)
    silent_output = output.with_name(f"{output.stem}.silent.mp4")
    writer = cv2.VideoWriter(
        str(silent_output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("The video encoder could not be started.")

    processed = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            writer.write(inpaint_frame(frame, mask, method, radius))
            processed += 1
            if processed % 3 == 0:
                if frame_count > 0:
                    progress(min(92.0, processed / frame_count * 92.0))
                else:
                    progress(min(92.0, processed / (processed + 30) * 92.0))
    finally:
        capture.release()
        writer.release()

    if processed == 0:
        silent_output.unlink(missing_ok=True)
        raise ValueError("No video frames could be decoded.")

    progress(94)
    if not _mux_original_audio(source, silent_output, output):
        shutil.move(str(silent_output), str(output))
    else:
        silent_output.unlink(missing_ok=True)
    progress(100)


def _mux_original_audio(source: Path, video_only: Path, output: Path) -> bool:
    """Mux the source audio when FFmpeg exists; return False on any failure."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_only),
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1800,
            check=False,
        )
        succeeded = completed.returncode == 0 and output.exists() and output.stat().st_size > 0
        if not succeeded:
            output.unlink(missing_ok=True)
        return succeeded
    except (OSError, subprocess.TimeoutExpired):
        output.unlink(missing_ok=True)
        return False

