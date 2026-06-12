"""
直播流录制模块
使用 ffmpeg 录制 m3u8/flv 流为 mp4 文件
"""

import os
import subprocess
import signal
import time
from datetime import datetime
from typing import Optional


class StreamRecorder:
    """直播流录制器"""

    def __init__(self, output_dir: str = "output/recordings"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.process: Optional[subprocess.Popen] = None

    def record(
        self,
        stream_url: str,
        duration: Optional[int] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        录制直播流

        Args:
            stream_url: 直播流地址 (m3u8/flv)
            duration: 录制时长(秒)，None 表示录制到直播结束
            filename: 输出文件名，None 则自动生成

        Returns:
            录制文件的路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"live_{timestamp}.mp4"

        output_path = os.path.join(self.output_dir, filename)

        # 构建 ffmpeg 命令
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖已有文件
            "-i", stream_url,
            "-c", "copy",  # 不重新编码，直接复制流
            "-bsf:a", "aac_adtstoasc",  # AAC 音频封装修复
        ]

        if duration:
            cmd.extend(["-t", str(duration)])

        cmd.append(output_path)

        print(f"  [录制] 开始录制: {output_path}")
        print(f"  [录制] 流地址: {stream_url[:80]}...")
        if duration:
            print(f"  [录制] 录制时长: {duration} 秒")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return output_path

    def record_sync(
        self,
        stream_url: str,
        duration: Optional[int] = None,
        filename: Optional[str] = None,
    ) -> str:
        """同步录制（会阻塞直到录制完成）"""
        output_path = self.record(stream_url, duration, filename)

        try:
            self.process.wait()
        except KeyboardInterrupt:
            print("\n  [中断] 用户中断录制")
            self.stop()

        # 检查录制结果
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  [完成] 录制完成: {output_path} ({size_mb:.1f} MB)")
        else:
            print(f"  [错误] 录制文件为空或不存在")

        return output_path

    def stop(self):
        """停止录制"""
        if self.process and self.process.poll() is None:
            # 发送 SIGINT 让 ffmpeg 优雅退出（保存文件）
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            print("  [停止] 录制已停止")

    @property
    def is_recording(self) -> bool:
        return self.process is not None and self.process.poll() is None


def record_live(stream_url: str, duration: int = 60, output_dir: str = "output/recordings") -> str:
    """
    便捷函数：录制直播流

    Args:
        stream_url: 流地址
        duration: 录制时长（秒）
        output_dir: 输出目录

    Returns:
        录制文件路径
    """
    recorder = StreamRecorder(output_dir)
    return recorder.record_sync(stream_url, duration=duration)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python stream_record.py <流地址> [时长秒数]")
        sys.exit(1)

    url = sys.argv[1]
    dur = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    record_live(url, duration=dur)
