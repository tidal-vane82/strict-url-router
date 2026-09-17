import sys
from pathlib import Path

# No editable install is assumed - point pytest at the src layout directly.
sys.path.insert(0, str(Path(__file__).parent / "src"))
