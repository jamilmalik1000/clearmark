from typing import Literal

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    mask_data_url: str = Field(min_length=20)
    method: Literal["telea", "ns"] = "telea"
    radius: float = Field(default=3.0, ge=1.0, le=20.0)


class JobResponse(BaseModel):
    id: str
    media_type: Literal["image", "video"]
    filename: str
    width: int
    height: int
    duration: float | None = None
    status: Literal["uploaded", "processing", "complete", "failed"]
    progress: float = 0
    error: str | None = None
    source_url: str
    preview_url: str
    result_url: str | None = None

