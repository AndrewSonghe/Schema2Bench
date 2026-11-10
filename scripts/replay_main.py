"""Recompute all five-method tables and ten releases from saved score intervals."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1] / "replay/main/replay.py"), run_name="__main__")
