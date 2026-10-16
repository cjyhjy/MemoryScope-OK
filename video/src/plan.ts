import timeline from '../public/timeline.json';
import edit from '../edit.json';

export const FPS = 30;
export const INTRO = 6 * FPS;
export const OUTRO = 7 * FPS;
const LEAD = Math.round(0.6 * FPS); // 每段开头先看画面再说话

export type Zoom = {t: number; s: number; x: number; y: number};
type Clip = {in: number; out: number; zoom?: Zoom[]} | null;
export type Line = {text: string; audio: string; from: number; frames: number};
export type Seg = {
  id: string; chapter: string; index: number; from: number; frames: number;
  lines: Line[]; clip: Clip; rate: number; srcFrames: number;
};

const f = (s: number) => Math.round(s * FPS);

export const plan = (() => {
  let cursor = INTRO;
  const segs: Seg[] = timeline.map((s, index) => {
    let t = LEAD;
    const lines = s.lines.map((l) => {
      const line = {text: l.text, audio: l.audio, from: t, frames: f(l.seconds)};
      t += line.frames + f(edit.gap);
      return line;
    });
    const speech = t + f(0.5);
    const clip = (edit.segments as Record<string, Clip>)[s.id] ?? null;
    let frames = speech, rate = 1, srcFrames = 0;
    if (clip) {
      srcFrames = f(clip.out - clip.in);
      // 录屏比配音长就加速（不超过 maxSpeed），超出部分保留原速播完
      rate = Math.min(edit.maxSpeed, Math.max(1, srcFrames / speech));
      frames = Math.max(speech, Math.ceil(srcFrames / rate));
    }
    const seg = {id: s.id, chapter: s.chapter, index, from: cursor, frames, lines, clip, rate, srcFrames};
    cursor += frames;
    return seg;
  });
  return {segs, outroFrom: cursor, total: cursor + OUTRO};
})();
export {edit};
