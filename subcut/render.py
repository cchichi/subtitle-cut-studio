# -*- coding: utf-8 -*-
"""自带 ffmpeg 渲染器：分窗切片 → 拼接 → ASS 字幕/花字 + 标记叠加 + 音效混音 → 质检。"""
import json
import subprocess
from pathlib import Path

from . import timeline as tl_mod


def run(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise SystemExit("ffmpeg 失败:\n" + (r.stderr or "")[-1500:])
    return r


def probe(video: Path):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height:format=duration",
             "-of", "json", str(video)])
    info = json.loads(r.stdout)
    has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
    size = next(((s["width"], s["height"]) for s in info["streams"]
                 if s.get("codec_type") == "video"), (1920, 1080))
    return has_audio, size, float(info["format"]["duration"])


def _atempo(sp: float) -> str:
    parts, rem = [], sp
    while rem > 2.0:
        parts.append("atempo=2.0"); rem /= 2.0
    while rem < 0.5:
        parts.append("atempo=0.5"); rem /= 0.5
    parts.append(f"atempo={rem:.6f}")
    return ",".join(parts)


def render_all(plan: dict, out_mp4: Path):
    video = Path(plan["video"])
    has_audio, (W, H), src_dur = probe(video)
    print(f"源视频 {W}x{H} 时长 {src_dur:.1f}s，预计成片 {plan['total']:.1f}s")

    tmp = Path("out/render")
    tmp.mkdir(parents=True, exist_ok=True)

    # ---- 1) 逐窗切片（含慢放） ----
    print("[1/3] 切片…")
    clips = []
    for i, (s, e, sp) in enumerate(plan["segments"]):
        cf = tmp / f"clip{i:03d}.mp4"
        vf = f"fps=30,setsar=1,format=yuv420p"
        if abs(sp - 1.0) > 1e-6:
            vf += f",setpts=PTS/{sp:.6f}"
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", str(video),
               "-filter:v", vf]
        if has_audio:
            af = "aresample=48000,aformat=channel_layouts=stereo"
            if abs(sp - 1.0) > 1e-6:
                af += "," + _atempo(sp)
            cmd += ["-filter:a", af, "-c:a", "aac", "-ar", "48000"]
        else:
            cmd += ["-an"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-video_track_timescale", "15360", str(cf)]
        run(cmd)
        clips.append(cf)

    # ---- 2) 拼接 ----
    print("[2/3] 拼接…")
    lst = tmp / "concat.txt"
    lst.write_text("\n".join(f"file '{c.resolve().as_posix()}'" for c in clips),
                   encoding="utf-8")
    base = tmp / "base.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(base)])

    # ---- 3) 字幕/花字(ass) + 标记叠加 + 音效混音 ----
    print("[3/3] 合成字幕/花字/标记/音效…")
    ass_path = tl_mod.build_ass(plan, tmp / "subs.ass")
    ass_arg = "filename='" + ass_path.replace("\\", "/").replace(":", "\\:") + "'"
    inputs = ["-i", str(base)]
    for ov in plan["overlays"]:
        inputs += ["-loop", "1", "-t", f"{plan['total']:.3f}",
                   "-i", ov["path"]]
    if plan["sfx_wav"]:
        inputs += ["-i", plan["sfx_wav"]]

    fc = [f"[0:v]ass={ass_arg}[v0]"]
    cur = "v0"
    for i, ov in enumerate(plan["overlays"], 1):
        fc.append(f"[{i}:v]format=rgba[o{i}]")
        nxt = f"v{i}"
        fc.append(f"[{cur}][o{i}]overlay={ov['x']}:{ov['y']}:"
                  f"eof_action=pass:shortest=0:"
                  f"enable='between(t,{ov['t0']:.3f},{ov['t1']:.3f})'[{nxt}]")
        cur = nxt
    if plan["sfx_wav"]:
        idx = len(plan["overlays"]) + 1
        fc.append(f"[0:a][{idx}:a]amix=inputs=2:duration=first:normalize=0[aout]")
        amap = ["-map", f"[{cur}]", "-map", "[aout]", "-c:a", "aac", "-ar", "48000"]
    else:
        amap = ["-map", f"[{cur}]", "-map", "0:a?", "-c:a", "copy"]

    cmd = (["ffmpeg", "-y", "-v", "error"] + inputs +
           ["-filter_complex", ";".join(fc)] + amap +
           ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-movflags", "+faststart", str(out_mp4)])
    run(cmd, timeout=3600)

    # ---- 4) 质检 ----
    ok_audio, _, out_dur = probe(out_mp4)
    drift = abs(out_dur - plan["total"])
    report = {"expected": plan["total"], "actual": round(out_dur, 2),
              "drift": round(drift, 2), "has_audio": ok_audio,
              "size_mb": round(out_mp4.stat().st_size / 1048576, 1)}
    Path("out/成片质检.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    # 逐片编码存在帧级取整累积，容差随片段数放宽
    tolerance = max(1.5, plan["total"] * 0.02)
    status = "pass" if (drift <= tolerance and ok_audio) else "fail"
    print(f"成片 {out_mp4} · {report['size_mb']}MB · 时长 {out_dur:.1f}s "
          f"(预期 {plan['total']:.1f}s) · QC: {status}")
    if status != "pass":
        raise SystemExit("质检未通过，详见 out/成片质检.json")
    return report
