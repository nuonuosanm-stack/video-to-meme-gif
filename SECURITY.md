# Security Policy

## Supported Versions

Security reports should target the latest release on the `main` branch.

## Reporting a Vulnerability

Please do not open a public issue for a security vulnerability. Instead, contact
the maintainer privately through GitHub profile contact information, or open a
minimal public issue that says you need a private security contact without
including exploit details.

Useful details to include:

- Operating system and Python version.
- FFmpeg and FFprobe versions.
- The endpoint or setting involved.
- A minimal reproduction using a harmless test file when possible.
- Whether the issue involves path traversal, unsafe file handling, command
  construction, denial of service, dependency vulnerabilities, or output access.

## Security Scope

Areas that matter most for this project:

- Uploaded video validation.
- Safe temporary file handling and cleanup.
- Output path restrictions for `/outputs/{filename}`.
- FFmpeg and FFprobe subprocess argument construction.
- Resource limits for file size, source duration, clip duration, FPS, and width.
- Dependency updates for FastAPI, Pillow, and related packages.

The project builds FFmpeg commands as argument arrays rather than shell strings.
Please keep that property intact when changing conversion logic.

