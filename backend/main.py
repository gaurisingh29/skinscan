import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, APIError, APIStatusError, OpenAI
from pydantic import BaseModel, Field, ValidationError


load_dotenv(Path(__file__).with_name(".env"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Skincare Advisor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/x-png",
    "image/webp",
    "image/jfif",
    "image/bmp",
    "image/gif",
}

IMAGE_SIGNATURES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8"),
    "image/jpg": lambda data: data.startswith(b"\xff\xd8"),
    "image/pjpeg": lambda data: data.startswith(b"\xff\xd8"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/x-png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda data: (
        len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    ),
    "image/jfif": lambda data: data.startswith(b"\xff\xd8"),
    "image/bmp": lambda data: data.startswith(b"BM"),
    "image/gif": lambda data: data.startswith(b"GIF87a") or data.startswith(b"GIF89a"),
}


def detect_and_validate_image(content_type: Optional[str], data: bytes) -> str:
    """Validate and return canonical MIME type from data bytes or content-type."""
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    # 1. Byte signature checks
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"BM"):
        return "image/bmp"

    # 2. Check if content_type is provided and valid
    if content_type:
        clean_type = content_type.split(";")[0].strip().lower()
        if clean_type in IMAGE_SIGNATURES:
            if IMAGE_SIGNATURES[clean_type](data):
                return clean_type
            raise HTTPException(
                status_code=415,
                detail="The image contents do not match the selected file type.",
            )

    raise HTTPException(
        status_code=415,
        detail="Upload a JPEG, PNG, or WebP image.",
    )


def provider_error_detail(status_code: int) -> str:
    if status_code == 400:
        return "OpenAI rejected the image or request. Try a different photo."
    if status_code == 401:
        return "OpenAI rejected the API key. Check OPENAI_API_KEY in your environment."
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
    return f"OpenAI returned HTTP {status_code}. Check backend logs and try again."


class SkinAnalysis(BaseModel):
    summary: str = Field(default="Skin analysis completed.")
    skin_type_guess: str = Field(default="Balanced / Normal")
    concerns: list[str] = Field(default_factory=list)
    morning_routine: list[str] = Field(default_factory=list)
    evening_routine: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    professional_care: str = Field(
        default="Consult a dermatologist for persistent or severe skin concerns."
    )


SYSTEM_PROMPT = (
    "You are an expert cosmetic skincare consultant and aesthetician. "
    "Carefully analyze visible surface skin attributes in the user's uploaded photo. "
    "Identify observable cosmetic characteristics such as surface texture, visible pores, "
    "shine/oiliness (e.g. in the T-zone), dry/flaky patches, visible redness or flush, "
    "blemishes or congestion, and uneven pigmentation or dark spots. "
    "Then formulate practical, gentle, everyday skincare recommendations tailored to the observed skin traits. "
    "Return ONLY a valid JSON object with the following schema: "
    "{\n"
    '  "summary": "2-3 sentences summarizing the overall visible condition and prominent traits",\n'
    '  "skin_type_guess": "e.g. Combination, Oily, Dry, Normal, or Sensitive",\n'
    '  "concerns": ["Observable trait 1", "Observable trait 2", ...],\n'
    '  "morning_routine": ["Step 1: Cleanser...", "Step 2: Hydration...", "Step 3: Moisturizer...", "Step 4: Sunscreen SPF 50+"],\n'
    '  "evening_routine": ["Step 1: Cleanse...", "Step 2: Gentle active or treatment...", "Step 3: Barrier moisturizer..."],\n'
    '  "cautions": ["Important cautions regarding sensitive areas, patch tests, and sun protection"],\n'
    '  "professional_care": "When to consult a dermatologist (e.g. persistent cysts, pain, or changing lesions)"\n'
    "}"
)


def extract_json_content(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=SkinAnalysis)
async def analyze_skin(image: UploadFile = File(...)) -> SkinAnalysis:
    content_type = (image.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, or WebP image.",
        )

    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")

    canonical_type = detect_and_validate_image(content_type, image_bytes)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in backend/.env before requesting an analysis.",
        )

    data_url = (
        f"data:{canonical_type};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )
    client = OpenAI(api_key=api_key)
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")

    try:
        response = client.chat.completions.create(
            model=model_name,
            response_format={"type": "json_object"},
            max_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please inspect visible skin features and provide cosmetic recommendations "
                                "in the requested JSON format."
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

    raw_content = response.choices[0].message.content

    try:
        parsed_data = extract_json_content(raw_content)
        return SkinAnalysis.model_validate(parsed_data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Failed to parse OpenAI response: %s", raw_content)
        raise HTTPException(
            status_code=502,
            detail="The analysis provider returned an unexpected response.",
        ) from exc
