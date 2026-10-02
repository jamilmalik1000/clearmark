import base64

import cv2
import numpy as np
import pytest

from app.processing import decode_mask, inpaint_frame


def make_data_url(image: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return "data:image/png;base64," + base64.b64encode(encoded).decode("ascii")


def test_decode_mask_uses_alpha_and_resizes() -> None:
    rgba = np.zeros((10, 10, 4), dtype=np.uint8)
    rgba[2:5, 3:7, 0] = 255
    rgba[2:5, 3:7, 3] = 180
    mask = decode_mask(make_data_url(rgba), 20, 20)
    assert mask.shape == (20, 20)
    assert cv2.countNonZero(mask) > 0
    assert set(np.unique(mask)).issubset({0, 255})


def test_decode_mask_rejects_empty_selection() -> None:
    empty = np.zeros((8, 8, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="Paint over"):
        decode_mask(make_data_url(empty), 8, 8)


def test_inpaint_frame_replaces_marked_pixels() -> None:
    image = np.full((40, 40, 3), 230, dtype=np.uint8)
    image[15:25, 15:25] = 0
    mask = np.zeros((40, 40), dtype=np.uint8)
    mask[13:27, 13:27] = 255
    result = inpaint_frame(image, mask, "telea", 3)
    assert result.shape == image.shape
    assert result[20, 20].mean() > 100

