import React from 'react';
import {
  AbsoluteFill, Audio, Easing, Freeze, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import {FPS, INTRO, OUTRO, Seg, Zoom, edit, plan} from './plan';

const FONT = '"PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif';
const BG = '#0d1b2a';
const ACCENT = '#3fa7ff';

const fade = (frame: number, dur: number, edge = 12) =>
  interpolate(frame, [0, edge, dur - edge, dur], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

const Intro = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 30% 30%, #1b3a5c, ${BG})`, fontFamily: FONT, color: 'white',
      justifyContent: 'center', alignItems: 'center', opacity: fade(frame, INTRO, 15)}}>
      <div style={{fontSize: 40, color: ACCENT, letterSpacing: 4, opacity: s}}>2026 上海开源软件应用创新大赛 · openKylin 赛题</div>
      <div style={{fontSize: 150, fontWeight: 700, marginTop: 30, transform: `translateY(${(1 - s) * 40}px)`}}>MemoryScope-OK</div>
      <div style={{fontSize: 56, marginTop: 20, opacity: interpolate(frame, [20, 45], [0, 1], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp'})}}>
        智能体长期记忆自动化评测 Benchmark
      </div>
      <div style={{fontSize: 32, marginTop: 50, color: '#9fb3c8', opacity: interpolate(frame, [45, 70], [0, 1], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp'})}}>
        六维评测 · 证据驱动的确定性评分 · openKylin 原生运行
      </div>
    </AbsoluteFill>
  );
};

const Outro = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: BG, fontFamily: FONT, color: 'white', justifyContent: 'center', alignItems: 'center',
      opacity: fade(frame, OUTRO, 15)}}>
      <div style={{fontSize: 120, fontWeight: 700}}>MemoryScope-OK</div>
      <div style={{fontSize: 44, marginTop: 30, color: '#cfd9e3'}}>智能体长期记忆自动化评测 Benchmark</div>
      <div style={{fontSize: 38, marginTop: 60, color: ACCENT}}>{edit.repoUrl}</div>
      <div style={{fontSize: 30, marginTop: 40, color: '#9fb3c8'}}>谢谢观看</div>
    </AbsoluteFill>
  );
};

const Placeholder = ({seg}: {seg: Seg}) => (
  <AbsoluteFill style={{background: '#22313f', justifyContent: 'center', alignItems: 'center', fontFamily: FONT, color: '#8fa3b5'}}>
    <div style={{fontSize: 48}}>[ 录屏占位：{seg.chapter} ]</div>
    <div style={{fontSize: 28, marginTop: 16}}>{seg.id}</div>
  </AbsoluteFill>
);

const ChapterTag = ({seg}: {seg: Seg}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const dur = Math.min(seg.frames, 4 * FPS);
  const x = spring({frame, fps, config: {damping: 200}});
  return (
    <div style={{position: 'absolute', top: 48, left: 48, fontFamily: FONT, display: 'flex', alignItems: 'center',
      opacity: fade(frame, dur, 10), transform: `translateX(${(x - 1) * 60}px)`}}>
      <div style={{background: ACCENT, color: 'white', fontSize: 34, fontWeight: 700, padding: '10px 20px', borderRadius: '10px 0 0 10px'}}>
        {String(seg.index + 1).padStart(2, '0')}
      </div>
      <div style={{background: 'rgba(13,27,42,0.88)', color: 'white', fontSize: 34, padding: '10px 26px', borderRadius: '0 10px 10px 0'}}>
        {seg.chapter}
      </div>
    </div>
  );
};

const Caption = ({text, frames}: {text: string; frames: number}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 22, opacity: fade(frame, frames, 4)}}>
      <div style={{fontFamily: FONT, fontSize: 40, color: 'white', background: 'rgba(0,0,0,0.72)', padding: '10px 28px',
        borderRadius: 12, maxWidth: 1700, textAlign: 'center', lineHeight: 1.35}}>{text}</div>
    </AbsoluteFill>
  );
};

const Radar = ({frames}: {frames: number}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: BG, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', paddingBottom: 110,
      gap: 80, fontFamily: FONT, color: 'white', opacity: fade(frame, frames, 15)}}>
      <Img src={staticFile('radar.png')} style={{height: 740, borderRadius: 16, background: 'white'}} />
      <div style={{fontSize: 44, lineHeight: 1.9}}>
        <div style={{color: ACCENT, fontSize: 36}}>openKylin 实测 · 48 条 × 2 个真实智能体</div>
        <div>DeepSeek Harness　<b>100.0</b></div>
        <div>Codex CLI　<b>97.9</b></div>
        <div style={{fontSize: 32, color: '#9fb3c8', marginTop: 20}}>长期保持 · 记忆调用 · 动态更新<br />相近区分 · 边界识别 · 任务复用</div>
      </div>
    </AbsoluteFill>
  );
};

// 按源时间插值推近镜头
const zoomAt = (zs: Zoom[] | undefined, t: number): Zoom => {
  if (!zs || zs.length === 0) return {t, s: 1, x: 0.5, y: 0.5};
  if (t <= zs[0].t) return zs[0];
  for (let i = 1; i < zs.length; i++) {
    if (t <= zs[i].t) {
      const a = zs[i - 1], b = zs[i];
      const k = interpolate(t, [a.t, b.t], [0, 1], {easing: Easing.inOut(Easing.cubic)});
      return {t, s: a.s + (b.s - a.s) * k, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k};
    }
  }
  return zs[zs.length - 1];
};

const Screen = ({seg}: {seg: Seg}) => {
  const frame = useCurrentFrame();
  const clip = seg.clip!;
  const c = edit.crop;
  const visible = Math.ceil(seg.srcFrames / seg.rate);
  const srcT = clip.in + Math.min(frame, visible) * seg.rate / FPS + Math.max(0, frame - visible) / FPS;
  const z = zoomAt(clip.zoom, srcT);
  const k = Math.min(1920 / c.w, 1080 / c.h);
  const W = c.w * k, H = c.h * k;
  const clampT = (v: number, lim: number) => Math.max(-lim, Math.min(lim, v));
  const tx = clampT((0.5 - z.x) * W * z.s, (W * z.s - W) / 2);
  const ty = clampT((0.5 - z.y) * H * z.s, (H * z.s - H) / 2);
  const video = {position: 'absolute' as const, width: c.srcW * k, height: c.srcH * k, left: -c.x * k, top: -c.y * k, maxWidth: 'none'};
  return (
    <AbsoluteFill style={{background: BG, justifyContent: 'center', alignItems: 'center'}}>
      <div style={{width: W, height: H, overflow: 'hidden', position: 'relative', boxShadow: '0 0 40px rgba(0,0,0,0.5)'}}>
        <div style={{position: 'absolute', inset: 0, transform: `translate(${tx}px, ${ty}px) scale(${z.s})`, transformOrigin: 'center center'}}>
          <Sequence durationInFrames={visible}>
            <OffthreadVideo src={staticFile(edit.recording)} muted playbackRate={seg.rate}
              startFrom={Math.round(clip.in * FPS)} endAt={Math.round(clip.out * FPS)} style={video} />
          </Sequence>
          {seg.frames > visible && (
            <Sequence from={visible}>
              <Freeze frame={0}>
                <OffthreadVideo src={staticFile(edit.recording)} muted startFrom={Math.max(0, Math.round(clip.out * FPS) - 2)} style={video} />
              </Freeze>
            </Sequence>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Segment = ({seg}: {seg: Seg}) => {
  return (
    <AbsoluteFill style={{background: 'black'}}>
      {seg.clip ? <Screen seg={seg} /> : <Placeholder seg={seg} />}
      {seg.id === 's9_summary' && edit.radarInSummary && <Radar frames={seg.frames} />}
      <ChapterTag seg={seg} />
      {seg.lines.map((l) => (
        <Sequence key={l.audio} from={l.from} durationInFrames={l.frames + 6}>
          <Audio src={staticFile(l.audio)} />
          <Caption text={l.text} frames={l.frames + 6} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const Main = () => (
  <AbsoluteFill style={{background: 'black'}}>
    <Sequence durationInFrames={INTRO}><Intro /></Sequence>
    {plan.segs.map((s) => (
      <Sequence key={s.id} from={s.from} durationInFrames={s.frames}><Segment seg={s} /></Sequence>
    ))}
    <Sequence from={plan.outroFrom} durationInFrames={OUTRO}><Outro /></Sequence>
  </AbsoluteFill>
);
