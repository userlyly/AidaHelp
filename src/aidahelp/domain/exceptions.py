"""业务异常。

业务层只抛出这些异常，不直接依赖 FastAPI 的 HTTPException；由 API 层统一转换成 HTTP 响应。
"""


class DomainError(Exception):
    """所有可预期业务错误的父类。"""

    code = "DOMAIN_ERROR"
    status_code = 400
    default_message = "业务处理失败"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class UserNotFoundError(DomainError):
    code = "USER_NOT_FOUND"
    status_code = 404
    default_message = "用户不存在"


class ConversationNotFoundError(DomainError):
    code = "CONVERSATION_NOT_FOUND"
    status_code = 404
    default_message = "会话不存在，或者当前用户无权访问"


class ConversationClosedError(DomainError):
    code = "CONVERSATION_CLOSED"
    status_code = 409
    default_message = "会话已经关闭，不能继续写入消息"


class ModelNotConfiguredError(DomainError):
    code = "MODEL_NOT_CONFIGURED"
    status_code = 503
    default_message = "聊天模型尚未配置"


class ModelUnavailableError(DomainError):
    code = "MODEL_UNAVAILABLE"
    status_code = 502
    default_message = "聊天模型暂时不可用，请稍后重试"


class KnowledgeIngestionError(DomainError):
    code = "KNOWLEDGE_INGESTION_FAILED"
    status_code = 500
    default_message = "知识文档入库失败"


class RetrievalUnavailableError(DomainError):
    code = "RETRIEVAL_UNAVAILABLE"
    status_code = 503
    default_message = "知识检索服务暂时不可用"


class AgentUnavailableError(DomainError):
    code = "AGENT_UNAVAILABLE"
    status_code = 503
    default_message = "Agent 工作流暂时不可用"


class PendingActionNotFoundError(DomainError):
    code = "PENDING_ACTION_NOT_FOUND"
    status_code = 409
    default_message = "当前会话没有等待确认的操作"


class AuthenticationError(DomainError):
    code = "AUTHENTICATION_REQUIRED"
    status_code = 401
    default_message = "登录状态无效或已经过期"


class AuthorizationError(DomainError):
    code = "FORBIDDEN"
    status_code = 403
    default_message = "当前身份无权访问该资源"


class UnsafeInputError(DomainError):
    code = "UNSAFE_INPUT"
    status_code = 400
    default_message = "请求包含高风险指令，已被安全策略拦截"


class RateLimitExceededError(DomainError):
    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    default_message = "请求过于频繁，请稍后再试"
