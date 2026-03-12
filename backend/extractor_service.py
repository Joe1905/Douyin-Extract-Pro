import os
import asyncio
import re
import json
import httpx
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page

# --- 配置区 ---
HEADLESS_MODE = False # 设为 False 可以看到浏览器操作，方便调试
DESKTOP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
MIN_AUDIO_SIZE_BYTES = 500 * 1024 # 忽略小于 500KB 的媒体文件
# ----------------

async def extract_video_data(video_url: str, output_dir: str = "temp_downloads"):
    """
    使用 Playwright (匿名模式) 打开抖音视频页，通过精准拦截和体积过滤，提取主视频音频。
    """
    print(f"🚀 [精准模式] 开始提取任务: {video_url}")
    
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "extracted_audio.mp4")
    
    if os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except OSError:
            pass

    metadata = {
        "title": "",
        "description": "",
        "audio_url": "",
        "local_audio_path": ""
    }

    async with async_playwright() as p:
        browser = None
        context = None
        page = None
        try:
            print("正在启动浏览器...")
            browser = await p.chromium.launch(
                headless=HEADLESS_MODE,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            context = await browser.new_context(
                user_agent=DESKTOP_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN"
            )
            
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

            page = await context.new_page()
            
            # “多中选优”策略：搜集所有可能的媒体请求
            candidate_media = []

            async def handle_response(response):
                try:
                    # 1. 检查 Content-Type 和 URL 关键字
                    content_type = response.headers.get("content-type", "").lower()
                    url = response.url
                    
                    is_media = "video" in content_type or "audio" in content_type
                    
                    # 抖音主视频通常在 v16-webapp.douyinvod.com 等域名下
                    # 宽松匹配：只要是 douyinvod 或 v1- v3- 开头的
                    has_keywords = any(kw in url for kw in ['douyinvod.com', 'v1-', 'v3-', 'v6-', 'v9-'])
                    is_not_ad = not any(kw in url for kw in ['ads', 'pre-roll', 'commercial', 'p1-'])

                    if not (is_media and has_keywords and is_not_ad):
                        return

                    # 2. 体积过滤
                    content_length_str = response.headers.get("content-length")
                    if not content_length_str:
                        return
                    
                    content_length = int(content_length_str)
                    if content_length < MIN_AUDIO_SIZE_BYTES:
                        print(f"📦 忽略小体积媒体 ({content_length / 1024:.1f} KB): {url[:60]}...")
                        return

                    # 3. 添加到候选列表
                    print(f"🎯 发现候选媒体! 大小: {content_length / 1024:.1f} KB, URL: {url[:60]}...")
                    
                    # 避免重复
                    if not any(c['url'] == url for c in candidate_media):
                        candidate_media.append({'url': url, 'size': content_length})
                except Exception as e:
                    print(f"⚠️ 处理响应时出错: {e}")

            page.on("response", handle_response)

            print(f"正在导航至: {video_url}")
            await page.goto(video_url, timeout=60000, wait_until="domcontentloaded")
            
            # 自动关闭登录弹窗
            print("等待并处理登录弹窗...")
            try:
                # 等待遮罩层出现，最多等5秒
                # 尝试点击 ESC 关闭任何弹窗
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)
                
                # 尝试查找并点击关闭按钮
                close_btn = await page.query_selector('.dy-account-close')
                if close_btn:
                    await close_btn.click()
                    print("已点击关闭登录弹窗按钮")
            except Exception:
                pass

            # 等待一段时间，让所有媒体请求充分加载
            print("等待媒体资源加载 (5秒)...")
            await asyncio.sleep(5)

            # DOM 辅助定位
            try:
                video_element = await page.query_selector('video')
                if video_element:
                    video_src = await video_element.get_attribute('src')
                    if video_src and video_src.startswith('blob:'):
                        print("ℹ️ DOM 辅助：检测到 <video> 标签使用 blob: src，确认需依赖网络拦截。")
                    elif video_src:
                        print(f"ℹ️ DOM 辅助：检测到 <video> 标签 src: {video_src[:60]}...")
            except Exception as e:
                print(f"⚠️ DOM 辅助定位失败: {e}")

            # 最终选择：选择体积最大的媒体文件
            if not candidate_media:
                print("❌ 未捕获到任何符合条件的媒体文件。")
                return None

            # 按大小降序排列
            candidate_media.sort(key=lambda x: x['size'], reverse=True)
            best_candidate = candidate_media[0]
            
            metadata["audio_url"] = best_candidate['url']
            print(f"✅ 最终选择: 体积最大的媒体文件 ({best_candidate['size'] / 1024 / 1024:.2f} MB)")

            # 下载音频
            print("正在下载音频...")
            headers = {"User-Agent": DESKTOP_USER_AGENT, "Referer": "https://www.douyin.com/"}
            
            # 使用 httpx 下载
            async with httpx.AsyncClient(headers=headers, verify=False) as client:
                try:
                    resp = await client.get(metadata["audio_url"], follow_redirects=True, timeout=120)
                    if resp.status_code == 200:
                        with open(audio_path, "wb") as f:
                            f.write(resp.content)
                        metadata["local_audio_path"] = audio_path
                        print(f"✅ 音频已保存至: {audio_path}")
                    else:
                        print(f"❌ 下载失败，状态码: {resp.status_code}")
                        metadata["audio_url"] = "" # 下载失败则清空
                except Exception as e:
                     print(f"❌ 下载过程中发生异常: {e}")
                     metadata["audio_url"] = ""

            # 提取标题和描述
            try:
                # 尝试获取 h1 (通常是描述)
                title_element = await page.query_selector('h1')
                if title_element:
                    text = await title_element.inner_text()
                    metadata["description"] = text
                    metadata["title"] = text[:50]
                
                # 尝试获取作者
                author_element = await page.query_selector('[data-e2e="video-author-uniqueid"]')
                if author_element:
                     print(f"👤 作者: {await author_element.inner_text()}")

            except Exception as e:
                print(f"⚠️ 提取元数据失败: {e}")

            return metadata

        except Exception as e:
            print(f"❌ 发生严重错误: {e}")
            return None
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()
            print("浏览器资源已释放。")

# --- 单元测试 ---
if __name__ == "__main__":
    # 测试用的链接
    test_url = "https://v.douyin.com/nek2YnKDCLg/"
    asyncio.run(extract_video_data(test_url))
