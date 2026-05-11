# 项目恢复指南

这是从 GitHub 下载项目后快速恢复开发环境的步骤。

## 前置要求

- Python 3.10+（[下载](https://www.python.org/downloads/)）
- Git（已安装）
- 一个 QQ 号（用于 NapCat 机器人）

## 恢复步骤（约 3 分钟）

### 1. 克隆仓库

```bash
git clone https://github.com/HengYu112233/QAssistant.git
cd QAssistant
```

### 2. 创建虚拟环境

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# 或 Windows CMD
.venv\Scripts\activate.bat

# 或 macOS/Linux
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下信息：

```env
# QQ 机器人 WebSocket 地址（NapCat 启动的地址）
QQ_WS_URL=ws://127.0.0.1:3001

# LLM 配置（火山引擎 Ark）
LLM_BASE_URL=https://ark.volces.com/api/v3
LLM_API_KEY=你的 API Key
LLM_MODEL=你的模型 ID

# 机器人名字和提示词
SYSTEM_PROMPT=你是一个名叫'宇恒'的专属生活助理，性格幽默、回答简明扼要

# 日志级别（可选：INFO/DEBUG/WARNING）
LOG_LEVEL=INFO
```

### 5. 启动 NapCat

确保你已有 NapCat 运行，并监听 `ws://127.0.0.1:3001`。

### 6. 运行项目

```bash
python main.py
```

看到日志输出 "机器人已启动" 就说明成功了。

## 常见问题

**Q: 没有 LLM API Key？**  
A: 去 [火山引擎 Ark](https://ark.volces.com) 注册并创建 API Key。

**Q: NapCat 是什么？**  
A: 这是一个本地 QQ 机器人框架，需要单独启动。参考 [NapCat 文档](https://github.com/NapNeko/NapCat-Onebot11)。

**Q: 运行后报连接错误？**  
A: 检查 `.env` 中的 `QQ_WS_URL` 和 `LLM_BASE_URL` 是否正确。

**Q: 需要修改代码？**  
A: 修改后运行以下命令提交（可选）：
```bash
git add .
git commit -m "你的修改说明"
git push
```

## 更多信息

- **项目简介**：见 README.md
- **架构设计**：见 ARCHITECTURE.md  
- **贡献指南**：见 CONTRIBUTING.md
