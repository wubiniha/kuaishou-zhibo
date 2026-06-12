"""
直播视频分析模块（高质量版）
- 镜头切割 + 分类 (PySceneDetect + CV 启发式)
- 语音转文字 (faster-whisper large-v3 + 标点恢复)
- 关键词提取 + 话术统计
- HTML 可视化报告
"""

import os
import re
import csv
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

import cv2
import numpy as np


# ============================================================
# 镜头切割
# ============================================================

def detect_shots(video_path: str, threshold: float = 27.0) -> List[dict]:
    """
    检测镜头切换，返回每个镜头的时间段
    """
    print("  [镜头] 检测镜头切换...")
    scenes = _detect_shots_scenedetect(video_path, threshold)

    if not scenes:
        print("  [镜头] scenedetect 无结果，使用 ffmpeg 备选方案")
        scenes = _detect_shots_ffmpeg(video_path)

    # 分类每个镜头
    print("  [镜头] 分类镜头类型...")
    for scene in scenes:
        scene["type"] = _classify_shot(video_path, scene["start"], scene["end"])

    print(f"  [镜头] 共 {len(scenes)} 个镜头")
    return scenes


def _detect_shots_scenedetect(video_path: str, threshold: float) -> List[dict]:
    """PySceneDetect 检测"""
    tmp_csv = "/tmp/_scenedetect_scenes.csv"
    cmd = [
        "scenedetect", "-i", video_path,
        "detect-content", "-t", str(threshold),
        "list-scenes", "-o", "/tmp", "-f", "_scenedetect_scenes.csv",
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=600)
    except Exception:
        return []

    scenes = []
    if os.path.exists(tmp_csv):
        with open(tmp_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start = float(row.get("Start Time (seconds)", 0))
                    end = float(row.get("End Time (seconds)", 0))
                    scenes.append(_make_scene(start, end))
                except (ValueError, KeyError):
                    continue
        os.remove(tmp_csv)
    return scenes


def _detect_shots_ffmpeg(video_path: str) -> List[dict]:
    """ffmpeg scene filter 备选"""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", "select='gt(scene,0.3)',showinfo",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        cut_points = [0.0]
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                try:
                    pts = float(line.split("pts_time:")[1].split()[0])
                    cut_points.append(pts)
                except (IndexError, ValueError):
                    continue
        duration = _get_duration(video_path)
        cut_points.append(duration)
        return [_make_scene(cut_points[i], cut_points[i+1]) for i in range(len(cut_points)-1)]
    except Exception:
        return []


def _make_scene(start: float, end: float) -> dict:
    return {
        "start": start, "end": end,
        "start_str": _fmt(start), "end_str": _fmt(end),
        "duration": round(end - start, 2),
        "type": "unknown",
    }


# ============================================================
# 镜头分类（基于 OpenCV 启发式）
# ============================================================

def _classify_shot(video_path: str, start: float, end: float) -> str:
    """
    分类镜头类型：person / product / text / scene / transition
    基于中间帧的视觉特征
    """
    mid = (start + end) / 2
    frame = _extract_frame(video_path, mid)
    if frame is None:
        return "unknown"

    h, w = frame.shape[:2]

    # 1. 检测人脸（皮肤色区域）
    skin_ratio = _skin_color_ratio(frame)

    # 2. 边缘密度（文字通常边缘密集）
    edge_density = _edge_density(frame)

    # 3. 中心区域关注度
    center_focus = _center_focus(frame)

    # 4. 颜色丰富度
    color_var = _color_variance(frame)

    # 分类逻辑
    if skin_ratio > 0.15 and center_focus > 0.3:
        return "person"
    elif edge_density > 0.12:
        return "text"
    elif color_var < 30 and center_focus > 0.4:
        return "product"
    elif skin_ratio < 0.05 and edge_density < 0.08:
        return "scene"
    else:
        return "transition"


def _extract_frame(video_path: str, timestamp: float) -> Optional[np.ndarray]:
    """提取指定时间的帧"""
    cmd = [
        "ffmpeg", "-ss", str(timestamp), "-i", video_path,
        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and len(result.stdout) > 0:
            # 需要知道帧尺寸，先获取
            info = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height",
                 "-of", "csv=p=0", video_path],
                capture_output=True, text=True, timeout=10
            )
            w, h = map(int, info.stdout.strip().split(","))
            return np.frombuffer(result.stdout, dtype=np.uint8).reshape(h, w, 3)
    except Exception:
        pass
    return None


def _skin_color_ratio(frame: np.ndarray) -> float:
    """计算皮肤色区域占比"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # 肤色范围（HSV）
    lower = np.array([0, 30, 60])
    upper = np.array([20, 170, 255])
    mask = cv2.inRange(hsv, lower, upper)
    return np.sum(mask > 0) / mask.size


def _edge_density(frame: np.ndarray) -> float:
    """边缘密度（Canny）"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    return np.sum(edges > 0) / edges.size


def _center_focus(frame: np.ndarray) -> float:
    """中心区域关注度"""
    h, w = frame.shape[:2]
    center = frame[h//4:3*h//4, w//4:3*w//4]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    center_gray = gray[h//4:3*h//4, w//4:3*w//4]
    # 中心区域方差 / 全图方差
    center_var = np.var(center_gray.astype(float))
    full_var = np.var(gray.astype(float)) + 1e-6
    return min(center_var / full_var, 2.0)


def _color_variance(frame: np.ndarray) -> float:
    """颜色方差"""
    return float(np.std(frame))


# ============================================================
# 语音转文字（高质量）
# ============================================================

def transcribe_audio(video_path: str, model_size: str = "large-v3") -> List[dict]:
    """
    使用 faster-whisper 转录，带标点恢复和后处理
    """
    print(f"  [语音] 转录中 (模型: {model_size})...")

    # 提取音频
    audio_path = video_path.rsplit(".", 1)[0] + "_audio.wav"
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=300, check=True)
    except Exception as e:
        print(f"  [语音] 音频提取失败: {e}")
        return []

    try:
        from faster_whisper import WhisperModel

        # 根据模型大小选择计算精度
        compute_type = "int8" if model_size in ("tiny", "base", "small") else "float16"
        device = "cpu"

        print(f"  [语音] 加载模型 {model_size}...")
        model = WhisperModel(model_size, device=device, compute_type=compute_type)

        segments, info = model.transcribe(
            audio_path,
            language="zh",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        print(f"  [语音] 语言: {info.language} ({info.language_probability:.0%})")

        results = []
        for seg in segments:
            text = _postprocess_text(seg.text.strip())
            if text:
                results.append({
                    "start": seg.start,
                    "end": seg.end,
                    "start_str": _fmt(seg.start),
                    "end_str": _fmt(seg.end),
                    "text": text,
                })

        print(f"  [语音] 完成，{len(results)} 段")

        if os.path.exists(audio_path):
            os.remove(audio_path)

        return results

    except ImportError:
        print("  [语音] faster-whisper 未安装")
        return []
    except Exception as e:
        print(f"  [语音] 转录失败: {e}")
        return []


def _postprocess_text(text: str) -> str:
    """话术后处理：标点恢复、去噪"""
    if not text:
        return ""

    # 去除多余空格
    text = re.sub(r'\s+', '', text)

    # 简单标点恢复
    # 在常见断句位置加标点
    text = re.sub(r'(好的|可以|对吧|是吧|对不对|是不是|知道吗|明白吗)', r'\1。', text)
    text = re.sub(r'(然后|那么|接下来|首先|其次|最后)', r'，\1', text)
    text = re.sub(r'(宝宝们|家人们|姐妹们|朋友们|亲们)', r'\1，', text)
    text = re.sub(r'(一号链接|二号链接|三号链接|链接)', r'\1，', text)

    # 去除重复标点
    text = re.sub(r'[，,]{2,}', '，', text)
    text = re.sub(r'[。.]{2,}', '。', text)

    # 如果没有句尾标点，加一个
    if text and text[-1] not in '。！？!?':
        text += '。'

    return text


# ============================================================
# 关键词提取
# ============================================================

def extract_keywords(transcript: List[dict]) -> Dict[str, int]:
    """提取高频关键词"""
    # 直播带货常见关键词
    hot_words = [
        "宝宝", "家人们", "姐妹", "链接", "一号", "二号", "三号",
        "拍", "买", "送", "优惠", "活动", "秒杀", "限时", "抢购",
        "面膜", "洁面", "护肤", "美白", "补水", "保湿", "控油",
        "去黑头", "清洁", "毛孔", "精华", "水乳", "防晒",
        "好用", "推荐", "回购", "囤货", "性价比", "正品",
        "关注", "点赞", "分享", "直播间", "粉丝",
    ]

    full_text = " ".join(t["text"] for t in transcript)
    word_counts = Counter()
    for word in hot_words:
        count = full_text.count(word)
        if count > 0:
            word_counts[word] = count

    return dict(word_counts.most_common(20))


# ============================================================
# 报告生成
# ============================================================

def generate_report(
    video_path: str,
    scenes: List[dict],
    transcript: List[dict],
    output_dir: str = "output/reports",
) -> str:
    """生成高质量 HTML 分析报告"""
    os.makedirs(output_dir, exist_ok=True)
    video_name = os.path.basename(video_path)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"report_{ts}.html")
    txt_path = os.path.join(output_dir, f"transcript_{ts}.txt")

    total_duration = _get_duration(video_path)
    keywords = extract_keywords(transcript)
    full_text = " ".join(t["text"] for t in transcript)

    # 镜头类型统计
    type_counts = Counter(s["type"] for s in scenes)

    # 镜头-话术映射
    scene_texts = []
    for s in scenes:
        texts = [t["text"] for t in transcript
                 if t["start"] >= s["start"] - 1 and t["end"] <= s["end"] + 1]
        scene_texts.append({**s, "text": " ".join(texts) if texts else "（无语音）"})

    # 生成 HTML
    html = _build_html(
        video_name=video_name,
        total_duration=total_duration,
        scenes=scene_texts,
        transcript=transcript,
        keywords=keywords,
        type_counts=dict(type_counts),
        full_text=full_text,
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 纯文本转录稿
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"=== 直播话术转录 ===\n")
        f.write(f"视频: {video_name}\n")
        f.write(f"时长: {_fmt(total_duration)}\n")
        f.write(f"转录时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{'='*50}\n\n")
        for t in transcript:
            f.write(f"[{t['start_str']} → {t['end_str']}] {t['text']}\n")
        f.write(f"\n{'='*50}\n")
        f.write(f"=== 关键词统计 ===\n")
        for word, count in keywords.items():
            f.write(f"  {word}: {count} 次\n")

    print(f"  [报告] {report_path}")
    print(f"  [转录] {txt_path}")
    return report_path


# ============================================================
# HTML 构建
# ============================================================

TYPE_LABELS = {
    "person": ("👤 人物", "#4f46e5"),
    "product": ("📦 产品", "#10b981"),
    "text": ("📝 文字", "#f59e0b"),
    "scene": ("🏞️ 场景", "#06b6d4"),
    "transition": ("🔄 过渡", "#94a3b8"),
    "unknown": ("❓ 未知", "#e2e8f0"),
}


def _build_html(video_name, total_duration, scenes, transcript, keywords, type_counts, full_text):
    word_count = len(full_text)
    scene_count = len(scenes)
    avg_dur = round(sum(s["duration"] for s in scenes) / max(scene_count, 1), 1)

    # 镜头表格
    scene_rows = ""
    for i, s in enumerate(scenes, 1):
        label, color = TYPE_LABELS.get(s["type"], ("❓ 未知", "#e2e8f0"))
        text_prev = s["text"][:60] + ("..." if len(s["text"]) > 60 else "")
        scene_rows += f"""<tr>
            <td>{i}</td><td>{s['start_str']}</td><td>{s['end_str']}</td>
            <td>{s['duration']}s</td>
            <td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">{label}</span></td>
            <td class="text-cell">{text_prev}</td></tr>"""

    # 话术时间线
    transcript_html = ""
    for t in transcript:
        transcript_html += f"""<div class="ts-item">
            <span class="ts-time">[{t['start_str']}]</span>
            <span class="ts-text">{t['text']}</span></div>"""

    # 关键词
    kw_html = ""
    for word, count in sorted(keywords.items(), key=lambda x: -x[1])[:15]:
        bar_w = min(count * 20, 200)
        kw_html += f"""<div class="kw-row">
            <span class="kw-word">{word}</span>
            <span class="kw-bar" style="width:{bar_w}px"></span>
            <span class="kw-count">{count}次</span></div>"""

    # 镜头类型分布
    type_html = ""
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        label, color = TYPE_LABELS.get(t, ("❓", "#e2e8f0"))
        pct = round(count / max(scene_count, 1) * 100)
        type_html += f"""<div class="type-row">
            <span style="color:{color};font-weight:600;">{label}</span>
            <span class="type-bar-bg"><span class="type-bar" style="width:{pct}%;background:{color}"></span></span>
            <span>{count}个 ({pct}%)</span></div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>直播分析报告</title>
<style>
:root{{--p:#7c3aed;--s:#10b981;--w:#f59e0b;--d:#ef4444;--bg:#faf5ff;--card:#fff;--t:#1e293b;--ts:#64748b;--b:#e9d5ff}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--t);padding:20px;line-height:1.6}}
.ct{{max-width:1200px;margin:0 auto}}
.hd{{background:linear-gradient(135deg,#7c3aed,#c084fc);color:#fff;border-radius:16px;padding:32px 36px;margin-bottom:20px}}
.hd h1{{font-size:22px;margin-bottom:6px}}.hd .sub{{opacity:.8;font-size:13px}}
.kg{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}}
.k{{background:var(--card);border:1px solid var(--b);border-radius:10px;padding:16px;text-align:center}}
.k .lb{{font-size:11px;color:var(--ts);margin-bottom:4px;text-transform:uppercase}}.k .vl{{font-size:24px;font-weight:700;color:var(--p)}}
.sec{{background:var(--card);border:1px solid var(--b);border-radius:12px;padding:20px;margin-bottom:16px}}
.sec h2{{font-size:16px;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#f5f0ff;padding:8px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase}}
td{{padding:8px;border-bottom:1px solid var(--b)}}
tr:hover td{{background:#faf5ff}}.text-cell{{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ts-item{{padding:8px 12px;border-left:3px solid var(--p);background:#faf5ff;margin-bottom:6px;border-radius:0 6px 6px 0;font-size:13px}}
.ts-time{{color:var(--p);font-weight:600;font-size:11px;margin-right:6px}}
.kw-row{{display:flex;align-items:center;gap:8px;margin-bottom:4px;font-size:13px}}
.kw-word{{min-width:60px;font-weight:500}}.kw-bar{{height:8px;background:var(--p);border-radius:4px;opacity:.6}}.kw-count{{color:var(--ts);font-size:11px}}
.type-row{{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:13px}}
.type-bar-bg{{flex:1;height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden}}.type-bar{{height:100%;border-radius:4px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.ft{{text-align:center;padding:16px;color:#94a3b8;font-size:11px}}
@media(max-width:768px){{.kg{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="ct">
<div class="hd">
  <h1>📺 直播分析报告</h1>
  <div class="sub">{video_name} · {now}</div>
</div>

<div class="kg">
  <div class="k"><div class="lb">时长</div><div class="vl">{_fmt(total_duration)}</div></div>
  <div class="k"><div class="lb">镜头数</div><div class="vl">{scene_count}</div></div>
  <div class="k"><div class="lb">平均镜头</div><div class="vl">{avg_dur}s</div></div>
  <div class="k"><div class="lb">话术字数</div><div class="vl">{word_count}</div></div>
  <div class="k"><div class="lb">话术段数</div><div class="vl">{len(transcript)}</div></div>
</div>

<div class="grid2">
  <div class="sec">
    <h2>📊 镜头类型分布</h2>
    {type_html if type_html else '<div style="color:#94a3b8">暂无数据</div>'}
  </div>
  <div class="sec">
    <h2>🔑 高频关键词</h2>
    {kw_html if kw_html else '<div style="color:#94a3b8">暂无数据</div>'}
  </div>
</div>

<div class="sec">
  <h2>🎬 镜头切割 ({scene_count})</h2>
  <table>
    <thead><tr><th>#</th><th>开始</th><th>结束</th><th>时长</th><th>类型</th><th>话术</th></tr></thead>
    <tbody>{scene_rows if scene_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8">无镜头数据</td></tr>'}</tbody>
  </table>
</div>

<div class="sec">
  <h2>🎙️ 话术转录 ({len(transcript)} 段)</h2>
  {transcript_html if transcript_html else '<div style="color:#94a3b8">无转录数据</div>'}
</div>

<div class="ft">快手直播分析报告 · {now}</div>
</div>
</body>
</html>"""


# ============================================================
# 工具函数
# ============================================================

def _get_duration(path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _fmt(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int((s - int(s)) * 1000)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"
    return f"{m:02d}:{sec:02d}.{ms:03d}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python analyze.py <视频文件> [whisper模型]")
        sys.exit(1)
    video = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "large-v3"
    scenes = detect_shots(video)
    transcript = transcribe_audio(video, model_size=model)
    report = generate_report(video, scenes, transcript)
    print(f"\n报告: {report}")
