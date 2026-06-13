"""把 sidecar 根目录加进 sys.path，使测试能 `import keeper_engine`。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
