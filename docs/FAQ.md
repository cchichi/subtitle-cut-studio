# 常见问题

**ffmpeg 怎么装？** 需要包含 libx264 / aac / libass 的完整构建。Windows 推荐 gyan.dev 的 essentials/full 包；macOS `brew install ffmpeg`。装完 `ffmpeg -version` 能看到即可。

**字幕字体？** ASS 字幕用"微软雅黑"（Windows 自带）。macOS/Linux 请把 `subcut/timeline.py` 里的 `Fontname` 改成系统有的中文字体（如 `PingFang SC`、`Noto Sans CJK SC`），缺中文字体时字幕会变豆腐块。

**剪映草稿打不开/生成失败？** ① 剪映正开着同名草稿会锁文件，工具会自动改用 B/C 后缀新名字；② 剪映 11.x 会把保存过的草稿加密回存，本工具每次整份重新生成明文草稿，实测 11.6 可正常打开。

**成片时长和预估差一两秒？** 正常现象。渲染按片段逐段编码，每段存在帧级取整，会随片段数累积（质检容差已考虑）。

**慢放的音频会变调吗？** 不会，音频走 atempo 变速不变调。

**换个视频要重新 init 吗？** 是。每个视频一个独立目录跑 `init`，互不影响。
