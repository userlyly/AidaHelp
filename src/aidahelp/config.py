"""应用配置。

所有配置都从环境变量读取，并集中放在一个对象中。这样业务代码不需要到处调用
``os.getenv``，也可以在应用启动时尽早发现端口、日志级别等配置错误。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]


class Settings(BaseSettings):
    """AidaHelp 的全局配置。

    ``env_prefix`` 表示字段 ``port`` 会读取环境变量 ``AIDAHELP_PORT``。
    生产环境通常由容器平台注入环境变量；本地开发则可以使用项目根目录的 ``.env``。
    """

    model_config = SettingsConfigDict(
        env_prefix="AIDAHELP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "AidaHelp"
    version: str = "0.1.0"
    environment: Environment = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    docs_enabled: bool = True

    # 业务数据使用 MySQL；测试会显式覆盖成临时 SQLite 数据库。
    database_url: str = "mysql+asyncmy://aidahelp:aidahelp@127.0.0.1:3307/aidahelp?charset=utf8mb4"
    database_echo: bool = False
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_pool_recycle: int = Field(default=1800, ge=60)
    database_connect_timeout: int = Field(default=5, ge=1, le=60)
    # 只允许测试环境开启。生产表结构必须由 Alembic 迁移管理。
    database_auto_create_schema: bool = False

    # mock 用来离线学习完整链路；openai_compatible 可连接 DeepSeek 等兼容服务。
    llm_provider: Literal["mock", "openai_compatible"] = "mock"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr | None = None
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_tokens: int = Field(default=512, ge=1, le=8192)
    llm_history_limit: int = Field(default=20, ge=1, le=100)

    # 阶段 4：Embedding 与 Milvus。更换真实 Embedding 模型时必须同步修改维度和集合名。
    embedding_provider: Literal["mock", "openai_compatible"] = "mock"
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: SecretStr | None = None
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = Field(default=256, ge=8, le=65536)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: SecretStr | None = None
    milvus_collection: str = "aidahelp_knowledge_v1"
    knowledge_chunk_size: int = Field(default=700, ge=100, le=8000)
    knowledge_chunk_overlap: int = Field(default=100, ge=0, le=2000)

    # 阶段 5：Dense/BM25 召回、RRF 融合、Reranker 和证据置信度。
    rerank_provider: Literal["mock", "openai_compatible"] = "mock"
    rerank_base_url: str = "https://api.siliconflow.cn/v1"
    rerank_api_key: SecretStr | None = None
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    retrieval_recall_top_k: int = Field(default=50, ge=1, le=200)
    retrieval_top_k: int = Field(default=10, ge=1, le=50)
    rerank_min_score: float = Field(default=0.30, ge=0, le=1)
    evidence_confidence_threshold: float = Field(default=0.26, ge=0, le=1)

    # 阶段 6～8：图执行、固定流程与上下文预算。
    agent_enabled: bool = True
    agent_max_steps: int = Field(default=6, ge=1, le=20)
    checkpointer_db_path: str = "data/checkpoints/aidahelp.sqlite"
    memory_recent_messages: int = Field(default=12, ge=2, le=100)
    memory_summary_trigger: int = Field(default=24, ge=4, le=500)
    memory_summary_max_chars: int = Field(default=2000, ge=200, le=10000)
    memory_message_max_chars: int = Field(default=3000, ge=200, le=20000)

    # 阶段 9：统一工具执行引擎和 MCP。MCP 某台不可用时只跳过该来源，不拖垮对话。
    tool_default_timeout: float = Field(default=5.0, gt=0, le=120)
    mcp_tool_timeout: float = Field(default=10.0, gt=0, le=120)
    tool_max_retries: int = Field(default=1, ge=0, le=5)
    tool_result_max_chars: int = Field(default=6000, ge=200, le=50000)
    mcp_logistics_url: str = "http://127.0.0.1:8101/mcp"
    mcp_aftersales_url: str = "http://127.0.0.1:8102/mcp"

    # 阶段 10：身份、接口防护和安全护栏。生产环境必须覆盖默认密钥并关闭 demo 登录。
    auth_enabled: bool = True
    auth_secret: SecretStr = SecretStr("change-me-before-production-aidahelp")
    auth_issuer: str = "aidahelp"
    auth_audience: str = "aidahelp-api"
    auth_token_ttl_minutes: int = Field(default=120, ge=5, le=10080)
    demo_auth_enabled: bool = True
    rate_limit_requests_per_minute: int = Field(default=30, ge=1, le=10000)
    max_request_body_bytes: int = Field(default=65536, ge=1024, le=10_485_760)
    cors_allowed_origins: str = ""
    guardrails_enabled: bool = True

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """统一 API 前缀格式，避免出现 ``api/v1`` 或 ``/api/v1/`` 两种写法。"""

        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("api_prefix 必须以 / 开头")
        if value != "/":
            value = value.rstrip("/")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """日志级别写错时直接阻止服务启动，而不是悄悄丢失日志。"""

        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level 必须是以下值之一：{sorted(allowed)}")
        return normalized

    @property
    def is_production(self) -> bool:
        """集中判断生产环境，后续可用于关闭调试信息和 API 文档。"""

        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """创建并缓存配置，保证一个进程内使用同一份配置快照。"""

    return Settings()
