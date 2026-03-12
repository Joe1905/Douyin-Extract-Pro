# 抖音提取 Pro (VideoExtract) - 开发全记录与技术日志

**文档日期**: 2024-05-20 (示例日期)
**项目状态**: 已结项 (Stable v1.0)
**技术栈**: Python (FastAPI), React (TypeScript), Playwright, FFmpeg

---

## 1. 项目概览与里程碑

### 1.1 项目定义
本项目旨在构建一个高可用、全栈式的**抖音短视频素材提取与二次创作平台**。它不仅仅是一个简单的下载器，更是一个集成了自动化采集、多模态处理（音视频/文本/关键帧）和 LLM 创意生成的生产力工具。

### 1.2 核心里程碑
*   **Phase 1: 核心提取跑通**
    *   成功集成 Playwright 实现无头浏览器抓取，攻克了抖音的反爬与动态加载机制。
    *   利用 `httpx` 实现流媒体的高速下载。
*   **Phase 2: 多模态处理**
    *   引入 FFmpeg，实现了视频关键帧（0%, 50%, 90%）的精准提取。
    *   实现了长音频的 30s 自动切片与格式标准化（Mono/16kHz），为 ASR 铺平道路。
*   **Phase 3: AI 能力接入**
    *   打通 PPIO/Gemini 接口，实现了基于脚本的“爆款文案”自动生成。
    *   实现了“人机协同”模式：用户可在线编辑脚本，并触发二次总结。
*   **Phase 4: 全栈工程化 (The Refactoring)**
    *   前端引入 SSE 流式日志，状态反馈毫秒级同步。
    *   后端实现数据持久化与物理删除闭环。
    *   UI 交互达到生产级标准（状态锁、渲染隔离）。

---

## 2. 技术架构演进

### 2.1 通信协议：拥抱 SSE
起初，我们考虑过简单的轮询或 WebSocket，但最终选择了 **SSE (Server-Sent Events)**。
*   **决策理由**：视频处理是典型的长耗时任务（解析->下载->切片->转录->分析）。SSE 允许后端单向、实时地推送 `step`（当前步骤）和 `message`（日志），让前端用户能感知到“正在切分音频 (2/5)...”这样的微粒度进度，极大地缓解了等待焦虑。

### 2.2 渲染策略：物理隔离 (Physical Isolation)
前端 React 组件的渲染逻辑经历了一次根本性的重构。
*   **早期痛点**：在任务状态频繁切换（如从 `fetching` 瞬间跳到 `success`）时，React 的 Diff 算法试图复用旧的 DOM 节点（特别是 `<video>` 和图片容器），导致了频发的 `Failed to execute 'insertBefore'` 崩溃。
*   **最终方案**：在结果展示区的根容器上强制绑定 `key={result?.ts || status}`。
*   **效果**：这告诉 React：“这完全是两个不同的组件”。React 会**彻底销毁**旧的 DOM 树并重新挂载新的，一劳永逸地解决了所有状态残留和节点冲突问题。

### 2.3 数据契约：字段名大一统
*   **混乱时期**：后端曾混用 `frames` 和 `frames_rel_paths`，前端也混淆了 `images` 和 `frames`，导致经常出现“图片无法显示”或“undefined”报错。
*   **最终契约**：全链路统一使用 **`frames`**。无论是在 `pipeline_service` 的返回值、`ProcessResponse` 模型定义，还是前端的 `ProcessResult` 接口中，`frames` 是唯一合法的事实来源。

---

## 3. 重大 Bug 修复记录 (The Bug War)

### 3.1 DOM 崩溃案 (The "insertBefore" Crash)
*   **现象**：用户点击“开始提取”瞬间，页面白屏，控制台报错 `NotFoundError: Failed to execute 'insertBefore' on 'Node'`。
*   **根因**：React 尝试更新一个已经被浏览器原生行为（如视频播放器的销毁）修改过的 DOM 结构。
*   **修复**：实施“物理隔离渲染”策略（见 2.2），强制重绘。

### 3.2 字段名罗生门 (KeyError: 'frames_rel_paths')
*   **现象**：后端日志显示任务已完成，但前端迟迟收不到 `done` 信号，后端抛出 `KeyError`。
*   **根因**：`pipeline_service.py` 已经重构为返回 `frames`，但 `main.py` 的流式响应组装逻辑中仍旧硬编码访问旧键名 `frames_rel_paths`。
*   **修复**：全量搜索替换，并引入防御性编程 `data.get('frames', [])`，确保即使字段缺失也不会导致进程崩溃。

### 3.3 环境依赖坑 (NameError: shutil)
*   **现象**：点击删除历史记录，后端报错 500。
*   **根因**：`main.py` 中使用了 `shutil.rmtree` 进行物理删除，但文件头部忘记 `import shutil`。
*   **修复**：补全导入，并增加了路径存在性检查 (`os.path.exists`)。

### 3.4 语法越界 (Python Comments in TS)
*   **现象**：前端编译失败，提示语法错误。
*   **根因**：在 `App.tsx` 中习惯性地使用了 Python 的 `#` 作为注释符。
*   **修复**：全量清理，统一替换为 TypeScript 标准的 `//` 注释。

---

## 4. 最终确定的工程规范

### 4.1 交互锁机制 (Interaction Lock)
为了防止数据流冲突，我们引入了严格的状态锁：
*   当 `status` 处于 `fetching_media`, `splitting_audio` 等忙碌状态时，侧边栏的**历史记录点击**、**删除按钮**以及**新建任务按钮**全部自动进入 `disabled` 状态。

### 4.2 极简预览逻辑 (Native Preview)
*   **移除**：删除了复杂的“悬浮下载按钮”逻辑，减少了 DOM 复杂度。
*   **确立**：
    *   **单击**图片 -> 弹出全屏 Modal。
    *   **下载** -> 依靠浏览器原生的“右键另存为”或模态框内的下载逻辑。

### 4.3 持久化契约 (Persistence)
*   **存储**：所有任务产物（包括 AI 生成的文案）必须实时写入 `temp_downloads/{ts}/` 目录。
*   **同步**：`re-summarize` 接口在返回给前端之前，**必须**先完成 `xhs_copy.txt` 的磁盘写入，确保前端刷新历史列表时能读到最新数据。
*   **清理**：`DELETE` 接口执行的是**物理删除**，彻底释放磁盘空间。
