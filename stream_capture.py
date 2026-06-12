"""
快手直播流地址提取模块
使用 Playwright 打开直播页面，拦截网络请求获取 m3u8/flv 流地址
"""

import re
import json
import asyncio
from typing import Optional
from playwright.async_api import async_playwright


async def extract_stream_url(live_url: str, timeout: int = 30) -> Optional[str]:
    """
    从快手直播页面提取视频流地址

    Args:
        live_url: 快手直播链接 (如 https://live.kuaishou.com/u/XXX)
        timeout: 等待流地址的超时时间(秒)

    Returns:
        m3u8 或 flv 流地址，失败返回 None
    """
    stream_urls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # 拦截网络请求，寻找流地址
        async def on_response(response):
            url = response.url
            if any(ext in url for ext in [".m3u8", ".flv", "live_stream", "pull-flv", "pull-hls"]):
                stream_urls.append(url)

        page.on("response", on_response)

        print(f"  正在访问直播页面...")
        try:
            await page.goto(live_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        except Exception:
            pass

        # 方法1: 网络请求捕获
        if stream_urls:
            await browser.close()
            return stream_urls[0]

        # 方法2: __INITIAL_STATE__
        try:
            state = await page.evaluate("() => window.__INITIAL_STATE__")
            if state:
                state_str = json.dumps(state)
                for pattern in [r'(https?://[^"]*\.m3u8[^"]*)', r'(https?://[^"]*\.flv[^"]*)']:
                    matches = re.findall(pattern, state_str)
                    if matches:
                        await browser.close()
                        return matches[0]
        except Exception:
            pass

        # 方法3: 页面源码匹配
        try:
            content = await page.content()
            for pattern in [
                r'(https?://[^"\']*\.m3u8[^"\']*)',
                r'(https?://[^"\']*\.flv[^"\']*)',
                r'playUrl["\s:]+["\']([^"\']+\.m3u8)',
                r'playUrl["\s:]+["\']([^"\']+\.flv)',
            ]:
                matches = re.findall(pattern, content)
                if matches:
                    await browser.close()
                    return matches[0]
        except Exception:
            pass

        # 方法4: 等待网络请求
        await asyncio.sleep(min(timeout, 15))
        if stream_urls:
            await browser.close()
            return stream_urls[0]

        await browser.close()

    return None


def extract_stream_url_sync(live_url: str, timeout: int = 30) -> Optional[str]:
    """同步包装函数"""
    return asyncio.run(extract_stream_url(live_url, timeout))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python stream_capture.py <快手直播链接>")
        sys.exit(1)
    result = extract_stream_url_sync(sys.argv[1])
    if result:
        print(f"流地址: {result}")
    else:
        print("未找到流地址")
