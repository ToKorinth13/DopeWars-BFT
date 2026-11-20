"""Rebuild the existing, original BFT icon instead of redistributing a beer logo."""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from PySide6.QtWidgets import QApplication
from app import make_icon, load_fonts

app = QApplication.instance() or QApplication([])
load_fonts()
icon = make_icon()
assert icon.pixmap(256, 256).save(str(root / 'logo.png'), 'PNG')
assert icon.pixmap(128, 128).save(str(root / 'bft.ico'), 'ICO')
