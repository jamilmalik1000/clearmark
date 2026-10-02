import base64
import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app


def png_bytes(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_image_job_end_to_end() -> None:
    client = TestClient(app)
    image = np.full((80, 120, 3), 225, dtype=np.uint8)
    image[28:52, 42:78] = 20

    upload = client.post(
        "/api/jobs",
        files={"file": ("sample.png", png_bytes(image), "image/png")},
    )
    assert upload.status_code == 201
    job = upload.json()

    mask = np.zeros((80, 120, 4), dtype=np.uint8)
    mask[25:55, 39:81, 0] = 255
    mask[25:55, 39:81, 3] = 180
    mask_url = "data:image/png;base64," + base64.b64encode(png_bytes(mask)).decode("ascii")

    started = client.post(
        f"/api/jobs/{job['id']}/process",
        json={"mask_data_url": mask_url, "method": "telea", "radius": 3},
    )
    assert started.status_code == 202

    deadline = time.monotonic() + 5
    current = started.json()
    while current["status"] == "processing" and time.monotonic() < deadline:
        time.sleep(0.05)
        current = client.get(f"/api/jobs/{job['id']}").json()

    assert current["status"] == "complete", current.get("error")
    result = client.get(current["result_url"])
    assert result.status_code == 200
    decoded = cv2.imdecode(np.frombuffer(result.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded[40, 60].mean() > 100

    deleted = client.delete(f"/api/jobs/{job['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""

