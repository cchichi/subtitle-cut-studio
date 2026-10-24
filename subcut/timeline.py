# -*- coding: utf-8 -*-
"""决策 → 渲染计划：窗口合并、慢放拆分、时间映射、ASS 字幕/花字、音效床、标记贴图。"""
import json
import math
import re
import wave
from pathlib import Path

R = 3
MIN_WIN = 0.5

STYLE_ASS = {"gold": "&H0000D7FF", "red": "&H000052FF", "blue": "&HFFC0A028"}


def build_plan(dec: dict) -> dict:
    S = {"缓冲": 0.35, "拼接间隔": 1.2, "字幕": True, "音效": True,
         "花字": True, "慢放": True, "人名前缀": False}
    S.update(dec.get("settings") or {})
    lines = sorted(dec.get("lines") or [], key=lambda l: (l["start"], l.get("id", 0)))
    video = _find_video(dec)

    # ---- 1. 保留窗口（相邻拼接） ----
    B, G = float(S["缓冲"]), float(S["拼接间隔"])
    wins = []
    for l in lines:
        if l["action"] == "skip":
            continue
        wins.append([max(0.0, l["start"] - B), l["end"] + B])
    wins.sort(key=lambda w: w[0])
    merged = []
    for a, b in wins:
        if merged and a - merged[-1][1] <= G:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    merged = [[a, b] for a, b in merged if b - a >= MIN_WIN]
    if not merged:
        raise SystemExit("没有任何保留行——请至少把一行设为保留")

    # ---- 2. 慢放拆分 ----
    slow_spans = [] if not S.get("慢放", True) else [
        [l["start"] - 0.2, l["end"] + 0.2] for l in lines if l["action"] == "slow"]
    subs = []
    for a, b in merged:
        cuts = {a, b}
        for s0, s1 in slow_spans:
            if s1 > a and s0 < b:
                cuts.add(max(a, s0)); cuts.add(min(b, s1))
        pts = sorted(cuts)
        parts = []
        for s, e in zip(pts, pts[1:]):
            mid = (s + e) / 2
            slow = any(s0 <= mid <= s1 for s0, s1 in slow_spans) and e - s >= 1.0
            if parts and parts[-1][2] == (0.5 if slow else 1.0):
                parts[-1][1] = e
            else:
                parts.append([s, e, 0.5 if slow else 1.0])
        i = 0
        while i < len(parts):
            if parts[i][1] - parts[i][0] < 0.25 and len(parts) > 1:
                if i + 1 < len(parts):
                    parts[i + 1][0] = parts[i][0]
                else:
                    parts[i - 1][1] = parts[i][1]
                parts.pop(i)
            else:
                i += 1
        subs += [(s, e, sp) for s, e, sp in parts if e - s > 0.15]

    # ---- 3. 时间轴与映射 ----
    seg_tl, tl = [], 0.0
    for s, e, sp in subs:
        dur = (e - s) / sp
        seg_tl.append((round(tl, R), round(tl + dur, R), s, sp))
        tl += dur
    TOTAL = round(tl, R)

    def src_to_tl(src_t: float) -> float:
        for idx, (tl0, tl1, s0, sp) in enumerate(seg_tl):
            nxt = seg_tl[idx + 1][2] if idx + 1 < len(seg_tl) else float("inf")
            if s0 - 1e-6 <= src_t < nxt:
                return round(tl0 + (src_t - s0) / sp, R)
        return seg_tl[-1][1]

    # ---- 4. 字幕 cues（重叠收敛 + 短句并入） ----
    raw = []
    for l in lines:
        if l["action"] == "skip" or not S.get("字幕", True) or l.get("subShow") is False:
            continue
        t0 = src_to_tl(l["start"])
        t1 = min(max(src_to_tl(l["end"]), t0 + 0.8), TOTAL)
        text = re.sub(r"\s+", "", str(l["text"]))
        if not text:
            continue
        if S.get("人名前缀") and l.get("who") and l["who"] != "?":
            text = f"{l['who']}：{text}"
        raw.append({"t0": t0, "t1": t1, "text": text})
    raw.sort(key=lambda c: c["t0"])
    i = 0
    while i < len(raw) - 1:
        cur, nxt = raw[i], raw[i + 1]
        if cur["t1"] > nxt["t0"] - 0.05:
            cur["t1"] = max(cur["t0"] + 0.3, nxt["t0"] - 0.05)
        if cur["t1"] - cur["t0"] < 0.5:
            nxt["t0"] = cur["t0"]
            nxt["text"] = (cur["text"] + "，" + nxt["text"])[:36]
            raw.pop(i)
        else:
            i += 1
    cues = [c for c in raw if c["t1"] - c["t0"] >= 0.4]

    # ---- 5. 花字（重叠时保长弃短） ----
    hz_raw = []
    for l in lines:
        if not S.get("花字", True):
            break
        if l["action"] not in ("highlight", "slow") or not l.get("huazi"):
            continue
        t0 = src_to_tl(l["start"])
        t1 = min(max(src_to_tl(l["end"]), t0 + 1.0), TOTAL - 0.2)
        hz_raw.append({"t0": t0, "t1": t1, "huazi": l["huazi"],
                       "style": l.get("style") or "gold"})
    hz_raw.sort(key=lambda c: c["t0"])
    hz_final = []
    for c in hz_raw:
        if hz_final:
            last = hz_final[-1]
            if c["t0"] <= last["t1"] - 0.01:
                if (c["t1"] - c["t0"]) > (last["t1"] - last["t0"]):
                    hz_final[-1] = c
                continue
            allowed = c["t0"] - 0.15
            if allowed - last["t0"] >= 0.5:
                last["t1"] = min(last["t1"], allowed)
        hz_final.append(c)
    hzs = [c for c in hz_final if c["t1"] - c["t0"] >= 0.5]

    # ---- 6. 标记贴图（人名条 + 归属环） ----
    overlays = _gen_marker_pngs(dec, src_to_tl, TOTAL)

    # ---- 7. 音效床 ----
    sfx_wav = _gen_sfx_bed(lines, src_to_tl, TOTAL) if S.get("音效", True) else None

    return {"video": str(video), "title": dec.get("title", ""),
            "total": TOTAL, "segments": subs, "seg_tl": seg_tl,
            "cues": cues, "huazi": hzs, "overlays": overlays,
            "sfx_wav": sfx_wav, "settings": S}


def _find_video(dec):
    for key in ("video_path", "video"):
        v = dec.get(key)
        if v and Path(v).suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v", ".avi"):
            p = Path(v)
            if p.is_file():
                return p.resolve()
    for p in sorted(Path(".").glob("*.mp4")) + sorted(Path(".").glob("*.mov")):
        if p.name not in ("预览视频.mp4", "成片.mp4"):
            return p.resolve()
    for p in sorted(Path("..").glob("*.mp4")) + sorted(Path("..").glob("*.mov")):
        if p.name not in ("预览视频.mp4", "成片.mp4"):
            return p.resolve()
    raise SystemExit("找不到源视频：把视频和决策文件放同一目录，或在决策里加 \"video_path\"")


def _gen_marker_pngs(dec, src_to_tl, total):
    from PIL import Image, ImageDraw, ImageFont
    out_dir = Path("out/markers")
    out_dir.mkdir(parents=True, exist_ok=True)
    overlays = []
    try:
        font = ImageFont.truetype("C:/WINDOWS/Fonts/msyhbd.ttc", 30 * 2)
    except OSError:
        font = ImageFont.load_default()

    for i, p in enumerate(dec.get("players") or [], 1):
        if p.get("tagX") is None:
            continue
        rgb = tuple(int(p["颜色"].lstrip("#")[k:k + 2], 16) for k in (0, 2, 4))
        text = f"{i} {p['名字']}"
        tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        l, t, r, b = tmp.textbbox((0, 0), text, font=font)
        W, H = (r - l) + 28 * 2, (b - t) + 16 * 2
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=H // 2,
                            fill=(20, 20, 28, 175), outline=rgb + (255,), width=6)
        d.text((28 - l, 16 - t), text, font=font, fill=(255, 255, 255, 255))
        img = img.resize((W // 2, H // 2), Image.LANCZOS)
        path = out_dir / f"tag_{i}_{p['名字']}.png"
        img.save(path)
        overlays.append({"path": str(path), "x": int(p["tagX"] - img.width / 2),
                         "y": int(p["tagY"] - img.height / 2),
                         "t0": 0.0, "t1": total})

    for m in dec.get("markers") or []:
        if m.get("kind") != "ring":
            continue
        rgb = tuple(int(str(m["颜色"]).lstrip("#")[k:k + 2], 16) for k in (0, 2, 4))
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([2, 2, 62, 62], outline=rgb + (255,), width=5)
        path = out_dir / f"ring_{m['名字']}.png"
        img.save(path)
        t0 = src_to_tl(float(m.get("出现", 0)))
        overlays.append({"path": str(path), "x": int(m["x"] - 32), "y": int(m["y"] - 32),
                         "t0": min(t0, total - 0.5), "t1": total})
    return overlays


def _gen_sfx_bed(lines, src_to_tl, total):
    events = []
    for l in lines:
        sfx = l.get("sfx") or ""
        if not sfx and l["action"] == "highlight":
            sfx = "ding" if l.get("event") == "安全" else \
                  ("dun" if l.get("event") == "中毒" else "")
        if sfx:
            events.append((min(src_to_tl(l["start"]), total - 1.0), sfx))
    if not events:
        return None
    FS = 48000
    bed = [0.0] * int(total * FS)
    for t, kind in events:
        i0 = int(max(0.0, t) * FS)
        dur = 0.45 if kind == "ding" else 0.75
        for i in range(int(dur * FS)):
            t2 = i / FS
            if kind == "ding":
                v = (0.5 * math.sin(2 * math.pi * 1318.5 * t2)
                     + 0.35 * math.sin(2 * math.pi * 1760 * t2)) * math.exp(-7 * t2)
            else:
                v = (0.6 * math.sin(2 * math.pi * 98 * t2)
                     + 0.35 * math.sin(2 * math.pi * 147 * t2)) * math.exp(-3.5 * t2)
            j = i0 + i
            if j < len(bed):
                bed[j] = max(bed[j], 0.55 * v)
    if not any(abs(v) > 1e-4 for v in bed[::997]):
        return None
    frames = bytearray()
    for v in bed:
        b = int(max(-1, min(1, v)) * 32767).to_bytes(2, "little", signed=True)
        frames += b + b
    wav = Path("out/sfx_events.wav").resolve()
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(bytes(frames))
    print(f"  音效床：{len(events)} 个提示音")
    return str(wav)


def build_ass(plan: dict, out_path: Path) -> str:
    """字幕 + 花字（ASS，花字带弹入动画）。返回 ass 文件路径。"""
    def ts(t):
        h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def esc(t):
        return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")

    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        "Style: Sub,微软雅黑,58,&H00FFFFFF,&H00FFFFFF,&H00202020,&H90000020,"
        "-1,0,0,0,100,100,0,0,1,2.4,1.2,2,60,60,44,1\n"
        "Style: HZg,微软雅黑,84,&H0000D7FF,&H0000D7FF,&H00202020,&H90000020,"
        "-1,0,0,0,100,100,0,-3,1,3.6,1.6,8,40,40,40,1\n"
        "Style: HZr,微软雅黑,84,&H000052FF,&H000052FF,&H00202020,&H90000020,"
        "-1,0,0,0,100,100,0,3,1,3.6,1.6,8,40,40,40,1\n"
        "Style: HZb,微软雅黑,84,&HFFC0A028,&HFFC0A028,&H00202020,&H90000020,"
        "-1,0,0,0,100,100,0,-2,1,3.6,1.6,8,40,40,40,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n")
    events = []
    for c in plan["cues"]:
        events.append(f"Dialogue: 0,{ts(c['t0'])},{ts(c['t1'])},Sub,,0,0,0,,"
                      f"{{\\fad(120,100)}}{esc(c['text'])}")
    for h in plan["huazi"]:
        style = "HZ" + (h["style"][:1] if h["style"][:1] in "grb" else "g")
        events.append(
            f"Dialogue: 1,{ts(h['t0'])},{ts(h['t1'])},{style},,0,0,0,,"
            "{{\\fad(100,140)\\fscx70\\fscy70"
            "\\t(0,150,\\fscx108\\fscy108)\\t(150,290,\\fscx100\\fscy100)}}"
            + esc(h["huazi"]))
    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return str(out_path)
