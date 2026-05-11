"""
QQ 助理智能体快速启动检查脚本

该脚本帮助你快速完成环境自检。
请在项目根目录执行。
"""

import sys
from pathlib import Path

def check_python_version():
    """检查 Python 版本是否满足要求。"""
    if sys.version_info < (3, 10):
        print("❌ 需要 Python 3.10 或更高版本")
        sys.exit(1)
    print(f"✅ 检测到 Python {sys.version_info.major}.{sys.version_info.minor}")

def check_dependencies():
    """检查所需依赖是否已安装。"""
    required = [
        "websockets",
        "openai",
        "httpx",
        "dotenv",
        "aiosqlite",
        "apscheduler",
        "aiofiles",
    ]
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            missing.append(package)
            print(f"❌ {package} 未安装")
    
    if missing:
        print(f"\n⚠️  缺少依赖: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt\n")
        return False
    return True

def check_env_file():
    """检查 .env 文件是否存在并包含必需字段。"""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ 未找到 .env 文件")
        print("   请执行: cp .env.example .env")
        print("   然后编辑 .env 填入真实凭据")
        return False
    
    print("✅ 已找到 .env 文件")
    
    # Check required keys
    required_keys = [
        "QQ_WS_URL",
        "LLM_BASE_URL", 
        "LLM_API_KEY",
        "LLM_MODEL",
    ]
    
    with open(env_path, encoding="utf-8") as f:
        env_content = f.read()
    
    missing_keys = [k for k in required_keys if k not in env_content]
    
    if missing_keys:
        print(f"⚠️  缺少环境变量: {', '.join(missing_keys)}")
        return False
    
    # 如果仍在使用示例值则提醒
    if "your_api_key_here" in env_content:
        print("⚠️  LLM_API_KEY 仍然是占位符！")
        print("   请更新为真实的 API Key")
        return False
    
    print("✅ 必需环境变量已配置")
    return True

def check_napcat():
    """输出 NapCat 配置说明。"""
    print("\n📌 NapCat 配置说明:")
    print("   1. 确保 NapCat 已安装并运行")
    print("   2. 默认地址: ws://127.0.0.1:3001")
    print("   3. 确认 .env 中的 QQ_WS_URL 与 NapCat 端点一致")
    return True

def print_summary():
    """输出检查结果和下一步操作。"""
    print("\n" + "="*60)
    print("🚀 QQ 助理智能体 - 检查结果")
    print("="*60)
    print("\n✅ 所有检查均已通过！可以开始运行。\n")
    print("下一步:")
    print("  1. 启动 NapCat（如果还没运行）")
    print("  2. 运行: python main.py")
    print("  3. 给 QQ 机器人发送消息测试")
    print("\n如需调试，请在 .env 中设置 LOG_LEVEL=DEBUG")
    print("="*60 + "\n")

def main():
    """执行所有检查。"""
    print("\n" + "="*60)
    print("🔍 QQ 助理智能体 - 环境检查")
    print("="*60 + "\n")
    
    check_python_version()
    print()
    
    if not check_dependencies():
        return False
    print()
    
    if not check_env_file():
        return False
    print()
    
    check_napcat()
    print()
    
    print_summary()
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
