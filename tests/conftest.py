import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if importlib.util.find_spec("tkinter") is None:
    for name in ("tkinter", "tkinter.ttk", "tkinter.messagebox"):
        sys.modules[name] = MagicMock()
