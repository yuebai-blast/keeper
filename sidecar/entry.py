"""PyInstaller 冻结入口：直接调用 sidecar 的 main()。

冻结后没有 `-m` 概念，故用显式入口。命令行参数（--host/--port）仍透传。
"""
from keeper_engine.main import main

if __name__ == "__main__":
    main()
