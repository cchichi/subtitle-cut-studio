# -*- coding: utf-8 -*-
"""Subtitle Cut Studio —— 看着字幕剪视频的本地工具。

用法：
  python cut.py init <视频路径> [--lang zh] [--model small] [--prefill peaks|all|none]
      抽音频 → 本地转录 → 响度分析 → 参考帧/预览视频 → 生成「剪辑台.html」
  python cut.py build [--decisions witch_decisions.json]
      读剪辑决策 → 自带 ffmpeg 渲染器出片（成片.mp4）+ 质检
  python cut.py draft [--decisions witch_decisions.json]
      把决策同步成剪映可编辑草稿（需 pyJianYingDraft）

所有产物都在当前目录（out/、剪辑台.html、预览视频.mp4、成片.mp4）。
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from subcut import asr, analysis, editor, timeline, render, jianying  # noqa: E402

DEC_DEFAULT = Path("witch_decisions.json")


def check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("需要 ffmpeg + ffprobe（含 libx264/aac/libass）并在 PATH 上。")


def cmd_init(args):
    check_ffmpeg()
    video = Path(args.video).resolve()
    if not video.is_file():
        raise SystemExit(f"视频不存在: {video}")
    Path("out").mkdir(exist_ok=True)

    # 1) 转录（有旧转录则复用）
    tr_path = Path("out/asr_transcript.json")
    if args.reuse_transcript and tr_path.exists():
        print("[1/5] 复用已有转录 out/asr_transcript.json")
    else:
        print("[1/5] 本地转录（首次会下载模型，10 分钟视频约 2-5 分钟）…")
        asr.transcribe(video, tr_path, lang=args.lang, model_size=args.model)

    # 2) 响度剖面
    print("[2/5] 响度分析…")
    loud = analysis.loudness_profile(video)

    # 3) 参考帧 + 网格图 + 低码率预览
    print("[3/5] 生成参考帧与预览视频（约 1 分钟）…")
    ref_b64 = analysis.reference_grid(video)
    analysis.make_proxy(video, Path("预览视频.mp4"))

    # 4) 台词决策数据
    print("[4/5] 生成决策数据…")
    data = analysis.build_lines(tr_path, loud, prefill=args.prefill, title=video.stem)

    # 5) 剪辑台
    print("[5/5] 生成 剪辑台.html")
    editor.generate(data, ref_b64, loud, proxy_name="预览视频.mp4",
                    video_name=video.name)
    DEC_DEFAULT.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"\n完成！双击打开「剪辑台.html」做剪辑决策，导出后运行：")
    print(f"    python cut.py build")


def cmd_build(args):
    check_ffmpeg()
    dec_path = Path(args.decisions or DEC_DEFAULT)
    if not dec_path.exists():
        dl = Path.home() / "Downloads"
        cands = sorted(dl.glob("witch_decisions*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            shutil.copyfile(cands[0], dec_path)
            print("已从 Downloads 取决策:", cands[0].name)
        else:
            raise SystemExit("没找到决策文件，先在剪辑台里导出 witch_decisions.json")
    dec = json.loads(dec_path.read_text(encoding="utf-8"))
    plan = timeline.build_plan(dec)
    render.render_all(plan, Path("成片.mp4"))
    if args.draft:
        cmd_draft(args)


def cmd_draft(args):
    dec_path = Path(args.decisions or DEC_DEFAULT)
    dec = json.loads(dec_path.read_text(encoding="utf-8"))
    try:
        jianying.sync(dec, timeline.build_plan(dec))
    except ImportError:
        print("未安装 pyJianYingDraft（pip install pyJianYingDraft），跳过剪映草稿。")


def main():
    ap = argparse.ArgumentParser(description="字幕剪辑台 Subtitle Cut Studio")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化项目：转录+分析+生成剪辑台")
    p.add_argument("video")
    p.add_argument("--lang", default="zh")
    p.add_argument("--model", default="small")
    p.add_argument("--prefill", choices=["peaks", "all", "none"], default="peaks",
                   help="预填剪辑方式：peaks=响度高潮附近保留，all=全保留，none=全略过")
    p.add_argument("--reuse-transcript", action="store_true",
                   help="若 out/asr_transcript.json 存在则直接复用")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("build", help="按决策渲染成片")
    p.add_argument("--decisions")
    p.add_argument("--draft", action="store_true", help="成片后同步剪映草稿")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("draft", help="仅同步剪映草稿")
    p.add_argument("--decisions")
    p.set_defaults(func=cmd_draft)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
