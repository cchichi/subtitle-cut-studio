# -*- coding: utf-8 -*-
"""确定性分析：响度剖面、参考帧网格、预览视频、台词决策数据预填。"""
import base64
import collections
import json
import math
import re
import subprocess
from pathlib import Path

PALETTE = ["#40C4FF", "#69F0AE", "#FFD740", "#FF4081", "#B388FF", "#FF7043",
           "#00BCD4", "#8BC34A", "#FF9800", "#E91E63", "#7C4DFF", "#795548"]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def probe_duration(video: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)])
    return float(r.stdout.strip())


def loudness_profile(video: Path) -> list:
    """逐秒 RMS(dB) 剖面 → [[sec, db], ...]"""
    txt = Path("out/loudness.txt")
    run(["ffmpeg", "-v", "error", "-i", str(video),
         "-af", "astats=metadata=1:reset=1,ametadata=print:"
                "key=lavfi.astats.Overall.RMS_level:file=" + str(txt).replace("\\", "/"),
         "-f", "null", "-"], timeout=1800)
    bins = collections.defaultdict(list)
    cur = None
    for line in txt.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            cur = float(m.group(1))
            continue
        m = re.search(r"RMS_level=(-?[0-9.]+|-inf)", line)
        if m is not None and cur is not None:
            v = m.group(1)
            bins[int(cur)].append(-99.0 if v == "-inf" else float(v))
    prof = {s: 20 * math.log10(sum(10 ** (d / 20) for d in v) / len(v))
            for s, v in bins.items()}
    return sorted([[s, round(db, 1)] for s, db in prof.items()])


def reference_grid(video: Path, at_ratio=0.25) -> str:
    """取一帧加坐标网格 → base64（剪辑台上放置人名条/标记用）。"""
    dur = probe_duration(video)
    t = max(0.5, dur * at_ratio)
    frame = Path("out/ref_frame.png")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
         "-frames:v", "1", str(frame)])
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(frame).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("C:/WINDOWS/Fonts/msyh.ttc", max(14, W // 90))
    except OSError:
        font = None
    step = W // 12
    for gx in range(0, W + 1, step):
        d.line([(gx, 0), (gx, H)], fill=(255, 255, 0), width=1)
        if font:
            d.text((gx + 3, 3), str(gx), fill=(255, 255, 0), font=font)
    for gy in range(0, H + 1, step):
        d.line([(0, gy), (W, gy)], fill=(255, 255, 0), width=1)
        if font:
            d.text((3, gy + 3), str(gy), fill=(255, 255, 0), font=font)
    tmp = Path("out/ref_grid.jpg")
    im.save(tmp, quality=88)
    return base64.b64encode(tmp.read_bytes()).decode()


def make_proxy(video: Path, out_mp4: Path):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-vf", "scale=854:480", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "27", "-c:a", "aac", "-b:a", "96k",
         "-movflags", "+faststart", str(out_mp4)], timeout=1800)


def build_lines(tr_json: Path, loud: list, prefill="peaks", title="") -> dict:
    tr = json.loads(tr_json.read_text(encoding="utf-8"))
    peaks = [s for s, db in loud if db > -16]
    dur = loud[-1][0] + 1 if loud else 655
    lines = []
    for i, seg in enumerate(tr["segments"], 1):
        text = re.sub(r"\s+", "", seg["text"])
        mid = (seg["start"] + seg["end"]) / 2
        near_peak = any(abs(p - mid) < 2.5 for p in peaks)
        if prefill == "all":
            action = "keep"
        elif prefill == "none":
            action = "skip"
        else:
            action = "keep" if near_peak else "skip"
        event = "高潮" if near_peak else "对话"
        if seg["start"] < 20:
            event = "规则"
        elif seg["end"] > dur - 15:
            event = "结尾"
        lines.append({"id": i, "no": i, "start": round(seg["start"], 2),
                      "end": round(seg["end"], 2), "who": "?", "text": text,
                      "event": event, "action": action, "huazi": "",
                      "sfx": "", "subShow": True, "style": "gold"})
    return {
        "version": 1, "title": title or "我的视频",
        "video": str(Path.cwd()),
        "settings": {"缓冲": 0.35, "拼接间隔": 1.2, "字幕": True, "音效": True,
                     "花字": True, "慢放": True, "人名前缀": False},
        "players": [], "markers": [], "lines": lines,
    }
