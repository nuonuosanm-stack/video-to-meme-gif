# Contributing

Thanks for helping improve Video to Meme GIF. This project is intentionally small:
it should stay easy to run locally, easy to understand, and privacy-friendly.

## Good First Contributions

- Improve setup documentation for Windows, macOS, or Linux.
- Add tests for edge cases in GIF settings or upload validation.
- Improve error messages when FFmpeg or FFprobe is missing.
- Improve accessibility and responsive behavior in the static UI.
- Add small, focused features that do not require third-party media uploads.

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest tests -q
```

Start the app:

```bash
uvicorn gif_toolkit.app:app --host 127.0.0.1 --port 8503
```

## Pull Request Checklist

Before opening a pull request:

- Run `pytest tests -q`.
- Keep changes focused on one topic.
- Avoid committing generated GIFs, local outputs, cache folders, or temporary files.
- Update `README.md` or `CHANGELOG.md` when behavior or setup changes.
- Explain why the change is useful and how it was tested.

## Project Boundaries

The core project should remain a local video-to-GIF tool. Features that upload
user media to third-party services, add accounts, or introduce payment flows are
outside the current scope.

