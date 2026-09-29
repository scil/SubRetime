# SubRetime（旧版中文说明）

> 这是 2026-09-28 之前的中文 README，保留供参考，部分内容已过时
> （例如 `--threshold` 等旧参数、"未来工作"中已实现的条目）。
> 最新文档见 [README.md](README.md)、[TROUBLESHOOTING.md](TROUBLESHOOTING.md)、
> [LESSONS.md](LESSONS.md)。

将 **原字幕的文字** 与 **WhisperX 新字幕的时间轴** 结合，生成新的 `.srt` 字幕文件。

适合以下场景：

- 原字幕文字基本正确，但时间轴整体或逐句不准
- WhisperX 能生成较准确的语音时间，但其文字识别结果不想直接使用
- 希望最终结果：
  - **文字来自原字幕**
  - **时间来自 WhisperX**
  - 尽量保持原字幕内容不变

---

## 目录结构

建议项目目录：

```text
subtitle-alignment-with-Whisper/
│
├─ .venv/
├─ align_srt.py
├─ gui.py
├─ README.md
│
├─ original.srt
├─ whisperx.srt
└─ fixed.srt
```

---

# 1. 准备 Python

推荐：

```text
Python 3.11
```

检查：

```powershell
python --version
```

如果使用 `uv` 管理 Python：

```powershell
uv python install 3.11
uv python pin 3.11
```

查看已安装 Python：

```powershell
uv python list
```

升级 `uv` 本身：

```powershell
python -m pip install --upgrade uv
```

升级 `pip`：

```powershell
python -m pip install --upgrade pip
```

---

# 2. 创建虚拟环境

进入项目目录：

```powershell
cd E:\me\subtitle-alignment-with-Whisper
```

使用 `uv`：

```powershell
uv venv
```

或者：

```powershell
python -m venv .venv
```

激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

成功后命令行前面通常会出现：

```text
(.venv)
```

---

# 3. PowerShell 不允许激活虚拟环境

如果出现：

```text
running scripts is disabled on this system
```

运行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新：

```powershell
.\.venv\Scripts\Activate.ps1
```

---

# 4. 安装 FFmpeg

使用 winget：

```powershell
winget install Gyan.FFmpeg
```

安装后关闭并重新打开 PowerShell。

检查：

```powershell
ffmpeg -version
```

必须能正常输出版本信息。

---

# 5. 安装 WhisperX

使用 `uv`：

```powershell
uv pip install whisperx
```

或者：

```powershell
pip install whisperx
```

检查：

```powershell
whisperx --help
```

---

# 6. 安装本项目需要的 Python 库

```powershell
uv pip install srt rapidfuzz
```

或者：

```powershell
pip install srt rapidfuzz
```

其中：

- `srt`
  - 读取和生成 `.srt`
- `rapidfuzz`
  - 模糊匹配原字幕和 WhisperX 字幕文字

GUI 使用的是 Python 自带的：

```text
tkinter
```

通常不需要额外安装。

---

# 7. 检查 NVIDIA GPU

运行：

```powershell
nvidia-smi
```

然后：

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

正常 GPU 情况类似：

```text
2.x.x+cu128
12.8
True
NVIDIA GeForce RTX 5070 Ti
```

如果显示：

```text
False
CPU only
```

说明当前 Python 环境中的 PyTorch 没有正确使用 CUDA。

---

# 8. RTX 50 系列 / Blackwell 注意事项

RTX 50 系列显卡需要较新的 CUDA / PyTorch 支持。

不要只追求：

```text
越新的 PyTorch 越好
```

应该优先保证：

```text
WhisperX
PyTorch
TorchCodec
CUDA
```

之间版本兼容。

如果 `torch.cuda.is_available()` 是 `False`，检查：

```powershell
python -m pip show torch
```

如果 `torch.version.cuda` 为：

```text
None
```

通常说明安装的是 CPU 版 PyTorch。

CUDA 12.8 示例：

```powershell
uv pip uninstall torch torchvision torchaudio
```

然后：

```powershell
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

再次检查：

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

> 注意：
>
> 具体 PyTorch / TorchCodec 版本必须结合当前 WhisperX 依赖要求。
> 如果出现 TorchCodec 兼容性错误，不要盲目升级到最新版 PyTorch。

---

# 9. 先测试 WhisperX

假设视频：

```text
F:\Videos\movie.mp4
```

输出目录：

```text
F:\Videos\whisper-output
```

## NVIDIA GPU：基础版本

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --model small `
  --device cuda `
  --compute_type float16 `
  --output_dir "F:\Videos\whisper-output"
```

---

# 10. 指定语言

英文：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language en `
  --model small `
  --device cuda `
  --compute_type float16 `
  --output_dir "F:\Videos\whisper-output"
```

中文：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language zh `
  --model small `
  --device cuda `
  --compute_type float16 `
  --output_dir "F:\Videos\whisper-output"
```

日语：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language ja `
  --model small `
  --device cuda `
  --compute_type float16 `
  --output_dir "F:\Videos\whisper-output"
```

---

# 11. WhisperX 模型选择

## 快速测试

```powershell
--model small
```

## 更高精度

```powershell
--model medium
```

## 更高精度、显存需求更高

```powershell
--model large-v3
```

示例：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language en `
  --model large-v3 `
  --device cuda `
  --compute_type float16 `
  --output_dir "F:\Videos\whisper-output"
```

`whisperx  "F:\Dog Man (2025) [1080p] [WEBRip] [5.1] [YTS.MX]\Dog.Man.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"  --language en  --model large-v3  --device cuda  --compute_type float16  --output_dir "F:\Dog Man (2025) [1080p] [WEBRip] [5.1] [YTS.MX]\whisper-output"

---

# 12. 显存不足时

使用：

```powershell
--compute_type int8
```

例如：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language en `
  --model small `
  --device cuda `
  --compute_type int8 `
  --batch_size 4 `
  --output_dir "F:\Videos\whisper-output"
```

也可以降低：

```powershell
--batch_size 2
```

或者使用更小模型：

```powershell
--model small
```

---

# 13. CPU 运行 WhisperX

没有可用 CUDA 时：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language en `
  --model small `
  --device cpu `
  --compute_type int8 `
  --output_dir "F:\Videos\whisper-output"
```

CPU 会明显慢很多。

---

# 14. WhisperX 输出目录陷阱

错误：

```text
F:\Videos\movie.mp4\whisper-output
```

这里把 `.mp4` 文件错误地当成目录。

会出现：

```text
FileNotFoundError
[WinError 3]
```

正确：

```text
F:\Videos\whisper-output
```

例如：

```powershell
--output_dir "F:\Videos\whisper-output"
```

---

# 15. 原字幕和 WhisperX 字幕

准备两个字幕文件。

原字幕：

```text
original.srt
```

特点：

```text
文字正确
时间不准确
```

WhisperX 字幕：

```text
whisperx.srt
```

特点：

```text
文字可能略有不同
时间更准确
```

最终：

```text
fixed.srt
```

目标：

```text
original.srt 的文字
+
whisperx.srt 的时间
```

---

# 16. Running the alignment

```powershell
python align_srt.py original.srt whisperx.srt fixed.srt
```

- `whisperx.srt` may also be the WhisperX `.json`. When a `.json` with the
  same name sits next to the `.srt`, it is used automatically: it carries
  **per-word timestamps**, which are far more precise than segment times.
- A diagnostic report `fixed.report.csv` is written next to the output
  (status, matched words, original vs new start, WhisperX text, notes).
- `--quiet` prints only the summary.

Recommended, when the video is available and `whisperx` + a GPU work:

```powershell
python align_srt.py original.srt whisperx.srt fixed.srt --audio movie.mp4
```

`--audio` settles disputed cues by listening (see "Audio verification"
below). It adds about 20 s for a feature film on an RTX GPU.

There are no tuning parameters any more. The old `--threshold`,
`--lookahead` and `--max-span` belonged to the greedy cue matcher, which
was replaced (see LESSONS.md for why).

## Summary lines

```text
Words matched: 6004/6806 (88.2%)
Anchored:      1105  (timed from WhisperX words)
Verified:      22    (rejected anchor restored by audio check)   # --audio only
Rescued:       4     (found by local search near expected time)
Outliers:      82    (anchor rejected, interpolated)
Interpolated:  178   (no words recognized)
```

Interpolated cues are mostly interjections WhisperX ignores ("Whew.",
"Huh?", "Shh") and song lyrics. They keep the original timing plus the
local offset, so they stay usable.

## Checking quality

```powershell
python evaluate_timing.py original.srt fixed.srt --audio movie.mp4
```

Prints structure problems (overlaps, order, too-short cues, reading speed)
and, with `--audio`, how often the audio prefers the new start over the
original on every cue where they differ by more than 1 s.

---

# 23. GUI 运行

运行：

```powershell
python gui.py
```

界面包括：

```text
Original SRT
WhisperX SRT
Output SRT
```

---

## Original SRT

选择：

```text
原始字幕
```

作用：

```text
保留它的字幕文字
```

---

## WhisperX SRT

选择：

```text
WhisperX 生成的字幕
```

作用：

```text
主要使用它的时间信息
```

---

## Output SRT

指定：

```text
输出文件
```

例如：

```text
fixed.srt
```

---

# 24. GUI 找不到 align_srt.py

当前 GUI 如果写成：

```python
"align_srt.py"
```

那么它依赖：

```text
当前工作目录
```

更稳妥的做法是：

```python
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ALIGN_SCRIPT = SCRIPT_DIR / "align_srt.py"
```

调用：

```python
str(ALIGN_SCRIPT)
```

这样：

```text
无论从哪里启动 gui.py
```

都可以找到同目录的：

```text
align_srt.py
```

---

# 25. Windows Unicode / 中文字幕陷阱

如果字幕里包含：

```text
中文
日文
韩文
♪
♫
特殊 Unicode 字符
```

Windows 子进程可能使用：

```text
cp1252
```

从而出现：

```text
UnicodeEncodeError:
'charmap' codec can't encode character
```

典型位置：

```python
print(orig.content)
```

---

## align_srt.py 修复

在顶部加入：

```python
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
    )

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
    )
```

---

## gui.py 修复

推荐：

```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
```

还可以进一步：

```python
import os

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
```

然后：

```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    env=env,
)
```

---

# 26. `utf-8-sig` 读取字幕

读取 `.srt` 时推荐：

```python
with open(path, "r", encoding="utf-8-sig") as f:
    ...
```

原因：

```text
有些字幕文件开头有 UTF-8 BOM
```

使用：

```text
utf-8-sig
```

可以自动处理 BOM。

---

# 27. Triton 警告

可能看到：

```text
triton not found;
flop counting will not work for triton kernels
```

Windows 环境下通常不是致命错误。

如果 WhisperX 后面仍正常执行：

```text
可以忽略
```

不要因为这条 warning 就立即安装各种非官方 Triton 包。

---

# 28. TorchCodec 警告

可能看到：

```text
torchcodec is not installed correctly
```

或者：

```text
Could not load libtorchcodec
```

常见原因：

```text
1. FFmpeg DLL 不完整
2. TorchCodec 与 PyTorch 版本不兼容
3. Windows PATH 中找不到 FFmpeg shared libraries
```

先检查：

```powershell
ffmpeg -version
```

再检查：

```powershell
python -c "import torch; print(torch.__version__)"
```

以及：

```powershell
python -c "import torchcodec; print(torchcodec.__version__)"
```

注意：

```text
ffmpeg.exe 能运行
```

不一定意味着：

```text
TorchCodec 能加载 FFmpeg DLL
```

这是两个不同层面的问题。

---

# 29. Torch / TorchCodec 版本陷阱

例如：

```text
PyTorch 很新
TorchCodec 很旧
```

可能出现：

```text
The PyTorch version is not compatible
with this version of TorchCodec
```

不要直接：

```powershell
pip install --upgrade torch
```

因为：

```text
升级 PyTorch
```

可能反而破坏：

```text
WhisperX
TorchCodec
torchaudio
torchvision
```

之间的兼容关系。

正确做法：

```text
先确认 WhisperX 当前依赖
再选匹配版本
```

---

# 30. FFmpeg Shared DLL 陷阱

Windows 下某些 TorchCodec 版本需要：

```text
avcodec-*.dll
avformat-*.dll
avutil-*.dll
```

如果只安装了：

```text
ffmpeg.exe
```

但没有相关 shared DLL：

```text
TorchCodec 仍可能加载失败
```

这时应检查当前 FFmpeg build 是否为：

```text
shared build
```

---

# 31. 原字幕和 WhisperX 必须尽量同语言

最佳情况：

```text
Original: English
WhisperX: English
```

或者：

```text
Original: 中文
WhisperX: 中文
```

---

## 不适合直接模糊匹配

例如：

```text
Original: 中文字幕
WhisperX: 英文识别结果
```

这时：

```text
英文声音
↓
英文转录
```

无法直接和：

```text
中文字幕
```

做普通字符串匹配。

需要改用：

```text
时间邻近
+
句子顺序
+
语义匹配
```

甚至：

```text
翻译后的文本匹配
```

---

# 32. How the alignment works

1. **Words, not cues.** Both subtitles are split into normalized words
   (lowercase, no punctuation, `ok` = `okay`, hyphens split). Each original
   word remembers its cue.
2. **Global monotonic word alignment.** `difflib.SequenceMatcher` finds
   exact runs of words shared by both streams. Inside the gaps between
   runs, a small Needleman-Wunsch pass (a dynamic-programming sequence
   alignment) pairs similar words (`grampa`/`grandpa`) and 2:1 splits
   (`dog man`/`dogman`).
3. **Cue timing.** A cue starts at its first matched word and ends at its
   last. An edge word pinned seconds away from the rest of the cue is
   dropped: WhisperX sometimes mistimes the first or last word of a phrase.
4. **Outlier rejection.** The *local offset* is the median of
   (WhisperX start - original start) over neighbouring anchored cues. An
   anchor more than 1.5 s (strong: 4+ matched words) or 1 s (weak) from it
   is rejected.
5. **Interpolation.** Rejected and unmatched cues get the original time
   plus the median local offset of up to 3 anchored cues on each side.
6. **Audio verification (`--audio`).** For each rejected anchor, the cue
   text is force-aligned in a tight window at the WhisperX time and at the
   interpolated time; the window with clearly higher confidence wins.
   Only cues with 3+ words are judged: a one-word cue ("Huh?") fits almost
   any short sound, so its comparison is too weak to overrule the fallback.
7. **Local rescue.** Unplaced cues are searched for near their expected
   time, between the WhisperX words used by their neighbours. This finds
   repeated lines ("Papa?" "Papa." "Papa!") that global alignment paired
   with the wrong copy.
8. **Order check.** A placed cue that starts after both following cues (or
   before both previous ones) is reverted to interpolation.
9. **Finishing.** One forward pass: no overlaps (84 ms gap), reading time
   of about 17 characters per second, starting up to 0.5 s early when the
   next cue leaves no room.

## Why not match cue against cue?

Cue boundaries differ between the two files, and fuzzy scores for short
text against long text are misleading (`WRatio("whoa", "... whoa ...")`
is 90). A greedy cue matcher that accepts such a score consumes WhisperX
cues too fast and falls off the end of the file.

## Why the original timing still matters

WhisperX word times fail in characteristic ways: words smeared over 10+
seconds during music, whole segments seconds early. On Dog Man (2025), when
a WhisperX anchor disagreed with the ffsubsync timing by more than 3 s, the
audio sided with ffsubsync about three times as often. So the original
timing, synced first with ffsubsync, is the prior; WhisperX refines it.

---

# 37. 推荐人工复核

完成：

```text
fixed.srt
```

后，推荐用：

```text
Subtitle Edit
```

同时打开：

```text
video.mp4
fixed.srt
```

重点检查：

```text
MISS
低分 MATCH
长字幕
多人同时讲话
歌曲
音效
快速对白
```

---

# 38. 特殊字幕

以下内容可能影响匹配：

```text
[door opens]
(laughing)
♪ song lyrics ♪
APPLAUSE
MUSIC
```

如果 WhisperX 没有识别这些：

```text
很可能出现 MISS
```

这是正常情况。

---

# 39. 数字与专有名词

WhisperX 可能把：

```text
PostgreSQL
```

识别成：

```text
Postgres SQL
```

或者：

```text
2026
```

识别成：

```text
twenty twenty-six
```

RapidFuzz 可以容忍一定差异，但：

```text
差异过大
```

仍然可能 MISS。

---

# 40. Special cases

- Songs and credits: WhisperX often skips or misplaces lyrics; those cues
  are interpolated. Check them by hand.
- Different edits of the film (extra or missing scenes): ffsubsync fixes
  only one global shift or speed, so run it first and let this tool fix the
  rest; long stretches of outliers point to an edit difference.

---

# 42. WhisperX 输出文字明显错误

如果 WhisperX 文本质量太差：

```text
模糊匹配也会失败
```

优先改善 WhisperX：

```text
指定正确语言
使用更大模型
提高音频质量
```

例如：

```powershell
--language en
--model medium
```

---

# 43. 输出字幕编码

推荐：

```text
UTF-8
```

写入：

```python
with open(output, "w", encoding="utf-8") as f:
    ...
```

这样最适合：

```text
中文
英文
多语言
特殊符号
```

---

# 44. 推荐完整工作流

## 第一步

生成 WhisperX 字幕：

```powershell
whisperx `
  "F:\Videos\movie.mp4" `
  --language en `
  --model medium `
  --device cuda `
  --compute_type float16 `
  --output_dir "F:\Videos\whisper-output"
```

---

## 第二步

准备：

```text
original.srt
whisperx.srt
```

---

## 第三步

运行：

```powershell
python align_srt.py `
  original.srt `
  whisperx.srt `
  fixed.srt `
  --audio movie.mp4
```

---

## 第四步

查看：

```text
MATCH
MISS
```

---

## 第五步

用 Subtitle Edit：

```text
video.mp4
+
fixed.srt
```

人工检查。

---

# 45. Recommended workflow

1. `ffsubsync` the original subtitle to the video (global shift).
2. WhisperX with `--language en --model large-v3` (keep the `.json`).
3. `align_srt.py original.srt whisperx.srt fixed.srt --audio movie.mp4`.
4. `evaluate_timing.py original.srt fixed.srt --audio movie.mp4`.
5. Spot check `outlier`, `rescued` and long `interpolated` runs from the
   report in Subtitle Edit.

---

# 开发备注

## A. 不要修改原字幕文字

这个项目的设计原则：

```text
WhisperX 只负责提供时间
原字幕负责提供最终文字
```

不要默认使用：

```text
WhisperX 转录文本
```

覆盖原字幕。

---

## B. 相似度只是候选依据

RapidFuzz：

```text
不是语义模型
```

它主要比较：

```text
字符
词
字符串结构
```

因此：

```text
完全不同语言
```

不能直接匹配。

---

## C. 不能只用单条字幕做匹配

因为：

```text
原字幕一条
```

经常对应：

```text
WhisperX 两条甚至更多
```

所以需要：

```text
span matching
```

---

## D. 未来应考虑双向 span

当前主要解决：

```text
1 条 Original
→
N 条 WhisperX
```

未来还可以增加：

```text
N 条 Original
→
1 条 WhisperX
```

因为 WhisperX 也可能：

```text
合并多个原字幕句子
```

---

## E. 当前算法是贪心算法

现在采用：

```text
逐条向前找最佳匹配
```

优点：

```text
简单
快
容易调试
```

缺点：

```text
早期错误匹配
可能影响后续所有匹配
```

未来更稳的方法：

```text
Dynamic Programming
Sequence Alignment
DTW
Needleman-Wunsch 类算法
```

可以从全局寻找最优字幕序列对应。

---

## F. 时间本身也应该加入评分

目前核心评分主要来自：

```text
文本相似度
```

未来建议加入：

```text
原字幕旧时间
WhisperX 时间
```

例如：

```text
候选时间离原时间越近
加分
```

可以显著降低：

```text
重复台词
```

造成的错误匹配。

---

## G. 重复句子是危险点

例如：

```text
Yes.
Yes.
Yes.
```

RapidFuzz：

```text
全部接近 100%
```

单靠文字无法确定是哪一句。

必须结合：

```text
顺序
时间
上下文
```

---

## H. 很短的字幕不可靠

例如：

```text
No.
Yes.
What?
Okay.
```

文本太短。

建议未来：

```text
短句提高时间权重
降低纯文本权重
```

---

## I. 日志不要直接依赖系统编码

Windows 默认控制台编码可能是：

```text
cp1252
cp936
```

不要假设：

```text
stdout == UTF-8
```

程序应主动：

```python
sys.stdout.reconfigure(
    encoding="utf-8",
    errors="replace",
)
```

GUI 子进程也应明确：

```python
encoding="utf-8"
```

---

## J. GUI 不应该依赖当前工作目录

不要：

```python
"align_srt.py"
```

最好：

```python
Path(__file__).resolve().parent / "align_srt.py"
```

否则：

```text
双击
快捷方式
从其他目录运行
```

可能找不到脚本。

---

## K. GUI 长任务会卡住

当前使用：

```python
subprocess.run()
```

会阻塞 Tkinter 主线程。

字幕多时：

```text
GUI 看起来会“卡住”
```

但程序实际上可能仍在运行。

未来应该：

```text
threading.Thread
```

或者：

```text
subprocess.Popen
```

并实时读取 stdout。

---

## L. GUI 最好增加进度日志

未来可以添加：

```text
Text 控件
```

实时显示：

```text
MATCH
MISS
当前进度
```

而不是只在结束时弹框。

---

## M. 输出不要覆盖原字幕

GUI 默认应让用户：

```text
另存为 fixed.srt
```

不要直接覆盖：

```text
original.srt
```

除非明确确认。

---

## N. 建议增加 dry-run

未来可增加：

```text
--dry-run
```

只打印：

```text
匹配结果
```

但：

```text
不生成 fixed.srt
```

方便调参数。

---

## O. 建议生成诊断文件

未来可以输出：

```text
alignment-report.csv
```

包含：

```text
original index
WhisperX start
WhisperX end
score
status
original text
matched text
```

这样更容易分析：

```text
MISS
低分匹配
异常跳跃
```

---

## P. 应考虑时间边界保护

可能出现：

```text
上一条字幕结束时间
>
下一条字幕开始时间
```

未来可以增加：

```text
overlap correction
```

例如：

```text
前一条 end
最多到下一条 start - 20ms
```

---

## Q. WhisperX 本身不是“原字幕 forced alignment”

当前流程：

```text
视频
→
WhisperX 自己转录
→
新字幕
→
再和原字幕匹配
```

并不是：

```text
直接把原字幕文字送入 forced aligner
```

后者理论上会更精确。

未来可以进一步研究：

```text
WhisperX align()
```

直接对：

```text
已有 transcript
```

进行 phoneme alignment。

这样可以减少：

```text
Whisper 转录文字差异
```

带来的二次匹配问题。

---

## R. 不同语言需要不同方案

### 同语言

例如：

```text
English → English
```

当前 RapidFuzz 方法适合。

### 翻译字幕

例如：

```text
English audio
→
Chinese subtitle
```

应该考虑：

```text
语义向量
机器翻译
时间先验
序列对齐
```

不能简单依赖 RapidFuzz。

---

## S. 最终结果必须人工抽查

AI 自动字幕对齐不能保证：

```text
100% 正确
```

尤其：

```text
多人同时讲话
歌曲
背景电视声音
快速对白
低音量
强噪声
字幕删减
字幕意译
```

最终建议：

```text
Subtitle Edit
+
波形
+
视频
```

做抽查。

---

# 总结

项目当前推荐工作流：

```text
video.mp4
   ↓
WhisperX
   ↓
whisperx.srt
   ↓
align_srt.py
   ↑
original.srt
   ↓
fixed.srt
   ↓
Subtitle Edit 人工复核
```

核心原则：

```text
原字幕保留文字
WhisperX 提供时间
RapidFuzz 负责寻找对应关系
不确定时保留原时间
不要强行错误匹配
```
