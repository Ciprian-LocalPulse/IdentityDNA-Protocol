import sys
from pathlib import Path

_REF = Path(__file__).resolve().parents[2] / "reference"
for p in ["", "identity-engine", "trust-engine", "session-engine", "entropy-engine", "gateway", "verifier"]:
    sys.path.insert(0, str(_REF / p) if p else str(_REF))
