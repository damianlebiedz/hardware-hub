"""Hardware Hub backend package."""

from pathlib import Path

from dotenv import load_dotenv

# Load ``.env`` from the project root once the ``backend`` package is imported.
# Existing environment variables are not overridden (Docker / CI remain authoritative).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
