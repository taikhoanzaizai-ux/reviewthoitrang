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

## Run interactively with GitHub Codespaces

1. Open this repository on GitHub.
2. Click **Code**.
3. Open the **Codespaces** tab.
4. Click **Create codespace on main**.
5. The dev container installs the core editor and the separate VieNeu environment automatically.
6. Port **8000** is forwarded as **Auto Review Video** and is configured to open in the browser automatically.
7. If the browser does not open, open the **Ports** tab in Codespaces and click the globe/open-browser icon for port **8000**.

The Codespaces runner uses `run_codespaces.py` and listens on `0.0.0.0:8000`. The normal Windows launcher remains unchanged.

Notes:

- Video/audio files selected in the Codespaces browser are uploaded to that Codespace session, not to your Windows PC backend.
- FFmpeg is supplied through `imageio-ffmpeg`.
- VieNeu dependencies are installed in `data/ai/.venv`; model downloads happen when VieNeu first needs them, so first voice generation can take longer.
- Codespaces is intended for testing the web editor and backend before packaging the Windows build.

## Local run

On Windows, run:

```bat
INSTALL_AND_RUN.bat
```

The editor opens in your browser on localhost.

## Runtime layout

- Core editor: Python 3.12
- VieNeu environment: separate Python 3.11 environment on Windows; Codespaces uses its own isolated venv compatibility layer
- FFmpeg: provided through `imageio-ffmpeg`
- Generated media and local caches are ignored by Git
