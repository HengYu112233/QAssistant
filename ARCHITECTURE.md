# 架构设计文档

QQ Assistant Agent 的架构设计文档。

## 设计原则

### 1. 模块化（Modularity）

项目分为四个清晰的层级：

```
┌─────────────────────────────────────┐
│        Application Layer (main.py)  │  生命周期管理
├─────────────────────────────────────┤
│    Agent Layer (agent/)              │  业务逻辑
│  ├─ processor.py: 消息处理中枢        │
│  └─ memory.py: 上下文记忆管理         │
├─────────────────────────────────────┤
│ Plugin Layer (plugins/)              │  功能扩展
│  └─ example_tool.py: 工具模板        │
├─────────────────────────────────────┤
│  Core Layer (core/)                 │  底层通信
│  ├─ llm_client.py: LLM API          │
│  └─ bot_client.py: WebSocket        │
├─────────────────────────────────────┤
│  Config Layer (config.py)            │  配置管理
└─────────────────────────────────────┘
```

### 2. 关注点分离（Separation of Concerns）

每个模块的单一职责：

| 模块 | 职责 | 依赖 |
|-----|------|------|
| config.py | 环境变量加载 | 无 |
| llm_client.py | LLM 通信 | config |
| bot_client.py | WebSocket 管理 | config |
| memory.py | 对话存储 | 无 |
| processor.py | 消息处理编排 | llm_client, bot_client, memory |
| main.py | 生命周期 | 所有模块 |

### 3. 网络鲁棒性（Network Resilience）

#### 代理安全（Proxy Isolation）

```python
# llm_client.py 中的关键配置
http_client = httpx.AsyncClient(
  trust_env=False,      # 默认不继承环境代理
)
```

在网络异常场景下，系统会回退到 `trust_env=True` 的客户端重试。

这确保：
- 本地 127.0.0.1 的 QQ WebSocket 不走代理
- 对火山引擎的 HTTPS 请求直连，绕过系统梯子

#### 自动重试（Automatic Retries）

```
LLM Call
  ↓
 [尝试 1] → 失败 [等待 0.8s]
  ↓
 [尝试 2] → 失败 [等待 1.6s]
  ↓
 [尝试 3] → 失败 [抛出异常]
  ↓
[processor.py 捕获] → 返回降级消息
```

#### 自动重连（Automatic Reconnect）

```
WebSocket 连接
  ↓
 [监听消息] → 连接正常
  ↓
[异常发生] → 关闭连接
  ↓
[等待 3s] → 重新连接
  ↓
[最大尝试数检查] → 达到则停止，否则继续
```

### 4. 配置外部化（Externalized Configuration）

所有敏感信息通过环境变量加载：

```
.env (本地开发，不提交)
  ├─ QQ_WS_URL
  ├─ LLM_BASE_URL
  ├─ LLM_API_KEY
  ├─ LLM_MODEL
  └─ SYSTEM_PROMPT
```

优势：
- 开发/测试/生产环境配置独立
- 敏感信息不会意外提交到 Git
- CI/CD 流程中可注入环境变量

### 5. 课程概念对齐（MCP / RAG / Subagent）

为了方便课堂汇报，这个项目可以直接对齐课程中的三个关键概念：

- MCP：`bot_client.py`、`database.py`、`persistent_memory.py` 提供外部能力，`processor.py` 统一编排调用。
- RAG：`memory.py` 负责短期记忆检索，`persistent_memory.py` 负责长期记忆检索，二者一起进入提示词。
- Subagent：`processor.py` 在主回复完成后异步触发长期记忆更新，属于独立的后台整理任务。

### 6. 文档职责分工

为了避免文档过多、重复说明，这个仓库后续建议保持下面的分工：

- `README.md`：安装、运行、课程概念映射、快速排障。
- `ARCHITECTURE.md`：架构设计、数据流、模块职责、扩展点。
- `CONTRIBUTING.md`：开发协作、提交规范、测试建议。

这样可以避免把同一份说明散落在多个 Markdown 文件里。

## 数据流

### 消息处理流程

```
[QQ 用户消息]
     ↓
[WebSocket (bot_client.py)]
     ↓
[消息解析 (processor.py)]
     ↓
[查询历史 (memory.py)]
     ↓
[调用 LLM (llm_client.py)]
     ├─ 重试逻辑
     └─ 错误处理
     ↓
[保存回复到历史 (memory.py)]
     ↓
[发送回复 (bot_client.py)]
     ↓
[QQ 用户收到回复]
```

### 概念流向图

```
[用户输入]
  ↓
[RAG：短期历史 + 长期记忆检索]
  ↓
[MCP：调用 QQ / DB / 提醒等外部能力]
  ↓
[主回复返回给用户]
  ↓
[Subagent：后台总结并更新长期记忆]
```

### 对话上下文

```python
# processor.py 中的上下文拼接
context = [
    # 历史消息（最近 10 条）
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    ...
    # 当前消息
    {"role": "user", "content": "当前问题"}
]

# 发送给 LLM
response = llm_client.call(user_message, messages=context)
```

## 扩展点设计

### 1. 添加新工具（Function Calling）

```python
# plugins/weather_tool.py
class WeatherTool(ExampleTool):
    def __init__(self):
        super().__init__(
            name="get_weather",
            description="查询天气"
        )
    
    async def call(self, city: str) -> dict:
        # 调用天气 API
        return {"city": city, "temp": 25}

# main.py 中注册
tool_registry = ToolRegistry()
tool_registry.register(WeatherTool())
```

### 2. 自定义存储后端

```python
# agent/memory_db.py
class DatabaseMemory(ConversationMemory):
    def __init__(self, db_url: str):
        self.db = AsyncDatabase(db_url)
    
    async def add_message(self, ...):
        # 保存到数据库而非内存
        await self.db.save(...)
```

### 3. 自定义 LLM 提供商

```python
# core/custom_llm.py
class CustomLLMClient:
    async def call(self, message: str) -> str:
        # 调用你的私有 LLM
        ...
```

## 性能考虑

### 并发能力

- **WebSocket 监听**：单个 async 任务处理
- **LLM 调用**：当前串行，可扩展为并发队列
- **内存存储**：O(n) 查询，可改为数据库 O(1)

### 内存使用

- **默认配置**：每个对话保留 20 条历史消息
- **多用户**：按用户/群组隔离，内存线性增长
- 可配置 `max_history_size` 以控制内存占用

### 网络优化

- **连接复用**：httpx 自动连接池
- **Keepalive**：WebSocket ping/pong 机制
- **超时设置**：LLM 请求 30s，WebSocket ping 20s

## 安全考虑

### 1. 敏感信息保护

- ✅ API Key 只存储在 `.env` 中
- ✅ 日志中不输出密钥信息
- ✅ `.gitignore` 防止 `.env` 提交

### 2. 输入验证

- ✅ JSON 解析异常处理
- ✅ 消息内容长度检查（可选）
- ✅ 类型注解提示合法输入

### 3. 错误处理

- ✅ 所有异步操作都有 try/except
- ✅ 降级响应防止服务中断
- ✅ 详细日志便于诊断问题

## 部署考虑

### 本地开发

```bash
python main.py
LOG_LEVEL=DEBUG
```

### Docker 部署

```dockerfile
FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV LOG_LEVEL=INFO
CMD ["python", "main.py"]
```

### 云平台部署

支持通过环境变量注入配置：
- 云函数：FaaS 环境设置变量
- 容器服务：Dockerfile 或 K8s ConfigMap
- 应用平台：提交 requirements.txt

## 监控和日志

### 日志级别

```
DEBUG: 详细的函数调用、参数信息
INFO: 关键操作点（连接、调用、回复）
WARNING: 可恢复的错误（重试、降级）
ERROR: 不可恢复的错误（导致功能失效）
```

### 关键指标（可扩展）

- 消息处理延迟
- LLM 调用成功率
- WebSocket 连接稳定性
- 内存占用趋势

## 版本更新计划

### v1.0.0 (当前)
- 核心功能：QQ 对话接入、LLM 调用、上下文记忆
- 网络安全加固

### v1.1.0 (计划)
- Function Calling / Tool Use
- 群组 @ 应答
- 消息中间件系统

### v2.0.0 (计划)
- 数据库存储后端
- 多 LLM 提供商支持
- Web 管理界面

---

详见 [README.md](README.md) 和 [CONTRIBUTING.md](CONTRIBUTING.md)。
