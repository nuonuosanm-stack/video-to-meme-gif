# First Open Source Release Plan

## Scope

This release extracts only the Toolbox Beta video-to-GIF workflow into a standalone app.
The original commercial workbench remains untouched.

## Included

- Local FastAPI app
- Static single-page UI
- Video upload and metadata probe
- GIF conversion through FFmpeg palette generation
- Fallback compression attempts
- JSON-backed task state
- Preview and download endpoints
- Focused service and API tests

## Excluded

- Login and registration
- Credits and billing
- Admin dashboard
- Recharge/payment pages
- AI providers
- COS/object storage
- Existing user data, history data, logs, and generated outputs

## Suggested GitHub Release Checklist

1. Copy `open_source/video-to-meme-gif` into a fresh repository.
2. Run `pytest tests -q`.
3. Start with `uvicorn gif_toolkit.app:app --host 127.0.0.1 --port 8503`.
4. Capture a screenshot and a small demo GIF.
5. Push as `v0.1.0`.

