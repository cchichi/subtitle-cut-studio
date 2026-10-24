# -*- coding: utf-8 -*-
"""可选：把决策同步为剪映可编辑草稿（需 pyJianYingDraft）。"""
import json
from pathlib import Path

SEC = 1_000_000
DRAFT_ROOT = (Path.home() / "AppData/Local/JianyingPro/User Data/Projects/"
              "com.lveditor.draft")


def _rgb(hexcolor):
    h = str(hexcolor).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def sync(dec: dict, plan: dict, draft_name: str = None):
    from pyJianYingDraft import (
        DraftFolder, TrackSpec, TrackType, VideoSegment, TextSegment, Timerange,
        TextStyle, TextBorder, TextShadow, ClipSettings, TransitionType, TextIntro)

    name = draft_name or (dec.get("title") or "字幕剪辑台") + "_草稿"
    folder = DraftFolder(str(DRAFT_ROOT))
    script = None
    used = name
    for cand in (name, name + "B", name + "C", name + "D"):
        try:
            script = folder.create_draft(cand, 1920, 1080, 30, allow_replace=True)
            used = cand
            break
        except PermissionError:
            print(f"草稿 {cand} 被剪映占用，换名重试")

    main = script.append_track(TrackSpec(TrackType.video, "主视频"))
    prev = None
    for i, (s, e, sp) in enumerate(plan["segments"]):
        src_us = round((e - s) * SEC)
        tgt_us = round(src_us / sp)
        seg = VideoSegment(plan["video"],
                           Timerange(round(plan["seg_tl"][i][0] * SEC), tgt_us),
                           source_timerange=Timerange(round(s * SEC), src_us),
                           speed=sp)
        if i == 0:
            seg.add_fade(0.4, 0)
        if i == len(plan["segments"]) - 1:
            seg.add_fade(0, 0.6)
        if prev is not None and i % 6 == 0:
            prev.add_transition(TransitionType.闪黑, duration=round(0.3 * SEC))
        script.add_segment(seg, main)
        prev = seg

    sub_t = script.append_track(TrackSpec(TrackType.text, "字幕"))
    for c in plan["cues"]:
        seg = TextSegment(
            c["text"].replace("\n", ""),
            Timerange(round(c["t0"] * SEC), round((c["t1"] - c["t0"]) * SEC)),
            style=TextStyle(size=5.2, color=(1, 1, 1)),
            clip_settings=ClipSettings(transform_y=-0.82),
            shadow=TextShadow(alpha=0.7, distance=4, diffuse=8))
        script.add_segment(seg, sub_t)

    hz_t = script.append_track(TrackSpec(TrackType.text, "花字"))
    for h in plan["huazi"]:
        seg = TextSegment(
            h["huazi"],
            Timerange(round(h["t0"] * SEC), round((h["t1"] - h["t0"]) * SEC)),
            style=TextStyle(size=13, bold=True, color=(1, 1, 1)),
            clip_settings=ClipSettings(transform_y=0.78,
                                       rotation=3 if h["style"] == "red" else -3),
            border=TextBorder(color=_rgb({"gold": "#FFD740", "red": "#FF5252",
                                          "blue": "#40C4FF"}[h["style"]]),
                              width=30),
            shadow=TextShadow(alpha=0.6, distance=6, diffuse=10))
        seg.add_animation(TextIntro.弹入, duration=0.5)
        script.add_segment(seg, hz_t)

    for p in dec.get("players") or []:
        if p.get("tagX") is None:
            continue
        t = script.append_track(TrackSpec(TrackType.text, f"人名条-{p['名字']}"))
        seg = TextSegment(
            p["名字"],
            Timerange(0, round(plan["total"] * SEC)),
            style=TextStyle(size=5, bold=True, color=(1, 1, 1)),
            clip_settings=ClipSettings(
                transform_x=round((p["tagX"] - 960) / 960, 3),
                transform_y=round(-(p["tagY"] - 540) / 540, 3)),
            border=TextBorder(color=_rgb(p["颜色"]), width=30),
            shadow=TextShadow(alpha=0.5, distance=4, diffuse=8))
        script.add_segment(seg, t)

    for m in dec.get("markers") or []:
        if m.get("kind") != "ring":
            continue
        t = script.append_track(TrackSpec(TrackType.text, f"归属环-{m['名字']}"))
        seg = TextSegment(
            "◯",
            Timerange(0, round(plan["total"] * SEC)),
            style=TextStyle(size=14, bold=True, color=_rgb(m["颜色"])),
            clip_settings=ClipSettings(
                transform_x=round((m["x"] - 960) / 960, 3),
                transform_y=round(-(m["y"] - 540) / 540, 3)))
        script.add_segment(seg, t)

    script.save()
    print(f"剪映草稿已生成：{DRAFT_ROOT / used}")
