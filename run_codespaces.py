import os
from waitress import serve
from app import app


def main():
    port = int(os.environ.get("PORT", "8000"))
    print("=" * 62)
    print("AUTO REVIEW VIDEO - GITHUB CODESPACES")
    print(f"Listening on 0.0.0.0:{port}")
    print("Open the forwarded port from the Codespaces Ports tab.")
    print("=" * 62)
    serve(app, host="0.0.0.0", port=port, threads=8)


if __name__ == "__main__":
    main()
