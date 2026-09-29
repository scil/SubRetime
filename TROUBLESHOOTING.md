# Troubleshooting

Problems met while setting up WhisperX and SubRetime on Windows 11 with an
NVIDIA RTX 50-series GPU. Check here before changing package versions.

## PowerShell refuses to activate the virtual environment

```text
running scripts is disabled on this system
```

Allow local scripts for your user, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## `torch.cuda.is_available()` is `False`

```powershell
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

- `torch.version.cuda` is `None` → a CPU-only PyTorch is installed. This
  happens when installing WhisperX pulls torch from PyPI. Reinstall the
  **same version** from the CUDA index, e.g. for torch 2.8.0 and CUDA 12.8:

  ```powershell
  uv pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
  ```

- Check that `nvidia-smi` works; if it does not, the driver is the problem,
  not Python.

## RTX 50-series (Blackwell) GPUs

These GPUs need a recent CUDA build of PyTorch (cu128 works). Do **not**
simply upgrade to the newest PyTorch: WhisperX, PyTorch, torchaudio and
TorchCodec must be versions that work together. Check which torch version
the installed WhisperX expects (`uv pip show whisperx`) and install the CUDA
build of that version.

## TorchCodec warnings

```text
torchcodec is not installed correctly
Could not load libtorchcodec
The PyTorch version is not compatible with this version of TorchCodec
```

Usual causes:

1. TorchCodec and PyTorch versions do not match. Fix the pair; do not run
   `pip install --upgrade torch` on its own, which can break WhisperX.
2. The FFmpeg **shared libraries** (`avcodec-*.dll`, `avformat-*.dll`,
   `avutil-*.dll`) are missing. `ffmpeg.exe` working does not mean these
   DLLs exist or are on `PATH`; some TorchCodec versions need a *shared*
   FFmpeg build.

If transcription still completes, the warning can usually be ignored.

## `triton not found`

```text
triton not found; flop counting will not work for triton kernels
```

Harmless on Windows. Do not install unofficial Triton packages because of it.

## Out of GPU memory

Use smaller numbers, a smaller model, or all of these:

```powershell
whisperx movie.mp4 --language en --model large-v3 --device cuda --compute_type int8 --batch_size 4 --output_dir out
```

`--batch_size 2`, `--model medium` or `--model small` reduce memory further.
CPU works too (`--device cpu --compute_type int8`) but is much slower.

## WhisperX `FileNotFoundError` / `[WinError 3]`

`--output_dir` must be a folder, not the video path:

```text
wrong:  --output_dir "F:\Videos\movie.mp4\whisper-output"
right:  --output_dir "F:\Videos\whisper-output"
```

## `UnicodeEncodeError: 'charmap' codec can't encode character`

Windows consoles and subprocesses may use a legacy code page (cp1252,
cp936), so printing `♪` or CJK text fails. `align_srt.py` reconfigures
stdout/stderr to UTF-8 and `gui.py` runs it with `PYTHONIOENCODING=utf-8`.
If you write your own scripts, do the same:

```python
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

## Subtitle files with a BOM

Some `.srt` files start with a UTF-8 byte-order mark. SubRetime reads them
with `encoding="utf-8-sig"`, which removes it, and writes plain UTF-8.

## GUI cannot find `align_srt.py`

`gui.py` locates the script relative to its own file
(`Path(__file__).resolve().parent`), so it works from any working
directory. If you copy `gui.py` elsewhere, copy `align_srt.py` with it.

## The GUI button says "Running…" for a long time

With **Audio check** ticked, a feature film takes about 1–2 minutes
(loading the audio and the alignment model). The window stays usable
meanwhile; a dialog appears when the run finishes. Without the audio
check it takes about a second.

## The original and the audio are in different languages

SubRetime matches words, so the subtitle must be in the language that is
spoken. A Chinese subtitle for English audio cannot be matched this way;
that would need meaning-based matching (e.g. sentence embeddings) instead
of word matching.
