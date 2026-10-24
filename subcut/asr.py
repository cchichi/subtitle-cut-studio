# -*- coding: utf-8 -*-
"""本地转录：抽音频 → faster-whisper（CPU int8）→ 简体清洗。"""
import json
import os
import subprocess
import time
from pathlib import Path


def _extract_audio(video: Path, wav: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
        check=True)


def transcribe(video: Path, out_json: Path, lang="zh", model_size="small"):
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    from faster_whisper import WhisperModel  # 延迟导入，缺依赖时报错清晰

    wav = out_json.with_suffix(".wav")
    _extract_audio(video, wav)

    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1:
            raise SystemExit("音频抽取异常：需要 16kHz 单声道")
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = pcm.astype(np.float32) / 32768.0

    t0 = time.time()
    model = WhisperModel(model_size, device="cpu", compute_type="int8",
                         download_root="asr_models")
    segments, info = model.transcribe(
        audio, language=lang, beam_size=5, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        word_timestamps=True, condition_on_previous_text=False)

    rows = [{"start": round(s.start, 3), "end": round(s.end, 3),
             "text": s.text.strip(),
             "words": [{"start": round(w.start, 3), "end": round(w.end, 3),
                        "word": w.word} for w in (s.words or [])]}
            for s in segments]

    # 简繁统一（中文场景）；其他语言原样保留
    if lang and lang.startswith("zh"):
        try:
            from opencc import OpenCC
            cc = OpenCC("t2s")
            for r in rows:
                r["text"] = cc.convert(r["text"])
                for w in r["words"]:
                    w["word"] = cc.convert(w["word"])
        except ImportError:
            print("(提示：pip install opencc-python-reimplemented 可统一简繁)")

    out_json.write_text(json.dumps({"language": info.language,
                                    "duration": info.duration,
                                    "segments": rows}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"  转录 {len(rows)} 段，用时 {time.time()-t0:.0f}s → {out_json}")
