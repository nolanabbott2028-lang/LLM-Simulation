#!/usr/bin/env python3
"""Download the configured Ollama model locally. Requires the Ollama app or CLI and a running server when you play."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from config import OLLAMA_MODEL

# macOS: PATH is often empty in GUI apps; Homebrew, Mac app bundle, and /usr/local are common
_CANDIDATES = (
    "ollama",
    "/opt/homebrew/bin/ollama",
    "/usr/local/bin/ollama",
    os.path.expanduser("~/bin/ollama"),
    # Ollama Mac app (see https://ollama.com — CLI may live inside the .app)
    "/Applications/Ollama.app/Contents/Resources/ollama",
    "/Applications/Ollama.app/Contents/MacOS/ollama",
)


def _find_ollama() -> str | None:
    w = shutil.which("ollama")
    if w:
        return w
    for c in _CANDIDATES:
        if c == "ollama":
            continue
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def main() -> None:
    exe = _find_ollama()
    if not exe:
        print(
            "Ollama CLI not found. The game still runs with built-in sim behavior (no local LLM).\n\n"
            "To add Ollama later:\n"
            "  1. Install: https://ollama.com  (or: brew install ollama)\n"
            "  2. Open the Ollama app, or start the server in a terminal: ollama serve\n"
            "  3. Run again: python3 setup_ollama.py\n"
            "Each line in step 2–3 is one command; do not run lines that start with #.",
            file=sys.stderr,
        )
        sys.exit(0)

    print(f"Using {exe!r} — pulling model {OLLAMA_MODEL!r} …", flush=True)
    p = subprocess.run([exe, "pull", OLLAMA_MODEL], check=False)
    if p.returncode != 0:
        print("Pull failed. Start the Ollama app or run `ollama serve`, then try again.", file=sys.stderr)
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
