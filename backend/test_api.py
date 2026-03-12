import os
import sys
import json
import time
import gc
import re
import asyncio
import subprocess
import base64
from datetime import datetime
from playwright.async_api import async_playwright
import httpx

# --- 配置区 ---
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "settings.json")
TEST_VIDEO_URL = "https://v.douyin.com/gxXMWxazucA/"
DESKTOP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
MIN_MEDIA_SIZE_BYTES = 500 * 1024 
CHUNK_DURATION = 30 # 切片时长 30秒
# ----------------

def print_step(message):
    print(f"\n🔹 {message}...")

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print_error(f"配置文件未找到: {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print_error(f"加载配置文件失败: {e}")
        return None

async def resolve_final_url(short_url):
    print_step(f"正在解析短链接: {short_url}")
    try:
        async with httpx.AsyncClient(follow_redirects=True, headers={'User-Agent': DESKTOP_USER_AGENT}) as client:
            response = await client.head(short_url)
            final_url = str(response.url)
            print_success(f"解析到最终 URL: {final_url}")
            return final_url
    except httpx.RequestError as e:
        print_error(f"解析 URL 失败: {e}")
        return None

def sanitize_url(url):
    video_id_match = re.search(r'/video/(\d+)', url)
    if video_id_match:
        return f"https://www.douyin.com/video/{video_id_match.group(1)}"
    return None

def extract_keyframes(media_path, frames_dir):
    print_step(f"正在从 {media_path} 提取关键帧...")
    if not os.path.exists(media_path): return []
    os.makedirs(frames_dir, exist_ok=True)
    extracted_frames = []
    try:
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", media_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        duration_str = result.stdout.strip()
        if not duration_str or duration_str == "N/A": return []
        duration = float(duration_str)
        time_points = [{"time": 0, "suffix": "00"}, {"time": duration * 0.5, "suffix": "50"}, {"time": duration * 0.9, "suffix": "90"}]
        for tp in time_points:
            frame_path = os.path.join(frames_dir, f"frame_{tp['suffix']}.jpg")
            ffmpeg_cmd = ["ffmpeg", "-v", "error", "-ss", str(tp['time']), "-i", media_path, "-vframes", "1", "-q:v", "2", "-y", frame_path]
            subprocess.run(ffmpeg_cmd, check=True)
            extracted_frames.append(frame_path)
        return extracted_frames
    except Exception as e:
        print_error(f"提取关键帧失败: {e}")
        return []

def split_audio(audio_path, chunks_dir):
    """
    使用 FFmpeg 将音频切分为 30 秒的小段 MP3，并强制转换为单声道 (Mono) 16kHz。
    """
    print_step("正在切分并标准化音频文件...")
    os.makedirs(chunks_dir, exist_ok=True)
    
    output_pattern = os.path.join(chunks_dir, "chunk_%03d.mp3")
    
    try:
        # -ac 1: 强制单声道
        # -ar 16000: 强制采样率 16kHz (ASR 标准)
        # -f segment: 切分
        cmd = [
            "ffmpeg", "-v", "error", "-i", audio_path,
            "-f", "segment", "-segment_time", str(CHUNK_DURATION),
            "-ac", "1", "-ar", "16000",
            "-c:a", "libmp3lame", "-q:a", "2",
            "-reset_timestamps", "1",
            output_pattern
        ]
        subprocess.run(cmd, check=True)
        
        chunks = sorted([os.path.join(chunks_dir, f) for f in os.listdir(chunks_dir) if f.startswith("chunk_")])
        print_success(f"音频已标准化并切分为 {len(chunks)} 个片段。")
        return chunks
        
    except subprocess.CalledProcessError as e:
        print_error(f"音频切分失败: {e}")
        return []

async def request_single_chunk_glm(client, audio_chunk_path, api_key):
    """
    处理单个音频切片：Base64 编码 -> PPIO GLM-ASR v3 请求
    """
    filename = os.path.basename(audio_chunk_path)
    
    try:
        with open(audio_chunk_path, "rb") as audio_file:
            base64_str = base64.b64encode(audio_file.read()).decode('utf-8')

        url = "https://api.ppio.com/v3/glm-asr"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "file": base64_str,
            "prompt": "短视频转录" 
        }

        response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("text", "") 
            return text
        else:
            print_error(f"   [{filename}] ASR 失败 ({response.status_code}): {response.text}")
            return ""
            
    except Exception as e:
        print_error(f"   [{filename}] 请求异常: {e}")
        return ""

async def process_audio_pipeline(audio_path, script_path, chunks_dir, config):
    api_key = config.get("apiKey")
    proxy_url = config.get("proxyUrl")
    
    if not api_key:
        print_error("未配置 API Key，跳过 ASR。")
        return

    # 1. 切分并标准化音频
    chunks = split_audio(audio_path, chunks_dir)
    if not chunks:
        print_error("没有生成有效的音频切片。")
        return

    # 2. 准备客户端
    print_step(f"开始 ASR 队列处理 (共 {len(chunks)} 个分段)...")
    client_kwargs = {"timeout": 60.0}
    if proxy_url and proxy_url.strip():
        client_kwargs["proxy"] = proxy_url.strip()
        print(f"   使用代理: {proxy_url}")

    # 3. 串行处理
    full_transcript = []
    
    async with httpx.AsyncClient(**client_kwargs) as client:
        for i, chunk_path in enumerate(chunks):
            print(f"   [{i+1}/{len(chunks)}] 处理中: {os.path.basename(chunk_path)}")
            text = await request_single_chunk_glm(client, chunk_path, api_key)
            if text:
                full_transcript.append(text)
            await asyncio.sleep(0.5)

    # 4. 合并与保存
    final_text = " ".join(full_transcript)
    try:
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
        print_success(f"全量转录完成! 脚本已保存至: {script_path}")
        print(f"📝 脚本摘要: {final_text[:100]}...")
    except Exception as e:
        print_error(f"保存脚本文件失败: {e}")

async def main():
    config = load_config()
    if not config: sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    task_dir = os.path.join(base_dir, "temp_downloads", ts)
    os.makedirs(task_dir, exist_ok=True)
    
    print(f"🚀 开始执行提取任务 (任务ID: {ts})")
    print(f"📂 任务主目录: {task_dir}")

    output_filepath = os.path.join(task_dir, "audio.m4a")
    frames_dir = os.path.join(task_dir, "frames")
    chunks_dir = os.path.join(task_dir, "chunks")
    script_filepath = os.path.join(task_dir, "script.txt")
    metadata_filepath = os.path.join(task_dir, "metadata.json")

    # --- URL 预处理 ---
    resolved_url = await resolve_final_url(TEST_VIDEO_URL)
    if not resolved_url: sys.exit(1)
    final_processed_url = sanitize_url(resolved_url)
    if not final_processed_url: sys.exit(1)

    # --- Playwright 提取 ---
    browser = None
    context = None
    page = None
    media_downloaded = False
    video_metadata = {"url": final_processed_url}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(user_agent=DESKTOP_USER_AGENT, viewport={"width": 1280, "height": 720})
            page = await context.new_page()

            candidate_media = []
            async def handle_response(response):
                try:
                    content_type = response.headers.get("content-type", "").lower()
                    if "video" not in content_type and "audio" not in content_type: return
                    content_length = int(response.headers.get("content-length", 0))
                    if content_length < MIN_MEDIA_SIZE_BYTES: return
                    if not any(c['url'] == response.url for c in candidate_media):
                        candidate_media.append({'url': response.url, 'size': content_length})
                except: pass

            page.on("response", handle_response)
            await page.goto(final_processed_url, timeout=60000, wait_until="domcontentloaded")
            try: await page.keyboard.press("Escape", delay=1000)
            except: pass
            await asyncio.sleep(5)

            if candidate_media:
                best_candidate = max(candidate_media, key=lambda x: x['size'])
                print_step("正在下载媒体文件...")
                download_client_kwargs = {"headers": {'User-Agent': DESKTOP_USER_AGENT, 'Referer': 'https://www.douyin.com/'}, "verify": False}
                if config.get("proxyUrl"): download_client_kwargs["proxy"] = config.get("proxyUrl")

                async with httpx.AsyncClient(**download_client_kwargs) as client:
                    resp = await client.get(best_candidate['url'], follow_redirects=True, timeout=120)
                    resp.raise_for_status()
                    with open(output_filepath, "wb") as f:
                        f.write(resp.content)
                    media_downloaded = True
                    print_success(f"媒体文件已保存至: {output_filepath}")

            title = await page.title()
            h1 = await page.query_selector('h1')
            desc = await h1.inner_text() if h1 else "无描述"
            video_metadata["title"] = title
            video_metadata["description"] = desc

    except Exception as e:
        print_error(f"Playwright 提取错误: {e}")
    finally:
        print_step("正在关闭浏览器资源...")
        try:
            if 'page' in locals() and page: await page.close()
        except Exception: pass
        try:
            if 'context' in locals() and context: await context.close()
        except Exception: pass
        try:
            if 'browser' in locals() and browser: await browser.close()
        except Exception: pass
        gc.collect()
        time.sleep(0.5)
        print("Playwright 资源已释放。")

    # --- 后处理 ---
    if media_downloaded:
        with open(metadata_filepath, 'w', encoding='utf-8') as f:
            json.dump(video_metadata, f, ensure_ascii=False, indent=4)
        
        extracted_frames = extract_keyframes(output_filepath, frames_dir)
        await process_audio_pipeline(output_filepath, script_filepath, chunks_dir, config)
        
        print("\n" + "="*50)
        print(f"🎉 任务完成！归档目录: {task_dir}")
        print("="*50)
    else:
        print_error("下载失败，无法后续处理。")

if __name__ == "__main__":
    asyncio.run(main())
