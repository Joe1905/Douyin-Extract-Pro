from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import httpx
import asyncio
import traceback
import shutil
from google import genai
from openai import AsyncOpenAI
from dotenv import load_dotenv
import pipeline_service

app = FastAPI(title="抖音爆款提取工具 API")

# 1. 环境无关性：动态路径解析
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp_downloads")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

os.makedirs(TEMP_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=TEMP_DIR), name="downloads")

# CORS
origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 数据模型 ---
class VideoRequest(BaseModel):
    url: str


class ConfigVerifyRequest(BaseModel):
    provider: str
    apiKey: str
    proxyUrl: Optional[str] = ""


class ReSummarizeRequest(BaseModel):
    ts: str
    custom_script: Optional[str] = None


class ProcessResponse(BaseModel):
    ts: str
    metadata: dict
    script: str
    audio_rel_path: str
    frames: List[str]
    xhs_copy: str


class HistoryItem(BaseModel):
    ts: str
    title: str
    description: str
    cover: str
    script: str
    xhs_copy: str
    audio_rel_path: str
    frames: List[str]


load_dotenv()


def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


# --- 接口 ---
@app.get("/api/get-config")
async def get_config():
    return load_settings()


@app.post("/api/verify-config")
async def verify_config(config: ConfigVerifyRequest):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config.model_dump(), f, indent=4)
    return {"status": "success", "message": "配置已保存"}


# --- 核心 AI 逻辑 ---
async def analyze_content(title: str, desc: str, script: str, config: dict) -> str:
    """使用 AI 生成小红书文案 (支持 Gemini 和 PPIO/OpenAI)"""

    api_key = config.get("apiKey")
    provider = config.get("provider")
    proxy_url = config.get("proxyUrl")

    masked_key = f"{api_key[:4]}****{api_key[-4:]}" if api_key and len(api_key) > 8 else "未配置"
    print(f"\n🧠 [AI 分析] 开始调用 - 厂商: {provider}, Key: {masked_key}, 代理: {proxy_url or '直连'}")

    if not api_key: return "⚠️ API Key 未配置，无法生成文案。"

    prompt = f"""
    你是一个短视频爆款专家。请根据以下视频信息，撰写一篇吸引人的小红书笔记。
    【视频标题】：{title}
    【视频描述】：{desc}
    【完整脚本】：{script[:3000]}
    任务要求：
    1. 给出 5 个【爆款标题】，必须包含痛点或反差，带 Emoji。
    2. 撰写【正文】，结构清晰，分段落，第一句必须抓人眼球。
    3. 语气活泼，多用 Emoji，具有互动感。
    4. 结尾列出 10 个相关的【热门标签】(Hashtags)。
    """

    try:
        response_text = ""
        if provider == "gemini":
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            response_text = response.text
        elif provider in ["ppio", "openai"]:
            http_client = httpx.AsyncClient(proxy=proxy_url.strip()) if proxy_url and proxy_url.strip() else None
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.ppio.com/openai" if provider == "ppio" else "https://api.openai.com/v1",
                http_client=http_client
            )
            model = "qwen/qwen3.5-27b" if provider == "ppio" else "gpt-3.5-turbo"
            completion = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], temperature=0.7
            )
            response_text = completion.choices[0].message.content

        if not response_text:
            return "AI 返回内容为空，请检查模型权限或余额。"

        return response_text

    except Exception as e:
        return f"文案生成失败: {str(e)}"


# --- 历史记录接口 ---
@app.get("/api/v1/history", response_model=List[HistoryItem])
async def get_history():
    history = []
    if not os.path.exists(TEMP_DIR): return history

    base_url = "http://localhost:8000/downloads"

    for ts in sorted(os.listdir(TEMP_DIR), reverse=True):
        task_dir = os.path.join(TEMP_DIR, ts)
        if not os.path.isdir(task_dir): continue

        meta_file = os.path.join(task_dir, "metadata.json")
        script_file = os.path.join(task_dir, "script.txt")
        copy_file = os.path.join(task_dir, "xhs_copy.txt")

        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                script_content = ""
                if os.path.exists(script_file):
                    with open(script_file, 'r', encoding='utf-8') as f: script_content = f.read()
                xhs_copy_content = ""
                if os.path.exists(copy_file):
                    with open(copy_file, 'r', encoding='utf-8') as f: xhs_copy_content = f.read()

                frames_dir = os.path.join(task_dir, "frames")
                frames = []
                cover = ""
                if os.path.exists(frames_dir):
                    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
                    frames = [f"{base_url}/{ts}/frames/{f}" for f in frame_files]
                    if frames: cover = frames[0]

                history.append(HistoryItem(
                    ts=ts,
                    title=metadata.get("title", "无标题"),
                    description=metadata.get("description", ""),
                    cover=cover,
                    script=script_content,
                    xhs_copy=xhs_copy_content,
                    audio_rel_path=f"{ts}/audio.m4a",
                    frames=frames
                ))
            except Exception as e:
                print(f"读取历史记录 {ts} 失败: {e}")
    return history


@app.delete("/api/v1/history/{ts}")
async def delete_history(ts: str):
    if ".." in ts or "/" in ts or "\\" in ts:
        raise HTTPException(status_code=400, detail="非法的时间戳参数")

    task_dir = os.path.join(TEMP_DIR, ts)
    if not os.path.exists(task_dir):
        raise HTTPException(status_code=404, detail="记录不存在")

    try:
        shutil.rmtree(task_dir)
        return {"status": "success", "message": f"记录 {ts} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# --- 重新总结接口 ---
@app.post("/api/v1/re-summarize", response_model=ProcessResponse)
async def re_summarize(request: ReSummarizeRequest):
    ts = request.ts
    task_dir = os.path.join(TEMP_DIR, ts)
    meta_file = os.path.join(task_dir, "metadata.json")

    if not os.path.exists(meta_file):
        raise HTTPException(status_code=404, detail="找不到该任务的元数据")

    config = load_settings()
    if not config.get("apiKey"):
        raise HTTPException(status_code=400, detail="请先在设置页配置 API Key")

    if request.custom_script is not None:
        script_text = request.custom_script
    else:
        script_file = os.path.join(task_dir, "script.txt")
        if not os.path.exists(script_file):
            raise HTTPException(status_code=404, detail="找不到脚本文件")
        with open(script_file, 'r', encoding='utf-8') as f:
            script_text = f.read()

    with open(meta_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    xhs_copy = await analyze_content(
        metadata.get("title", ""),
        metadata.get("description", ""),
        script_text,
        config=config
    )

    copy_file = os.path.join(task_dir, "xhs_copy.txt")
    with open(copy_file, 'w', encoding='utf-8') as f:
        f.write(xhs_copy)

    base_url = "http://localhost:8000/downloads"
    frames_dir = os.path.join(task_dir, "frames")
    images = []
    if os.path.exists(frames_dir):
        images = [f"{base_url}/{ts}/frames/{f}" for f in sorted(os.listdir(frames_dir)) if f.endswith(".jpg")]

    return ProcessResponse(
        ts=ts,
        metadata=metadata,
        script=script_text,
        audio_rel_path=f"{ts}/audio.m4a",
        frames=images,
        xhs_copy=xhs_copy
    )


# --- 流式处理接口 ---
@app.post("/api/v1/stream-process")
async def stream_process_video(request: VideoRequest):
    config = load_settings()

    async def event_generator():
        try:
            pipeline_gen = pipeline_service.run_pipeline(request.url, config)
            final_data = None

            async for update in pipeline_gen:
                try:
                    update_json = json.loads(update)
                    if "error" in update_json:
                        yield update + "\n"
                        return
                    if "data" in update_json: final_data = update_json["data"]
                    yield update + "\n"
                except:
                    yield update + "\n"

            if final_data:
                if not final_data.get("frames"):
                    yield json.dumps({"error": "提取失败：未获取到有效的视频素材（截图缺失）"}) + "\n"
                    return

                yield json.dumps({"step": "analyzing", "message": "正在生成爆款文案..."}) + "\n"

                xhs_copy = await analyze_content(
                    final_data["metadata"].get("title", "无标题"),
                    final_data["metadata"].get("description", "无描述"),
                    final_data["script"],
                    config=config
                )

                ts = final_data["ts"]
                task_dir = os.path.join(TEMP_DIR, ts)
                copy_file = os.path.join(task_dir, "xhs_copy.txt")
                with open(copy_file, 'w', encoding='utf-8') as f:
                    f.write(xhs_copy)

                final_response = {
                    "ts": ts,
                    "metadata": final_data["metadata"],
                    "script": final_data["script"],
                    "audio_rel_path": final_data['audio_rel_path'],
                    "frames": [f"http://localhost:8000/downloads/{p}" for p in final_data['frames']],
                    "xhs_copy": xhs_copy
                }
                yield json.dumps({"step": "done", "data": final_response}) + "\n"
            else:
                yield json.dumps({"error": "未知错误：流程异常中断，未获取到数据"}) + "\n"

        except Exception as e:
            err_msg = f"流式处理异常: {str(e)}"
            print(f"❌ {err_msg}")
            yield json.dumps({"error": err_msg}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8000)
