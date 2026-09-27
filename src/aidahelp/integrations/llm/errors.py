"""模型适配层异常。"""


class ChatModelError(Exception):
    """所有模型调用错误的父类。"""


class ChatModelNotConfiguredError(ChatModelError):
    """选择了真实模型，但缺少 API Key 等必要配置。"""


class ChatModelUpstreamError(ChatModelError):
    """模型服务超时、返回错误状态或响应格式不正确。"""
