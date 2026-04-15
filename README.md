# VideoExtract Pro (抖音爆款提取工具)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-blue)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-orange)](https://playwright.dev/)

VideoExtract is a full-stack short video content analysis and repurposing platform. It uses automated browser technology to scrape Douyin (Chinese TikTok) videos, leverages FFmpeg for precise multi-modal processing (keyframes, audio slices), and integrates AI models like PPIO (ASR/LLM) or Google Gemini to generate Xiaohongshu (Little Red Book) style viral captions with one click.

## ✨ Key Features

*   **Fully Automated Pipeline**: From URL parsing, video downloading, keyframe extraction, and speech-to-text transcription to AI caption generation — everything flows seamlessly.
*   **Multi-modal Extraction**: Not just video downloading — automatically captures keyframes at 0/50/90% positions and generates precise word-by-word transcripts.
*   **Streaming Response (SSE)**: Backend uses Server-Sent Events technology; frontend displays real-time progress for each processing step (e.g., slicing audio, transcribing segment 3/5...).
*   **Human-in-the-Loop**: Supports online video preview, **manual ASR script proofreading**, and **secondary generation** based on modified scripts for precise content correction.
*   **Historical Asset Management**: All tasks are archived by timestamp, supporting historical record lookup, instant loading, and physical deletion.
*   **Robust Design**: Frontend uses physical isolation rendering strategy (Key-based Remounting) to completely prevent React DOM conflicts; backend has complete error handling and resource cleanup mechanisms.

---

## 🛠️ Tech Stack

### Backend
*   **Core Framework**: FastAPI (Python 3.9+)
*   **Web Automation**: Playwright (Chromium engine only, headless/headed mode optional)
*   **Media Processing**: FFmpeg (audio transcoding, slicing, screenshots)
*   **HTTP Client**: httpx (full async HTTP client, proxy support)
*   **AI SDK**: Google GenAI, OpenAI (PPIO protocol compatible)

### Frontend
*   **Core Library**: React 18
*   **Language**: TypeScript
*   **Styling**: Tailwind CSS
*   **Icons**: Lucide React

---

## 🚀 Setup & Running

### Prerequisites
*   **FFmpeg**: Must be pre-installed with `ffmpeg` and `ffprobe` commands available in system PATH.
*   **Python**: 3.9 or higher.
*   **Node.js**: 16.x or higher.

### 1. Backend Setup

```bash
cd backend

# 1. Create and activate virtual environment (recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 2. Install dependencies
pip install fastapi uvicorn playwright httpx openai google-genai python-dotenv

# 3. Initialize Playwright Chromium browser
playwright install chromium

# 4. Start server
python main.py
```
Backend will start at `http://localhost:8000`.

### 2. Frontend Setup

```bash
# Back to project root, then go to the directory where package.json is
# (usually root or frontend directory, depending on project structure)
npm install

# Start development server
npm start
```
Frontend will start at `http://localhost:3000`.

### 3. API Configuration
On first run, click **"API Settings"** in the top-right corner of the page:
*   **Provider**: Select PPIO (recommended) or Gemini.
*   **API Key**: Enter your API key.
*   **Proxy**: If you need to access overseas APIs (like Gemini), enter your local proxy address (e.g., `http://127.0.0.1:7890`); domestic APIs (like PPIO) can be used directly without proxy.

---

## 🧠 Core Logic Contracts

### 1. Physical Storage Isolation
All task outputs are stored in `backend/temp_downloads/{TIMESTAMP}/` directory, containing:
*   `audio.m4a`: Original audio.
*   `frames/`: Keyframe screenshots (frame_00.jpg, frame_50.jpg, frame_90.jpg).
*   `chunks/`: Audio slices for ASR (30s per slice).
*   `script.txt`: ASR transcription script.
*   `xhs_copy.txt`: Latest AI-generated captions.
*   `metadata.json`: Video title, description, and other metadata.

### 2. Rendering Stability (Frontend)
To solve React rendering crashes caused by complex async state transitions (e.g., `Failed to execute 'insertBefore'`), the result display area uses **physical isolation rendering** strategy:
```tsx
// Use key to force React to destroy and rebuild the entire DOM tree on task switching
<div key={result?.ts || status}>
  {/* Result display components */}
</div>
```

### 3. Atomic Deletion (Backend)
When executing deletion, the backend calls `shutil.rmtree` to completely remove the corresponding folder, ensuring disk space is effectively released without "soft deletion" or residual files.

---

## 📖 User Guide

1.  **New Task Extraction**:
    *   Paste a Douyin video link in the top input box (short URLs supported).
    *   Click "Start Extraction" and observe the terminal-style log stream below.
    *   Wait for the progress bar to complete (parsing -> downloading -> slicing -> transcription -> analysis).

2.  **Material Proofreading & Editing**:
    *   The left video player previews the original video.
    *   The script editor below displays ASR transcription results. **You can directly edit typos or adjust sentences here**.

3.  **Secondary Generation (Human-in-the-loop)**:
    *   After modifying the script, click the **"Generate/Update Caption Based on Current Script"** button below the editor.
    *   The system will skip the time-consuming download process and directly send your modified text to the LLM to generate new viral captions in seconds.

4.  **Historical Lookup**:
    *   The left sidebar lists all historical tasks.
    *   Click any item to instantly switch the interface to that task's state (no reloading required).

---

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
