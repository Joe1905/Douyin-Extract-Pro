# 抖音爆款提取工具 Pro (VideoExtract)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-blue)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-orange)](https://playwright.dev/)

VideoExtract 是一个全栈式的短视频内容分析与二次创作平台。它通过自动化浏览器技术抓取抖音视频素材，利用 FFmpeg 进行精准的多模态处理（关键帧、音频切片），并集成 PPIO (ASR/LLM) 或 Google Gemini 等先进 AI 模型，一键生成符合小红书风格的爆款文案。

## ✨ 核心特性

*   **全流程自动化**：从 URL 解析、视频下载、关键帧提取、语音转文字到 AI 文案生成，一气呵成。
*   **多模态提取**：不仅提取视频，还自动截取第 0/50/90% 处的关键帧，并生成精准的逐字稿。
*   **流式响应 (SSE)**：后端采用 Server-Sent Events 技术，前端实时展示每一步处理进度（如：正在切分音频、正在转写第 3/5 段...）。
*   **人机协同创作**：支持在线预览视频、**人工校对 ASR 脚本**，并基于修改后的脚本**二次生成**文案，实现内容精准纠偏。
*   **历史资产管理**：所有任务以时间戳归档，支持历史记录回溯、瞬间加载和物理删除。
*   **健壮性设计**：前端采用物理隔离渲染策略（Key-based Remounting），彻底杜绝 React DOM 冲突；后端具备完善的错误捕获与资源清理机制。

---

## 🛠️ 技术栈

### 后端 (Backend)
*   **核心框架**: FastAPI (Python 3.9+)
*   **网页自动化**: Playwright (仅使用 Chromium 内核，无头/有头模式可选)
*   **媒体处理**: FFmpeg (用于音频转码、切片、截图)
*   **网络请求**: httpx (全异步 HTTP 客户端，支持代理)
*   **AI SDK**: Google GenAI, OpenAI (兼容 PPIO 协议)

### 前端 (Frontend)
*   **核心库**: React 18
*   **语言**: TypeScript
*   **样式**: Tailwind CSS
*   **图标**: Lucide React

---

## 🚀 环境搭建与运行

### 前置要求
*   **FFmpeg**: 必须预装并确保 `ffmpeg` 和 `ffprobe` 命令在系统环境变量 PATH 中可用。
*   **Python**: 3.9 或更高版本。
*   **Node.js**: 16.x 或更高版本。

### 1. 后端设置

```bash
cd backend

# 1. 创建并激活虚拟环境 (推荐)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 2. 安装依赖
pip install fastapi uvicorn playwright httpx openai google-genai python-dotenv

# 3. 初始化 Playwright 浏览器内核
playwright install chromium

# 4. 启动服务
python main.py
```
后端服务将在 `http://localhost:8000` 启动。

### 2. 前端设置

```bash
# 回到项目根目录，然后进入 src 所在目录 (通常是根目录或 frontend 目录，视项目结构而定)
# 假设 package.json 在根目录
npm install

# 启动开发服务器
npm start
```
前端应用将在 `http://localhost:3000` 启动。

### 3. API 配置
首次运行时，请在网页右上角点击 **"API 设置"**：
*   **厂商**: 选择 PPIO (推荐) 或 Gemini。
*   **API Key**: 填入您的密钥。
*   **代理**: 如果需要访问海外 API (如 Gemini)，请填入本地代理地址 (如 `http://127.0.0.1:7890`)；国内 API (如 PPIO) 留空即可直连。

---

## 🧠 核心逻辑契约

### 1. 物理存储隔离
所有任务产物存储在 `backend/temp_downloads/{TIMESTAMP}/` 目录下，包含：
*   `audio.m4a`: 原始音频。
*   `frames/`: 关键帧截图 (frame_00.jpg, frame_50.jpg, frame_90.jpg)。
*   `chunks/`: 为 ASR 切分的音频片段 (30s/片)。
*   `script.txt`: ASR 转录的原始脚本。
*   `xhs_copy.txt`: AI 生成的最新文案。
*   `metadata.json`: 视频标题、描述等元数据。

### 2. 渲染稳定性 (Frontend)
为了解决复杂的异步状态切换可能导致的 React 渲染崩溃 (如 `Failed to execute 'insertBefore'`)，结果展示区采用了**物理隔离渲染**策略：
```tsx
// 利用 key 强制 React 在任务切换时销毁并重建整个 DOM 树
<div key={result?.ts || status}>
  {/* 结果展示组件 */}
</div>
```

### 3. 原子化删除 (Backend)
执行删除操作时，后端调用 `shutil.rmtree` 彻底移除对应的文件夹，确保磁盘空间被有效释放，不存在“软删除”或残留文件。

---

## 📖 操作指南

1.  **新任务提取**：
    *   在顶部输入框粘贴抖音视频链接（支持短链）。
    *   点击“开始提取”，观察下方的终端风格日志流。
    *   等待进度条走完（解析 -> 下载 -> 切片 -> 转录 -> 分析）。

2.  **素材校对与编辑**：
    *   左侧视频播放器可预览原片。
    *   下方脚本编辑器显示 ASR 转录结果。**您可以直接在这里修改错别字或调整语句**。

3.  **二次生成 (Human-in-the-loop)**：
    *   修改完脚本后，点击编辑器下方的 **"基于当前脚本生成/更新文案"** 按钮。
    *   系统将跳过耗时的下载流程，直接将您修改后的文本发送给 LLM，秒级生成新的爆款文案。

4.  **历史回溯**：
    *   左侧侧边栏列出了所有历史任务。
    *   点击任意一项，界面瞬间切换至该任务的状态（无需重新加载）。
