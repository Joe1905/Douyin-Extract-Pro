import os
import sys
import json
import time
import gc
import re
import asyncio
import subprocess
import base64
import traceback
from datetime import datetime
from playwright.async_api import async_playwright
import httpx

# --- 常量定义 ---
DESKTOP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
MIN_MEDIA_SIZE_BYTES = 500 * 1024 
CHUNK_DURATION = 30 

def get_timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def print_step(message):
    print(f"\n🔹 [{get_timestamp()}] {message}")

def print_success(message):
    print(f"✅ [{get_timestamp()}] {message}")

def print_error(message):
    print(f"❌ [{get_timestamp()}] {message}")

async def resolve_final_url(short_url):
    """使用 httpx 请求短链接，获取重定向后的最终长链接。"""
    if not short_url or not short_url.strip().startswith('http'):
        raise ValueError("输入的链接格式不正确，请确保是以 http 开头的视频地址")
        
    print_step(f"开始解析短链接: {short_url}")
    try:
        async with httpx.AsyncClient(follow_redirects=True, headers={'User-Agent': DESKTOP_USER_AGENT}) as client:
            response = await client.head(short_url)
            final_url = str(response.url)
            print_success(f"URL 解析成功: {final_url}")
            return final_url
    except Exception:
        print_error(f"URL 解析异常:\n{traceback.format_exc()}")
        return None

def sanitize_url(url):
    print_step(f"开始标准化 URL: {url}")
    video_id_match = re.search(r'/video/(\d+)', url)
    if video_id_match:
        standard_url = f"https://www.douyin.com/video/{video_id_match.group(1)}"
        print_success(f"URL 标准化完成: {standard_url}")
        return standard_url
    print_error("URL 标准化失败: 未找到 video ID")
    return None

def extract_keyframes(media_path, frames_dir):
    media_path = os.path.abspath(media_path)
    frames_dir = os.path.abspath(frames_dir)
    print_step(f"开始提取关键帧 -> {media_path}")
    
    if not os.path.exists(media_path): 
        print_error(f"媒体文件不存在: {media_path}")
        return []
    
    os.makedirs(frames_dir, exist_ok=True)
    extracted_frames = []
    
    try:
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", media_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        duration_str = result.stdout.strip()
        
        if not duration_str or duration_str == "N/A": 
            print_error(f"无法获取时长 (ffprobe output: {duration_str})")
            return []
            
        duration = float(duration_str)
        
        time_points = [{"time": 0, "suffix": "00"}, {"time": duration * 0.5, "suffix": "50"}, {"time": duration * 0.9, "suffix": "90"}]
        for tp in time_points:
            frame_name = f"frame_{tp['suffix']}.jpg"
            frame_path = os.path.join(frames_dir, frame_name)
            ffmpeg_cmd = ["ffmpeg", "-v", "error", "-ss", str(tp['time']), "-i", media_path, "-vframes", "1", "-q:v", "2", "-y", frame_path]
            subprocess.run(ffmpeg_cmd, check=True)
            extracted_frames.append(frame_name)
            
        return extracted_frames
    except Exception:
        print_error(f"关键帧提取异常:\n{traceback.format_exc()}")
        return []

def split_audio(audio_path, chunks_dir):
    audio_path = os.path.abspath(audio_path)
    chunks_dir = os.path.abspath(chunks_dir)
    print_step(f"开始切分音频 -> {chunks_dir}")
    
    os.makedirs(chunks_dir, exist_ok=True)
    output_pattern = os.path.join(chunks_dir, "chunk_%03d.mp3")
    
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-i", audio_path,
            "-f", "segment", "-segment_time", str(CHUNK_DURATION),
            "-ac", "1", "-ar", "16000", 
            "-c:a", "libmp3lame", "-q:a", "4",
            "-reset_timestamps", "1",
            output_pattern
        ]
        subprocess.run(cmd, check=True)
        chunks = sorted([os.path.join(chunks_dir, f) for f in os.listdir(chunks_dir) if f.startswith("chunk_")])
        print_success(f"切分完成，共 {len(chunks)} 个片段")
        return chunks
    except Exception:
        print_error(f"音频切分异常:\n{traceback.format_exc()}")
        return []

async def request_single_chunk_glm(client, audio_chunk_path, api_key):
    try:
        with open(audio_chunk_path, "rb") as audio_file:
            base64_str = base64.b64encode(audio_file.read()).decode('utf-8')
        
        url = "https://api.ppio.com/v3/glm-asr"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"file": base64_str, "prompt": "短视频转录"}
        
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json().get("text", "")
        else:
            print_error(f"ASR 请求失败 ({response.status_code}): {response.text}")
            return ""
    except Exception:
        print_error(f"ASR 请求异常:\n{traceback.format_exc()}")
        return ""

async def run_pipeline(video_url: str, config: dict):
    yield json.dumps({"step": "init", "message": f"[{get_timestamp()}] 初始化任务..."})
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    task_dir = os.path.abspath(os.path.join(base_dir, "temp_downloads", ts))
    os.makedirs(task_dir, exist_ok=True)
    
    output_filepath = os.path.join(task_dir, "audio.m4a")
    frames_dir = os.path.join(task_dir, "frames")
    chunks_dir = os.path.join(task_dir, "chunks")
    script_filepath = os.path.join(task_dir, "script.txt")
    metadata_filepath = os.path.join(task_dir, "metadata.json")

    try:
        # --- 1. 解析 ---
        yield json.dumps({"step": "resolve_url", "message": f"[{get_timestamp()}] 解析 URL: {video_url}"})
        resolved_url = await resolve_final_url(video_url)
        if not resolved_url:
            raise ValueError("URL 解析失败，请检查链接是否有效")
        
        final_url = sanitize_url(resolved_url) or resolved_url
        print_step(f"最终访问 URL: {final_url}")

        # --- 2. 提取 ---
        yield json.dumps({"step": "extract_video", "message": f"[{get_timestamp()}] 启动 Playwright 抓取..."})
        
        browser = None
        context = None
        page = None
        media_downloaded = False
        video_meta = {"title": "", "description": ""}

        try:
            print_step("正在启动 Playwright Chromium...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
                context = await browser.new_context(user_agent=DESKTOP_USER_AGENT, viewport={"width": 1280, "height": 720})
                page = await context.new_page()

                candidate_media = []
                async def handle_response(response):
                    try:
                        ctype = response.headers.get("content-type", "").lower()
                        if "video" not in ctype and "audio" not in ctype: return
                        clength = int(response.headers.get("content-length", 0))
                        if clength < MIN_MEDIA_SIZE_BYTES: return
                        if not any(c['url'] == response.url for c in candidate_media):
                            print_success(f"捕获候选媒体: {response.url[:80]}... (Size: {clength/1024/1024:.2f} MB)")
                            candidate_media.append({'url': response.url, 'size': clength})
                    except: pass

                page.on("response", handle_response)
                await page.goto(final_url, timeout=60000, wait_until="domcontentloaded")
                
                try: await page.keyboard.press("Escape", delay=1000)
                except Exception: pass
                
                for i in range(5):
                    yield json.dumps({"step": "loading_media", "message": f"[{get_timestamp()}] 等待媒体加载 ({i+1}/5s)..."})
                    await asyncio.sleep(1)

                if not candidate_media:
                    raise ValueError("未捕获到任何符合条件的媒体请求！")

                best = max(candidate_media, key=lambda x: x['size'])
                yield json.dumps({"step": "download_audio", "message": f"[{get_timestamp()}] 正在下载媒体文件..."})
                
                dl_kwargs = {"headers": {'User-Agent': DESKTOP_USER_AGENT, 'Referer': 'https://www.douyin.com/'}, "verify": False}
                if config.get("proxyUrl"): dl_kwargs["proxy"] = config.get("proxyUrl")
                
                async with httpx.AsyncClient(**dl_kwargs) as client:
                    resp = await client.get(best['url'], follow_redirects=True, timeout=120)
                    if resp.status_code == 200:
                        with open(output_filepath, "wb") as f: f.write(resp.content)
                        media_downloaded = True
                        print_success(f"下载完成: {output_filepath}")
                    else:
                        raise ValueError(f"下载失败: HTTP {resp.status_code}")

                video_meta["title"] = await page.title()
                try:
                    h1 = await page.query_selector('h1')
                    if h1: video_meta["description"] = await h1.inner_text()
                except Exception: pass

        except Exception as e:
            raise e
        finally:
            print_step("清理浏览器资源...")
            if page: 
                try: await page.close()
                except: pass
            if context:
                try: await context.close()
                except: pass
            if browser:
                try: await browser.close()
                except: pass
            gc.collect()
            time.sleep(0.5)

        if not media_downloaded:
            raise ValueError("严重错误：媒体文件未能成功下载，流程终止。")

        # --- 3. 预处理 ---
        with open(metadata_filepath, 'w', encoding='utf-8') as f:
            json.dump(video_meta, f, ensure_ascii=False, indent=4)

        yield json.dumps({"step": "extract_frames", "message": f"[{get_timestamp()}] 正在提取关键帧..."})
        frames = extract_keyframes(output_filepath, frames_dir)
        if not frames:
             raise ValueError("关键帧提取失败，无法继续。")

        # --- 4. ASR 转录 ---
        script_text = ""
        api_key = config.get("apiKey")
        
        if api_key:
            yield json.dumps({"step": "splitting_audio", "message": f"[{get_timestamp()}] 正在优化音频并快速切片..."})
            chunks = split_audio(output_filepath, chunks_dir)
            
            if chunks:
                client_kwargs = {"timeout": 60.0}
                if config.get("proxyUrl"): client_kwargs["proxy"] = config.get("proxyUrl")
                
                full_transcript = []
                async with httpx.AsyncClient(**client_kwargs) as client:
                    total_chunks = len(chunks)
                    for idx, chunk in enumerate(chunks):
                        msg = f"正在识别第 {idx+1}/{total_chunks} 段音频..."
                        yield json.dumps({"step": "asr_processing", "message": f"[{get_timestamp()}] {msg}"})
                        
                        text = await request_single_chunk_glm(client, chunk, api_key)
                        if text: full_transcript.append(text)
                        await asyncio.sleep(0.5)
                
                script_text = " ".join(full_transcript)
                if not script_text.strip():
                     raise ValueError("ASR 转录结果为空，请检查音频质量或 API 额度。")

                with open(script_filepath, 'w', encoding='utf-8') as f:
                    f.write(script_text)
            else:
                 raise ValueError("音频切片失败，无法进行 ASR。")
        else:
            yield json.dumps({"step": "skip_asr", "message": "未配置 API Key，跳过转录。"})

        # --- 5. 验证与完成 ---
        if api_key and not script_text.strip():
             raise ValueError("ASR 转录结果为空。")
        
        # 字段名唯一事实来源：必须使用 frames
        result_data = {
            "ts": ts,
            "metadata": video_meta,
            "script": script_text,
            "audio_rel_path": f"{ts}/audio.m4a",
            "frames": [f"{ts}/frames/{f}" for f in frames] # 这里的 key 是 frames
        }

        yield json.dumps({"step": "complete", "data": result_data})

    except Exception as e:
        err_msg = str(e)
        print_error(f"任务中断: {err_msg}")
        yield json.dumps({"error": err_msg})
