import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("SubRetime")
root.resizable(False, False)

SCRIPT_DIR = Path(__file__).resolve().parent
ALIGN_SCRIPT = SCRIPT_DIR / "align_srt.py"

vars = [tk.StringVar() for _ in range(3)]
labels = ["Original SRT", "WhisperX SRT", "Output SRT"]

def pick(i):
    if i < 2:
        p = filedialog.askopenfilename(filetypes=[
            ("Subtitles / WhisperX JSON", "*.srt *.json"), ("All files", "*.*")])
    else:
        p = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=[("SRT files", "*.srt")])
    if p:
        vars[i].set(p)

for i, label in enumerate(labels):
    tk.Label(root, text=label).grid(row=i, column=0, padx=8, pady=5, sticky="e")
    tk.Entry(root, textvariable=vars[i], width=55).grid(row=i, column=1, padx=4)
    tk.Button(root, text="Browse", command=lambda i=i: pick(i)).grid(row=i, column=2, padx=8)

file_help = [
    "保留这个字幕文件的文字，只重新调整时间。",
    "WhisperX 的 .srt 或 .json；同名 .json 存在时自动使用逐词时间。",
    "生成的新字幕文件：原字幕文字 + WhisperX 时间（另附 .report.csv）。",
]

for i, text in enumerate(file_help):
    tk.Label(root, text=text, fg="gray", anchor="w").grid(
        row=i, column=3, padx=(2, 10), sticky="w"
    )

audio_on = tk.BooleanVar(value=False)
video_path = tk.StringVar()

def pick_video():
    p = filedialog.askopenfilename(filetypes=[
        ("Video / audio", "*.mp4 *.mkv *.avi *.mov *.m4a *.mp3 *.wav"),
        ("All files", "*.*")])
    if p:
        video_path.set(p)
        audio_on.set(True)
        toggle_audio()

def toggle_audio():
    state = "normal" if audio_on.get() else "disabled"
    video_entry.configure(state=state)
    video_button.configure(state=state)

tk.Checkbutton(root, text="Audio check", variable=audio_on, command=toggle_audio).grid(
    row=3, column=0, padx=8, pady=5, sticky="e")
video_entry = tk.Entry(root, textvariable=video_path, width=55)
video_entry.grid(row=3, column=1, padx=4)
video_button = tk.Button(root, text="Browse", command=pick_video)
video_button.grid(row=3, column=2, padx=8)
tk.Label(root, text="可选：用视频的音频裁决有争议的句子（--audio，需要 GPU，一部电影约 1–2 分钟）。",
         fg="gray", anchor="w").grid(row=3, column=3, padx=(2, 10), sticky="w")
toggle_audio()

tk.Label(root, text="Command").grid(row=4, column=0, padx=8, pady=(8, 2), sticky="ne")

command_box = tk.Text(root, width=92, height=4, wrap="word")
command_box.grid(row=4, column=1, columnspan=3, padx=(4, 10), pady=(8, 2), sticky="w")
command_box.configure(state="disabled")

def quote_arg(arg):
    arg = str(arg)
    if not arg:
        return '""'
    if any(ch.isspace() for ch in arg) or any(ch in arg for ch in '()[]&'):
        return '"' + arg.replace('"', '\\"') + '"'
    return arg

def format_command(cmd):
    return " ".join(quote_arg(arg) for arg in cmd)

def show_command(command):
    command_box.configure(state="normal")
    command_box.delete("1.0", tk.END)
    command_box.insert("1.0", command)
    command_box.configure(state="disabled")

def finish(command_text, result, error):
    """Runs on the Tk thread once the subprocess is done."""
    run_button.configure(state="normal", text="Align subtitles")
    if error is not None:
        messagebox.showerror("Error", "Command:\n\n" + command_text + "\n\n" + str(error))
    elif result.returncode == 0:
        messagebox.showinfo(
            "Done",
            "Command:\n\n" + command_text + "\n\n" +
            (result.stdout[-1500:] or "Finished.")
        )
    else:
        messagebox.showerror(
            "Error",
            "Command:\n\n" + command_text + "\n\n" + result.stderr[-2000:]
        )

def run():
    if not all(v.get() for v in vars):
        messagebox.showerror("Error", "Please select all three files.")
        return
    if audio_on.get() and not video_path.get():
        messagebox.showerror("Error", "Audio check is on: please select the video file.")
        return

    cmd = [
        sys.executable,
        str(ALIGN_SCRIPT),
        vars[0].get(),
        vars[1].get(),
        vars[2].get(),
        "--quiet",
    ]
    if audio_on.get():
        cmd += ["--audio", video_path.get()]

    # 显示实际运行的命令
    command_text = format_command(cmd)
    show_command(command_text)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    done = queue.Queue()

    def work():
        # No Tk calls here: Tk is not thread-safe. Hand the result back
        # through the queue; the Tk thread polls it in check().
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            done.put((result, None))
        except Exception as e:
            done.put((None, e))

    def check():
        try:
            result, error = done.get_nowait()
        except queue.Empty:
            root.after(200, check)
            return
        finish(command_text, result, error)

    run_button.configure(state="disabled", text="Running…")
    threading.Thread(target=work, daemon=True).start()
    root.after(200, check)

run_button = tk.Button(root, text="Align subtitles", command=run, width=20)
run_button.grid(row=5, column=0, columnspan=4, pady=12)

root.mainloop()
