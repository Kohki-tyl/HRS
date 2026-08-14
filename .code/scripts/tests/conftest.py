"""pytest の共通設定

.code を `sys.path` に追加し、`domain` / `application` / `infrastructure` を
トップレベルパッケージとして import できるようにする。
"""
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT))
