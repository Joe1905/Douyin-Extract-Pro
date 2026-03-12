import subprocess
import sys
import os
import socket
import platform

def print_step(message):
    print(f"\n🔹 {message}...")

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def check_ffmpeg():
    print_step("检查 FFmpeg 环境")
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print_success("FFmpeg 已安装且可用")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print_error("未检测到 FFmpeg！")
        print("\n⚠️  Windows 安装指南：")
        print("   方法 1 (推荐 - 使用 Chocolatey):")
        print("      以管理员身份打开 PowerShell，运行: choco install ffmpeg")
        print("   方法 2 (手动下载):")
        print("      1. 访问 https://gyan.dev/ffmpeg/builds/ 下载 release-essentials.zip")
        print("      2. 解压并将 bin 文件夹路径添加到系统环境变量 Path 中")
        print("      3. 重启终端重试")

def install_dependencies():
    print_step("安装核心依赖库")
    packages = [
        "fastapi",             # Web 框架
        "uvicorn",             # ASGI 服务器
        "python-dotenv",       # 环境变量管理
        "httpx"                # 异步 HTTP 请求
    ]
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print_success("所有 Python 依赖库安装完成")
    except subprocess.CalledProcessError:
        print_error("依赖安装失败，请检查网络或 pip 配置")

def create_directories_and_config():
    print_step("配置目录与环境变量")
    
    # 获取当前脚本所在目录 (即 backend 目录)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 创建 temp_downloads (直接在 backend 目录下)
    temp_dir = os.path.join(backend_dir, "temp_downloads")
    os.makedirs(temp_dir, exist_ok=True)
    print_success(f"临时目录已创建: {temp_dir}")

    # 2. 创建 .env 模板 (直接在 backend 目录下)
    env_path = os.path.join(backend_dir, ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("GEMINI_API_KEY=\n")
        print_success(f".env 配置文件已生成: {env_path} (请填入您的 API Key)")
    else:
        print_success(f".env 文件已存在，跳过创建")

def test_google_connectivity():
    print_step("测试 Google API 网络连通性")
    host = "generativelanguage.googleapis.com"
    port = 443
    try:
        # 尝试建立 TCP 连接
        socket.create_connection((host, port), timeout=5)
        print_success("成功连接到 Google API 服务器")
    except OSError:
        print_error("无法连接到 Google API 服务器")
        print("⚠️  请检查您的网络环境（VPN/代理），确保能访问 generativelanguage.googleapis.com")

def main():
    print("🚀 开始配置后端开发环境...\n")
    
    check_ffmpeg()
    install_dependencies()
    create_directories_and_config()
    test_google_connectivity()
    
    print("\n🎉 环境配置脚本执行完毕！")

if __name__ == "__main__":
    main()
