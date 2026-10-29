# Auto Review Video — Fashion Review Studio

Source code for the local Auto Review Video editor.

## Test on GitHub first

Every push to `main` runs **GitHub Actions** before a Windows package is produced:

- Windows / Python 3.12 core dependency install
- Python syntax checks
- Flask + FFmpeg smoke test
- Frontend JavaScript syntax check
- VieNeu environment test on Windows / Python 3.11

Open the **Actions** tab in this repository and check **Auto Review CI**. A green workflow means the automated smoke tests passed.

> GitHub Pages cannot run this app because the editor requires a Python backend, FFmpeg, local file access, and VieNeu. GitHub Actions can test the source automatically; interactive video editing remains a local/Codespaces workflow.

## Local run

On Windows, run:

```bat
INSTALL_AND_RUN.bat
```

The editor opens in your browser on localhost.

## Runtime layout

- Core editor: Python 3.12
- VieNeu environment: separate Python 3.11 environment
- FFmpeg: provided through `imageio-ffmpeg`
- Generated media and local caches are ignored by Git
