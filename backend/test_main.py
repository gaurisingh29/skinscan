import asyncio
import json
import os
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from fastapi import HTTPException
import httpx2
from openai import APIStatusError
from starlette.datastructures import Headers, UploadFile

import main


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def upload(content: bytes, media_type: str = "image/png") -> UploadFile:
    return UploadFile(
        filename="photo.png",
        file=BytesIO(content),
        headers=Headers({"content-type": media_type}),
    )


class AnalyzeSkinTests(unittest.TestCase):
    def test_provider_error_messages_are_actionable(self) -> None:
        self.assertIn("API key", main.provider_error_detail(401))
        self.assertIn("billing", main.provider_error_detail(429))
        self.assertIn("temporarily unavailable", main.provider_error_detail(503))

    def test_provider_quota_error_is_actionable_and_does_not_leak_body(self) -> None:
        response = httpx2.Response(
            429,
            request=httpx2.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
        provider_error = APIStatusError(
            "provider error",
            response=response,
            body={"error": {"message": "private provider response"}},
        )

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            patch.object(main, "OpenAI") as openai,
        ):
            openai.return_value.chat.completions.create.side_effect = provider_error
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    main.analyze_skin(upload(PNG_SIGNATURE + b"image data"))
                )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("billing and limits", raised.exception.detail)
        self.assertNotIn("private provider response", raised.exception.detail)

    def test_rejects_mime_type_that_is_not_allowed(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.analyze_skin(upload(b"not an image", "text/plain")))
        self.assertEqual(raised.exception.status_code, 415)

    def test_rejects_image_with_mismatched_signature(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.analyze_skin(upload(b"not a PNG")))
        self.assertEqual(raised.exception.status_code, 415)

    def test_rejects_oversized_image(self) -> None:
        oversized = b"\x00" * (main.MAX_IMAGE_BYTES + 1)
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.analyze_skin(upload(oversized)))
        self.assertEqual(raised.exception.status_code, 413)

    def test_requires_provider_key_before_analysis(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_skin(upload(PNG_SIGNATURE + b"image data")))
        self.assertEqual(raised.exception.status_code, 503)

    def test_returns_mocked_analysis_without_network_access(self) -> None:
        expected = {
            "summary": "Only a limited visual observation.",
            "skin_type_guess": "Not clear from image",
            "concerns": ["Some visible redness"],
            "morning_routine": ["Use a gentle cleanser"],
            "evening_routine": ["Moisturize"],
            "cautions": ["This is not a diagnosis"],
            "professional_care": "Consult a dermatologist for persistent concerns.",
        }
        mocked_response = Mock(
            choices=[Mock(message=Mock(content=json.dumps(expected)))]
        )

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            patch.object(main, "OpenAI") as openai,
        ):
            openai.return_value.chat.completions.create.return_value = mocked_response
            result = asyncio.run(
                main.analyze_skin(upload(PNG_SIGNATURE + b"image data"))
            )

        self.assertEqual(result.model_dump(), expected)
        openai.return_value.chat.completions.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
