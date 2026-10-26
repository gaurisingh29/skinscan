# Pre-publication test prompt

Copy this prompt into your coding assistant when you want an independent QA pass:

> Act as a careful QA engineer reviewing the `skincare-advisor` app before publication. First inspect the README, frontend, backend, and existing tests. Do not make any real OpenAI API requests, do not use real face/health images, and never reveal or print environment variables or secrets.
>
> Run the existing backend tests and frontend production build. Add or run safe tests using mocked provider responses for:
> - API health and the successful analysis response shape.
> - Missing API key, unsupported MIME type, mismatched image signature, empty file, and the 10 MB upload limit.
> - Actionable handling for provider authentication, permission/model, quota/rate-limit, connection, and temporary service errors.
> - Frontend photo selection, replacement/removal, required OpenAI consent, disabled/loading states, error display, and rendering each analysis section.
>
> Check that the API key is only read by the backend, `.env` files are ignored, uploads are not written to disk, errors/logs never include keys or image contents, and the UI clearly says the image is sent to OpenAI and the result is not medical advice. Review keyboard/screen-reader access and mobile layout.
>
> Fix only confirmed issues, add regression tests for fixes, and rerun the relevant checks. End with a concise report of tests passed/failed, remaining risks, and production blockers. Do not claim medical accuracy or call the app production-ready without addressing HTTPS, authentication, rate limiting, provider data handling, privacy obligations, and deployment configuration.
