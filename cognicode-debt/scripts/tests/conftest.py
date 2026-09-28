"""测试导入路径：把 cognicode-debt/scripts 挂到 sys.path，测试文件以
`from lib.symbols import ...` / `from scan import ...` 导入（脚本直跑
同形态：scan.py 也是这样找 lib 的）。
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
