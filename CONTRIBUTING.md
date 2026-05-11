# QQ Assistant Agent 贡献指南

感谢你对本项目的兴趣！本文档提供了参与贡献的指南。

## 行为准则

我们承诺提供一个欢迎、包容的社区环境。请尊重他人，反对任何形式的骚扰。

## 如何贡献

### 报告问题

使用 GitHub Issues 报告问题，包含以下信息：
- 清晰的标题
- 详细的复现步骤
- 期望的行为
- 实际的行为
- Python 版本、操作系统等环境信息

### 提交功能建议

在 Issues 中描述你的想法，包括：
- 功能概述
- 使用场景
- 可选的实现建议

### Pull Request 提交流程

1. **Fork 项目**
   ```bash
   git clone https://github.com/yourusername/qq-assistant-agent.git
   cd qq-assistant-agent
   ```

2. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   git checkout -b fix/your-bug-fix
   ```

3. **开发与修改**
   - 遵循代码风格（见下文）
   - 添加或更新相关测试
   - 更新文档（如必要）

4. **提交 Commit**
   ```bash
   git add .
   git commit -m "feat: add new feature" -m "Detailed description"
   ```

   Commit 消息格式：
   - `feat: ` - 新功能
   - `fix: ` - 修复 Bug
   - `docs: ` - 文档更新
   - `refactor: ` - 代码重构
   - `test: ` - 测试更新
   - `chore: ` - 环境或依赖变化

5. **推送并创建 Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

   在 GitHub 上创建 PR，附加以下信息：
   - 清晰的 PR 标题
   - 详细的修改说明
   - 相关 Issue 号（如有）
   - 自测通过证明

## 代码风格

### Python 风格规范

本项目遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/)：

- 缩进：4 个空格
- 行长：不超过 100 字符
- 函数和类：使用 snake_case
- 常量：使用 UPPER_CASE

### Type Hints

优先使用类型提示提升代码可读性：

```python
async def process_message(self, event: dict) -> None:
    """Process an incoming message event."""
    pass
```

### Docstrings

使用 Google 风格的 docstrings：

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of the function.
    
    Longer description if needed, explaining the behavior,
    edge cases, or usage examples.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.
        
    Raises:
        ValueError: When something is wrong.
    """
    pass
```

### 日志

使用标准 logging 模块：

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
logger.debug("Debug message")
```

## 项目架构

### 核心原则

1. **模块化**：明确的职责边界，低耦合
2. **异步优先**：使用 asyncio 支持高并发
3. **网络鲁棒**：自动重试、超时保护、优雅降级
4. **配置外部化**：环境变量驱动，敏感信息不硬编码

### 添加新功能的步骤

1. 确定属于哪个模块（`core/`, `agent/`, `plugins/`）
2. 在对应位置创建代码
3. 添加或修改 `__init__.py` 导出
4. 编写 docstrings 和类型提示
5. 添加日志记录关键操作
6. 在 `processor.py` 中集成（如需要）
7. 更新 README.md 文档

## 测试与验证

目前项目尚无自动化测试框架，但欢迎贡献！

### 手动测试清单

在提交 PR 前，请验证：

- [ ] Python 3.10+ 能正常运行
- [ ] `pip install -r requirements.txt` 成功
- [ ] `python quickstart.py` 通过
- [ ] 能成功连接到 NapCat
- [ ] 能成功调用 LLM 并获得响应
- [ ] WebSocket 断线后能自动重连
- [ ] 关闭 VPN/梯子后仍能正常工作

### 新增功能测试建议

- 提供手动测试步骤
- 描述预期行为
- 如有条件，提供自动化测试代码

## 文档维护

如果修改涉及用户见的功能或 API：

1. 更新 `README.md` 中的相关部分
2. 在 docstrings 中添加清晰示例
3. 考虑在 `CONTRIBUTING.md` 中添加开发指南

## 发布流程（维护者）

项目维护者会：

1. 审核 PR 代码质量和功能完整性
2. 运行集成测试
3. 更新版本号（遵循 Semantic Versioning）
4. 发布新版本到 PyPI（如适用）
5. 更新 Release Notes

## 许可证

通过贡献代码，你同意你的代码将在 MIT 许可证下发布。

## 问题反馈

- **Bug 报告**：GitHub Issues （标签：`bug`）
- **功能建议**：GitHub Issues （标签：`enhancement`）
- **讨论**：GitHub Discussions

## 联系与反馈

如有疑问，欢迎提交 Issue 或 Discussion。

---

再次感谢你的贡献！🙏
