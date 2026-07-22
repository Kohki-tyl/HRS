"""pytest の共通設定

.code をルートに置いたまま `domain` / `application` / `infrastructure` を
トップレベルパッケージとして import できるようにする。これがないと
`pytest tests/...` と直接実行したときに import に失敗する。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
