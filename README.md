# QQ Assistant Agent - 生活助理智能体

基于 OneBot V11 协议和 DeepSeek 大模型的智能 QQ 机器人，支持上下文记忆和自适应梯子环境。

## 小组分工

本项目由两人共同完成，按照代码量和实际功能贡献五五开分工。为便于老师快速判断两人的独立贡献，下面按“成员 + 编号任务”说明。

### 张芷宁（组长）代码与工程贡献

1. 负责主程序运行链路的组织与收敛，重点参与 `main.py` 的启动流程、关闭流程、任务守护逻辑与生命周期管理。

2. 参与并推进“自动退出”问题修复，围绕连接任务结束后的行为做流程梳理，确保主链路稳定运行。

3. 参与 `agent/processor.py` 的业务编排设计，重点梳理消息处理顺序、提示词拼接结构和回复路径，使处理链路更清晰。

4. 参与记账与提醒业务逻辑联调，确认消息输入、规则匹配、数据库写入与回复输出之间的闭环一致性。

5. 负责项目文档主线整理，重点完善 `README.md` 和 `ARCHITECTURE.md` 的结构、课程概念映射与汇报可读性表达。

6. 负责演示叙事与展示逻辑设计，明确“背景-实现-演示-复盘”的呈现顺序，保证汇报时能对应课程评分点。

### 张雨泽（组员）代码与工程贡献

1. 负责核心功能实现与联调验证，重点参与 `core/bot_client.py` 的 WebSocket 连接、重连、消息接收与发送逻辑。

2. 参与 `core/llm_client.py` 的模型接入与异常处理，重点排查超时、连接失败与调用稳定性问题。

3. 负责 `core/database.py` 的持久化能力实现，覆盖记账数据与提醒数据的写入、查询、聚合与状态更新。

4. 负责 `agent/persistent_memory.py` 的长期记忆存储与更新逻辑，实现记忆文本读写与对话后异步更新流程。

5. 参与 `agent/memory.py` 与 `agent/processor.py` 的上下文管理和规则解析，完善记账、提醒、回复分支等功能路径。

6. 负责调试验证与问题复盘，围绕连接异常、模型超时、数据写入一致性等问题进行排查和修复验证。

### 共同贡献（两人均有实际代码参与）

1. 主程序与通信链路：两人共同参与主流程、收发链路和异常场景处理。

2. 记忆与数据能力：两人共同参与短期记忆、长期记忆与数据库能力的组合落地。

3. 业务功能闭环：两人共同参与记账录入、金额查询、提醒触发和回复结果验证。

4. 工程质量保障：两人共同参与日志排查、问题复盘、文档维护与演示准备。



## 特性

- 🤖 **智能对话**：集成 DeepSeek V3.2，通过火山引擎 Ark 接入
- 💬 **上下文记忆**：内置对话历史管理，支持用户/群组隔离
- 🔌 **OneBot V11**：完整支持 NapCat WebSocket 协议
- 🛡️ **代理安全**：严格绕过系统代理，支持频繁开关 VPN
- 🔄 **自动重连**：WebSocket 和 API 失败自动重试
- 📦 **模块化架构**：清晰的层级设计，易于扩展
- ✅ **开源友好**：遵循 GitHub 开源规范

## 项目结构

```
qq-assistant-agent/
├── main.py                 # 程序入口和生命周期管理
├── config.py               # 配置管理（环境变量）
├── core/                   # 核心通信层
│   ├── __init__.py
│   ├── llm_client.py       # DeepSeek API 客户端（无代理确保）
│   ├── bot_client.py       # NapCat WebSocket 客户端（断线重连）
│   ├── database.py         # SQLite 持久化（记账/提醒）
│   └── scheduler.py        # 定时提醒调度器
├── agent/                  # 智能体逻辑层
│   ├── __init__.py
│   ├── memory.py           # 对话记忆管理
│   ├── persistent_memory.py # 长期记忆文本存储
│   └── processor.py        # 消息处理中枢
├── plugins/                # 功能扩展
│   ├── __init__.py
│   └── example_tool.py     # 工具模板（Function Calling 预留）
├── requirements.txt        # 依赖清单
├── .env.example           # 环境变量模板
├── .gitignore             # Git 忽略规则
└── README.md              # 本文件
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+ 推荐
python --version

# 克隆项目
git clone <repository_url>
cd qq-assistant-agent

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入实际信息：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# QQ 机器人 WebSocket 地址（NapCat）
QQ_WS_URL=ws://127.0.0.1:3001

# LLM 配置
LLM_BASE_URL=https://ark.volces.com/api/v3
LLM_API_KEY=your_api_key_here
LLM_MODEL=ep-20260429054819-rm76z

# 系统提示词
SYSTEM_PROMPT=你是一个名叫'宇恒'的专属生活助理，性格幽默、回答简明扼要

# 日志级别
LOG_LEVEL=INFO
```

### 3. 启动 NapCat

确保本地 NapCat 已启动，监听 `ws://127.0.0.1:3001`。

### 4. 运行机器人

```bash
python main.py
```

## 核心模块说明

### config.py
环境变量管理，支持 `.env` 文件和系统环境变量。所有敏感信息通过环境变量加载，不硬编码。

### core/llm_client.py
- **关键特性**：默认 `trust_env=False` 直连环境，网络异常时回退到 `trust_env=True`
- 自动重试和退避机制
- 超时作用域管理
- 完整的错误日志

### core/bot_client.py
- OneBot V11 WebSocket 客户端
- 自动断线重连（支持最大尝试次数限制）
- 消息处理句柄注册
- 私聊/群聊信息发送 API

### agent/memory.py
- 内存对话历史管理（可扩展到数据库）
- 按用户/群组隔离存储
- 自动老化策略（超出上限自动删除最旧消息）

### agent/processor.py
- 消息处理中枢，协调 LLM 和 Bot 客户端
- OneBot 数据结构解析
- 上下文拼接和发送

### plugins/example_tool.py
工具系统模板，为 Function Calling/Tool Use 预留扩展接口。

## 课程概念映射

如果你要做期末汇报，这个项目可以直接串起课程里的 3 个核心概念：

- MCP：`agent/processor.py` 统一编排，`core/bot_client.py`、`core/database.py` 提供外部能力。
- RAG：`agent/memory.py` 和 `agent/persistent_memory.py` 负责短期与长期记忆检索，再拼入提示词。
- Subagent：`agent/processor.py` 后台异步更新长期记忆，不阻塞主回复链路。

一页图就可以概括成：用户输入 → 检索记忆（RAG）→ 调用外部能力（MCP）→ 后台总结更新（Subagent）。

## 网络安全说明

项目严格应对开发环境中频繁开关 VPN/梯子的情况：

1. **本地通信绕过**：127.0.0.1 不走代理
2. **HTTP 客户端策略**：默认 `trust_env=False` 直连，必要时自动切换 `trust_env=True`
3. **连接容错机制**：WebSocket 自动重连，模型调用指数退避重试
4. **启动预检机制**：启动阶段执行模型连通性检查并支持降级回复

## 日志和调试

设置 `LOG_LEVEL=DEBUG` 以获得详细日志：

```env
LOG_LEVEL=DEBUG
```

## 扩展和自定义

### 添加新工具

在 `plugins/` 下创建新文件并继承 `ExampleTool`：

```python
from plugins.example_tool import ExampleTool

class WeatherTool(ExampleTool):
    async def call(self, city: str) -> str:
        # 实现天气查询逻辑
        pass
```

### 连接数据库

修改 `agent/memory.py` 使用数据库存储而非内存存储。

### 自定义 System Prompt

在 `.env` 中修改 `SYSTEM_PROMPT` 或通过代码初始化时传入 `system_prompt` 参数。

## 常见问题

### Q: 为什么模型无法连接？
A: 检查 `.env` 中的 `LLM_API_KEY` 和 `LLM_BASE_URL`，并确保网络能访问火山引擎。

### Q: WebSocket 连接失败？
A: 确保 NapCat 已启动并监听指定端口。检查 `QQ_WS_URL` 配置。

### Q: 频繁收到"大脑掉线"消息？
A: 检查 API Key 是否有效、网络连接、日志中是否有具体错误信息。

## 快速排障

如果程序看起来“自己关闭”，优先检查这三类原因：

- 运行环境里是否有人为终止进程。
- WebSocket 是否短暂断开，导致主流程误判。
- LLM 网络是否被系统代理或 VPN 干扰。

对应日志前缀建议这样看：

- `[STARTUP]`：启动检查
- `[PROCESSOR]`：消息处理
- `[LLM CALL]`：模型调用
- `[SEND]`：消息发送

排查原则是先看最早出现的错误，不要只看最后一条“已退出”。

## 许可证

MIT License - 欢迎开源贡献！

## 更新日志

### v1.0.0 (2026-05-11)
- 初始版本发布
- 核心功能：QQ 对话接入、LLM 调用、上下文记忆
- 模块化架构、网络安全加固
