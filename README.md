# AidaHelp

AidaHelp 是一个用于学习和展示的企业级客服 Agent Demo。项目会从一个最小可运行的
FastAPI 服务开始，逐步加入知识库、混合检索、LangGraph 工作流、多轮记忆、Tool、MCP、
安全审核、全链路追踪和自动化评测。

## 当前进度：阶段 10——权限安全与可交互客服前端

阶段 1 已经完成 FastAPI、配置、结构化日志、`trace_id` 和统一异常响应。
阶段 2 完成 MySQL 业务数据持久化，阶段 3 完成基础聊天闭环。阶段 4、5 新增：

- MySQL 8.4 开发环境；
- SQLAlchemy 2.0 异步连接池和请求级 Session；
- Alembic 数据库版本迁移；
- 用户、会话、消息、知识文档、知识 Chunk 五张表；
- Repository 数据访问层和 Service 事务层；
- 创建会话、查询会话和查询消息接口；
- 用户级会话数据隔离；
- MySQL 就绪检查；
- 可重复执行的演示数据脚本；
- SQLite 自动化测试和可选的真实 MySQL 集成测试。
- 与厂商无关的 ChatModel 协议；
- 无需密钥的 Mock 客服模型；
- DeepSeek 等 OpenAI Chat Completions 兼容模型适配器；
- 基础聊天接口；
- 自动创建或复用会话；
- 保存用户原文和 Assistant 回答；
- 读取最近若干条消息作为基础多轮上下文；
- 保存模型名称、上游请求 ID 和 Token 用量。
- Markdown、TXT、PDF、DOCX、XLSX、PPTX 文档加载；
- 文本标准化、章节解析、递归切块和重叠窗口；
- Mock Hash Embedding 和真实 OpenAI 兼容 Embedding；
- MySQL 原文/Chunk 与 Milvus 向量双写；
- `pending/indexed/failed` 可重试索引状态；
- Milvus Dense 语义召回与原生 BM25 关键词召回；
- RRF 双路结果融合；
- Mock/真实 Reranker 精排；
- Dense 与 BM25 使用不同改写文本；
- 证据置信度与低置信标记。

当前是单企业客服系统，不包含租户表。聊天接口已经统一进入 LangGraph，根据意图自动选择
知识检索、业务 Agent、退款固定流程或人工工单流程。

## 阶段 6：LangGraph Workflow 与 ReAct

`src/aidahelp/agent/` 将“理解问题、检索、生成、调用工具”拆成显式节点。业务查询进入
`agent → tools → agent` 循环，并由 `AIDAHELP_AGENT_MAX_STEPS` 限制最大循环次数。
`conversation_id` 同时作为 LangGraph `thread_id`，SQLite Checkpointer 只保存图运行现场；
MySQL 仍保存可审计的业务消息。

## 阶段 7：意图、指代与固定流程

- 意图识别把请求路由到知识、业务 Agent、退款、人工或闲聊出口；
- 指代消解把“那笔订单呢”补成下游能独立理解的问题；
- 退款和人工工单是确定性流程，真正写库前用 `interrupt` 暂停；
- 前端调用 `POST /api/v1/chat/{conversation_id}/resume` 确认或取消。

确认请求示例：

```json
{"user_id": "用户ID", "confirmed": true}
```

## 阶段 8：上下文管理

MySQL `messages` 永久保留完整原文；模型上下文只使用“较早消息滚动摘要 + 最近 12 条原文”。
摘要游标、结构化事实和稳定前缀哈希保存在 `conversation_memories`，避免会话越长模型输入
无限增长，也让模型服务的前缀缓存更容易命中。

## 阶段 9：统一 Tool 与 MCP

所有工具统一登记为 `ToolSpec`，包含名称、用途、JSON Schema、来源和读写权限。执行时固定经过：

```text
查注册表 → JSON Schema 校验 → 写权限确认 → 超时/只读重试 → 结果截断 → tool_audits 审计
```

内置工具负责订单查询、工单和退款写入；物流与售后查询由两台独立 MCP Server 提供：

```powershell
python mcp_servers/logistics_server.py   # 8101
python mcp_servers/aftersales_server.py  # 8102
```

MCP Server 暂时不可用时只跳过该来源，本轮仍可使用其他能力；外部 MCP 工具默认只读，
不能仅凭 Server 自己的声明获得写权限。

## 阶段 10：权限与安全

本阶段不是简单增加一句“请安全回答”的 Prompt，而是在不同层设置独立边界：

- Bearer Token 中的 `sub` 是可信用户身份，客户端提交的 `user_id` 不能覆盖它；
- 每次读取会话和消息都同时检查 `conversation_id + user_id`，避免水平越权；
- 停用用户不能继续访问，生产环境禁止使用默认签名密钥和演示登录；
- 输入护栏拦截明显的越权、密钥窃取和 Prompt Injection 请求；
- 知识 Chunk 和工具结果被标记为不可信数据，疑似外部指令不会直接进入模型上下文；
- 模型最终回答会做密钥、邮箱和手机号脱敏；
- MCP 工具默认只读，写工具只认服务端权限表，并且必须经过 interrupt 用户确认；
- 请求体大小、接口频率、CORS、CSP、HSTS 等由 HTTP 中间件统一控制；
- 高风险输入和鉴权失败写入 `security_events`，工具执行写入 `tool_audits`。

开发环境前端会调用 `/api/v1/auth/demo-token` 自动登录 `demo-user`。生产环境至少修改：

```env
AIDAHELP_ENVIRONMENT=production
AIDAHELP_AUTH_SECRET=替换成足够长的随机密钥
AIDAHELP_DEMO_AUTH_ENABLED=false
AIDAHELP_CORS_ALLOWED_ORIGINS=https://你的客服域名
```

企业真实部署建议把 Demo Token 签发替换成公司 OIDC/SSO 的 JWKS 验签。

## 客服前端

前端位于 `web/`，不需要安装 Node.js。启动 FastAPI 后打开：

- 客服页面：<http://127.0.0.1:8000/>
- API 文档：<http://127.0.0.1:8000/docs>

页面包含多会话切换、SSE 分片显示、意图/路由状态、知识引用、退款/工单确认卡、移动端布局
和 Token 设置。模型内容只通过 `textContent` 写入页面，不把模型生成文本当作 HTML 执行。

## 运行环境

- Python 3.11+
- Docker Desktop 或可访问的 MySQL 8.x

## 安装

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

## 启动 MySQL 并初始化数据库

```powershell
docker compose up -d mysql
python -m alembic upgrade head
python scripts/check_database.py
python scripts/seed_demo_data.py
```

执行第一条命令前需要确认 Docker Desktop 已经启动；服务器使用现有 MySQL 时可以跳过
Docker 命令，直接在 `.env` 中填写服务器数据库地址。

`seed_demo_data.py` 会创建一个演示用户和一篇退货政策文档。脚本可以重复执行，不会重复创建
相同用户和相同版本文档。

## 启动

```powershell
python -m uvicorn aidahelp.main:app --app-dir src --reload
```

启动后可以访问：

- 客服页面：<http://127.0.0.1:8000/>
- API 文档：<http://127.0.0.1:8000/docs>
- 存活检查：<http://127.0.0.1:8000/api/v1/health/live>
- 就绪检查：<http://127.0.0.1:8000/api/v1/health/ready>

数据库正常时，就绪检查包含：

```json
{
  "application": "ok",
  "mysql": "ok"
}
```

## 会话接口

创建会话前先执行演示数据脚本，并复制脚本输出的用户 ID：

```powershell
$body = @{
  user_id = "替换成演示用户ID"
  title = "物流咨询"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/conversations `
  -ContentType "application/json" `
  -Body $body
```

查询会话：

```text
GET /api/v1/conversations/{conversation_id}?user_id={user_id}
```

查询原始消息：

```text
GET /api/v1/conversations/{conversation_id}/messages?user_id={user_id}
```

目前 `user_id` 由请求参数传入。后续接入认证后，会改成从可信登录身份中获取。

## 基础聊天接口

默认 `.env` 使用 Mock 模型，不需要 API Key：

```powershell
$body = @{
  user_id = "替换成演示用户ID"
  message = "我的订单什么时候发货？"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType "application/json" `
  -Body $body
```

继续同一个会话时传回 `conversation_id`：

```json
{
  "user_id": "演示用户ID",
  "conversation_id": "上一轮返回的会话ID",
  "message": "那可以修改收货地址吗？"
}
```

接入真实 OpenAI 兼容模型时修改 `.env`：

```env
AIDAHELP_LLM_PROVIDER=openai_compatible
AIDAHELP_LLM_BASE_URL=https://你的模型服务地址/v1
AIDAHELP_LLM_API_KEY=你的API密钥
AIDAHELP_LLM_MODEL=你的模型名称
```

API Key 只放在服务器环境变量或 `.env`，不要写入源码或提交 Git。

## 阶段 4：知识入库

安装更新后的依赖并启动 MySQL、Milvus Standalone：

```powershell
python -m pip install -e ".[dev]"
docker compose up -d mysql etcd minio milvus
python -m alembic upgrade head
```

将示例知识写入 MySQL 和 Milvus：

```powershell
python scripts/ingest_knowledge.py data/knowledge/raw --version demo-v1
```

指定分类：

```powershell
python scripts/ingest_knowledge.py data/knowledge/raw --version demo-v1 --category after_sales
```

默认使用 `mock-hash-256` 跑通流程，不会产生模型费用。接入真实 Embedding 时需要同时修改：

```env
AIDAHELP_EMBEDDING_PROVIDER=openai_compatible
AIDAHELP_EMBEDDING_BASE_URL=https://模型服务地址/v1
AIDAHELP_EMBEDDING_API_KEY=真实密钥
AIDAHELP_EMBEDDING_MODEL=真实模型名称
AIDAHELP_EMBEDDING_DIMENSION=模型真实向量维度
AIDAHELP_MILVUS_COLLECTION=aidahelp_knowledge_bge_v1
```

向量维度或 Embedding 模型变化时必须使用新集合名，不能把不同向量空间写进同一集合。

双写顺序：

```text
解析文档并计算 checksum
  → MySQL 事务写入原文和 pending Chunk
  → 批量生成 Embedding
  → Milvus 幂等 upsert Dense 与 BM25 文本
  → flush
  → MySQL 回填 indexed、vector_id、embedding_model
```

如果中间失败，文档被标记为 `failed`，再次执行同一个入库命令会复用记录并继续索引。

## 阶段 5：混合检索

```http
POST /api/v1/knowledge/search
Content-Type: application/json
```

```json
{
  "query": "寄回来要邮费吗？",
  "strategy": "hybrid_rerank",
  "top_k": 5,
  "category": "after_sales"
}
```

支持四种策略：

```text
vector          只使用 Dense 语义向量
bm25            只使用 BM25 关键词
hybrid          Dense + BM25 + RRF
hybrid_rerank   Dense + BM25 + RRF + Reranker
```

默认召回流程：

```text
用户问题
  → query：清理后的自然问法，给 Dense 和 Reranker
  → bm25_text：自然问法加关键词同义词，只给 BM25
  → Dense Top-50 + BM25 Top-50
  → RRF 融合
  → Reranker 精排 Top-10
  → 计算证据置信度
```

默认 Mock Reranker 只验证工程链路。真实环境配置：

```env
AIDAHELP_RERANK_PROVIDER=openai_compatible
AIDAHELP_RERANK_BASE_URL=https://模型服务地址/v1
AIDAHELP_RERANK_API_KEY=真实密钥
AIDAHELP_RERANK_MODEL=真实重排模型名称
```

## 测试

```powershell
python -m pytest
```

真实 MySQL 集成测试默认跳过。需要执行时设置一个专用测试数据库：

```powershell
$env:AIDAHELP_TEST_DATABASE_URL = "mysql+asyncmy://用户名:密码@地址:3306/测试库"
python -m pytest -m integration
```

## 当前请求链路

```text
浏览器请求
  → 限流 / 请求体大小 / Bearer Token 验证
  → Token user_id 与会话归属授权
  → 输入安全护栏
  → MySQL 保存用户原文并构建“摘要 + 最近窗口”上下文
  → LangGraph 意图识别 / 指代消解 / 路由
  → RAG、ReAct Tool/MCP 或 interrupt 固定流程
  → 输出脱敏并保存 Assistant 消息
  → SSE 发送回答、引用和确认卡
  → 安全响应头与 Trace 日志
```

## 数据库职责

```text
users
  └── conversations
        └── messages

knowledge_documents
  └── knowledge_chunks

conversation_memories
tickets / refund_requests
tool_audits / security_events
```

MySQL 保存可审计的原始业务数据。后续 Milvus 只保存 Chunk 对应的向量，不替代 MySQL。
