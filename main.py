#!/usr/bin/env python3
"""
快手直播录制+分析工具

用法:
    python main.py <快手直播链接>
    python main.py <链接> -d 300
    python main.py --analyze-only video.mp4
    python main.py --stream-url <m3u8地址> -d 120
"""

import argparse
import asyncio
import sys
import os

from stream_capture import extract_stream_url
from stream_record import StreamRecorder
from analyze import detect_shots, transcribe_audio, generate_report

BANNER = """
========================================
  🎥 快手直播录制+分析工具 v2.0
========================================"""


def main():
    parser = argparse.ArgumentParser(
        description="快手直播录制+分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s https://live.kuaishou.com/u/xxx
  %(prog)s https://live.kuaishou.com/u/xxx -d 300
  %(prog)s https://live.kuaishou.com/u/xxx -m medium
  %(prog)s --analyze-only output/recordings/xxx.mp4
        """,
    )
    parser.add_argument("url", nargs="?", help="快手直播链接")
    parser.add_argument("-d", "--duration", type=int, default=60, help="录制时长(秒)，默认60")
    parser.add_argument("-m", "--model", default="large-v3",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper模型，默认large-v3")
    parser.add_argument("-o", "--output-dir", default="output", help="输出目录")
    parser.add_argument("--record-only", action="store_true", help="仅录制不分析")
    parser.add_argument("--analyze-only", type=str, help="仅分析已有视频")
    parser.add_argument("--stream-url", type=str, help="直接指定流地址")

    args = parser.parse_args()
    print(BANNER)

    record_dir = os.path.join(args.output_dir, "recordings")
    report_dir = os.path.join(args.output_dir, "reports")
    os.makedirs(record_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    video_path = None

    # 仅分析
    if args.analyze_only:
        if not os.path.exists(args.analyze_only):
            print(f"\n❌ 文件不存在: {args.analyze_only}")
            sys.exit(1)
        video_path = args.analyze_only
    else:
        stream_url = args.stream_url
        if not stream_url and not args.url:
            print("\n❌ 请提供直播链接或流地址")
            parser.print_help()
            sys.exit(1)

        if not stream_url:
            print(f"\n🔍 提取直播流地址...")
            stream_url = asyncio.run(extract_stream_url(args.url, timeout=20))
            if not stream_url:
                print("\n❌ 未获取到流地址")
                print("   可能原因: 未开播 / 链接错误 / 页面结构变更")
                print(f"   手动指定: python main.py --stream-url <地址> -d {args.duration}")
                sys.exit(1)
            print(f"  ✅ 流地址获取成功")

        print(f"\n🔴 录制中 ({args.duration}秒)...")
        recorder = StreamRecorder(record_dir)
        video_path = recorder.record_sync(stream_url, duration=args.duration)

    # 分析
    if not args.record_only and video_path:
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            print(f"\n❌ 视频文件无效: {video_path}")
            sys.exit(1)

        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"\n{'='*45}")
        print(f"  📊 分析中... ({size_mb:.1f} MB)")
        print(f"{'='*45}")

        scenes = detect_shots(video_path)
        transcript = transcribe_audio(video_path, model_size=args.model)
        report_path = generate_report(video_path, scenes, transcript, report_dir)

        print(f"\n{'='*45}")
        print(f"  ✅ 完成!")
        print(f"{'='*45}")
        print(f"  📹 视频: {video_path}")
        print(f"  📊 报告: {report_path}")
        print(f"  🎬 镜头: {len(scenes)} 个")
        print(f"  🎙️ 话术: {len(transcript)} 段")
    elif args.record_only:
        print(f"\n✅ 录制完成: {video_path}")
        print(f"   分析: python main.py --analyze-only {video_path}")


if __name__ == "__main__":
    main()
