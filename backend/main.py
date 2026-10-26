import base64
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, APIError, APIStatusError, OpenAI
from pydantic import BaseModel, ValidationError


load_dotenv(Path(__file__).with_name(".env"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Skincare Advisor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_SIGNATURES = {
    "image/jpeg": lambda image: image.startswith(b"\xff\xd8\xff"),
    "image/png": lambda image: image.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda image: (
        len(image) >= 12 and image[:4] == b"RIFF" and image[8:12] == b"WEBP"
    ),
}


def provider_error_detail(status_code: int) -> str:
    if status_code == 400:
        return "OpenAI rejected the image or request. Try a different, smaller photo."
    if status_code == 401:
        return "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env."
    if status_code == 403:
        return "This OpenAI project may not have access to the requested model."
    if status_code == 404:
        return "The requested OpenAI model is unavailable for this API project."
    if status_code == 413:
        return "OpenAI rejected the image because the request was too large."
    if status_code == 429:
        return "OpenAI rate or usage limits were reached. Check project billing and limits."
    if status_code >= 500:
        return "OpenAI is temporarily unavailable. Please try again later."
    return f"OpenAI returned HTTP {status_code}. Check the backend logs and try again."


class SkinAnalysis(BaseModel):
    summary: str
    skin_type_guess: str
    concerns: list[str]
    morning_routine: list[str]
    evening_routine: list[str]
    cautions: list[str]
    professional_care: str


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=SkinAnalysis)
async def analyze_skin(image: UploadFile = File(...)) -> SkinAnalysis:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, or WebP image.",
        )

    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if not IMAGE_SIGNATURES[image.content_type](image_bytes):
        raise HTTPException(
            status_code=415,
            detail="The image contents do not match the selected file type.",
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in backend/.env before requesting an analysis.",
        )

    data_url = (
        f"data:{image.content_type};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            max_tokens=900,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Offer cautious, general cosmetic skincare guidance from the "
                        "visible image only. Do not diagnose or claim certainty about "
                        "a condition, skin type, or demographic traits. Mention image "
                        "limitations, favor gentle and broadly suitable habits, avoid "
                        "prescription treatments, and recommend a dermatologist for "
                        "persistent, painful, severe, or concerning changes. Return "
                        "only JSON with string fields summary, skin_type_guess, "
                        "professional_care and array-of-string fields concerns, "
                        "morning_routine, evening_routine, cautions. If the image "
                        "doesn't clearly show skin, say so and keep suggestions general."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe only visible skin observations and provide "
                                "a simple, cautious routine. Do not identify the person."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "high"},
                        },
                    ],
                },
            ],
        )
    except APIStatusError as exc:
        logger.warning(
            "OpenAI image analysis failed with HTTP %s (request_id=%s)",
            exc.status_code,
            exc.request_id,
        )
        raise HTTPException(
            status_code=502,
            detail=provider_error_detail(exc.status_code),
        ) from exc
    except APIConnectionError as exc:
        logger.warning("Could not connect to OpenAI for image analysis.")
        raise HTTPException(
            status_code=502,
            detail="Could not connect to OpenAI. Check the backend network and retry.",
        ) from exc
    except APIError as exc:
        logger.warning(
            "OpenAI SDK error during image analysis (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned an unexpected API error. Check the backend logs.",
        ) from exc

    if not response.choices or not response.choices[0].message.content:
        raise HTTPException(status_code=502, detail="The analysis returned no result.")
    content = response.choices[0].message.content

    try:
        return SkinAnalysis.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="The analysis provider returned an unexpected response.",
        ) from exc
