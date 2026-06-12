# 🎥 快手直播录制+分析工具

自动录制快手直播并分析：镜头切割 + 话术提取 + 关键词统计。

## ⚡ 快速开始

### 方式一：Windows 可执行文件（推荐）

1. 下载 `kuaishou-live.exe`（从 [Releases](../../releases) 页面下载）
2. 双击运行，或拖拽链接到 exe 上

```
kuaishou-live.exe https://live.kuaishou.com/u/xxx
```

### 方式二：Python 运行

```bash
pip install -r requirements.txt
python main.py https://live.kuaishou.com/u/xxx
```

## 📖 使用方法

```bash
# 录制 60 秒 + 分析（默认）
python main.py https://live.kuaishou.com/u/xxx

# 录制 5 分钟 + 分析
python main.py https://live.kuaishou.com/u/xxx -d 300

# 用 medium 模型（更快，准确度稍低）
python main.py https://live.kuaishou.com/u/xxx -m medium

# 仅录制不分析
python main.py https://live.kuaishou.com/u/xxx --record-only -d 120

# 分析已有视频
python main.py --analyze-only output/recordings/xxx.mp4

# 直接指定流地址
python main.py --stream-url https://xxx.m3u8 -d 300
```

## 📊 输出文件

```
output/
├── recordings/
│   └── live_20260612_1530.mp4          # 录制视频
└── reports/
    ├── report_20260612_1530.html       # 可视化分析报告
    └── transcript_20260612_1530.txt    # 纯文本转录稿
```

### HTML 报告包含：
- 🎬 镜头切割（时间线 + 类型分类：人物/产品/文字/场景）
- 🎙️ 话术转录（带时间戳）
- 🔑 高频关键词统计
- 📊 镜头类型分布

## 🔧 Whisper 模型选择

| 模型 | 大小 | 速度 | 中文准确度 |
|------|------|------|-----------|
| tiny | 39M | ⚡⚡⚡ | ★★☆ |
| base | 74M | ⚡⚡⚡ | ★★★ |
| small | 244M | ⚡⚡ | ★★★★ |
| medium | 769M | ⚡ | ★★★★ |
| **large-v3** | **1.5G** | **⚡** | **★★★★★** |

默认使用 `large-v3`（最佳中文效果）。首次运行自动下载模型。

## 🏗️ 自己构建 Windows exe

```bash
pip install pyinstaller
pyinstaller build_windows.spec --clean
# 输出: dist/kuaishou-live.exe
```

或使用 GitHub Actions：推送 `v*` tag 自动构建。

```bash
git tag v1.0.0
git push origin v1.0.0
# 在 Actions 页面下载构建产物
```

## 📁 项目结构

```
kuaishou-live/
├── main.py                  # 主入口
├── stream_capture.py        # 直播流提取（Playwright）
├── stream_record.py         # 录制模块（ffmpeg）
├── analyze.py               # 分析模块（镜头+话术+报告）
├── requirements.txt         # Python 依赖
├── build_windows.spec       # PyInstaller 打包配置
├── run.bat                  # Windows 快捷运行脚本
└── .github/workflows/
    └── build.yml            # GitHub Actions 自动构建
```
