"""Verify the saved binary assignment for the reference-risk comparison."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1] / "replay/witness/verify_witness.py"), run_name="__main__")
