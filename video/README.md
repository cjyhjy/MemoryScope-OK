# 演示视频剪辑工程

Remotion + 项目内 ffmpeg（`ffmpeg-static`），不依赖系统安装。分镜见 `../docs/demo-script.md`。

1. 旁白稿：`narration.json`（每行 = 一句字幕 + 一段配音）。改完运行 `node scripts/tts.mjs` 重新生成配音（macOS `say`，婷婷）。
2. 录屏：放到 `public/rec/demo.mov`，在 `edit.json` 里填每段的起止秒数 `in/out`。
3. 预览：`npm run studio`；导出：`npm run render`，成片在 `out/memoryscope-ok-demo.mp4`。

`remotion.config.ts` 指定用系统 Chrome 渲染（自带的 headless shell 在本机启动失败）。
