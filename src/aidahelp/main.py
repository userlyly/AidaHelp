"""ASGI 入口。

Uvicorn 会导入这个模块中的 ``app``。实际装配逻辑放在 bootstrap.py，保持入口简单。
"""

from aidahelp.bootstrap import create_app

app = create_app()
