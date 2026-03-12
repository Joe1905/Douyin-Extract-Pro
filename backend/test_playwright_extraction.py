import asyncio
import os
import extractor_service

async def main():
    print("🚀 开始测试 Playwright 视频提取服务...")
    
    # 替换为您实际想测试的抖音链接 (短链接或长链接均可)
    test_url = "https://v.douyin.com/gxXMWxazucA"
    
    # 调用提取函数
    result = await extractor_service.extract_video_data(test_url)
    
    if result and result.get("audio_url"):
        print("\n✅ 提取成功!")
        print(f"   - 标题: {result.get('title')}")
        print(f"   - 描述: {result.get('description')}")
        print(f"   - 音频链接: {result.get('audio_url')}")
        print(f"   - 本地保存路径: {result.get('local_audio_path')}")
        
        # 验证文件是否存在
        if os.path.exists(result.get("local_audio_path", "")):
            print("   - 本地文件验证通过: ✅")
        else:
            print("   - 本地文件验证失败: ❌")
            
    else:
        print("\n❌ 提取失败，未能获取音频链接。")
        print("💡 请检查 extractor_service.py 中的 USER_DATA_DIR 设置是否正确。")
        print("💡 尝试在 headless=False 模式下观察浏览器行为。")

if __name__ == "__main__":
    asyncio.run(main())
