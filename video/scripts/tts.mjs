// 用 macOS say 生成每句配音，输出 public/audio/*.wav 和 public/timeline.json
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import ffmpeg from 'ffmpeg-static';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const n = JSON.parse(fs.readFileSync(path.join(root, 'narration.json'), 'utf8'));
// 只影响发音，不影响字幕
const speak = [
  [/\bdeb\b/g, 'D E B'], [/SHA-256/g, 'SHA 256'], [/MEMORY\.md/g, 'memory 点 M D'],
  [/JSONL/g, 'JSON L'], [/custom-agents\.yaml/g, 'custom agents 点 yaml'],
  [/memoryscope-ok all/g, 'memoryscope OK all'], [/MemoryScope-OK/g, 'Memory Scope OK'],
  [/new_session/g, 'new session'], [/ARM64/g, 'ARM 64'], [/aarch64/g, 'A arch 64'], [/\bCLI\b/g, 'C L I'], [/\bjsonl\b/g, 'JSON L'], [/openKylin/g, 'open Kylin'],
];
const outDir = path.join(root, 'public/audio');
fs.mkdirSync(outDir, {recursive: true});
const tmp = fs.mkdtempSync(path.join(root, 'out/tts-'));
const timeline = [];
for (const seg of n.segments) {
  const lines = [];
  const src = n.liveMode === 'demo' && seg.linesDemo ? seg.linesDemo : seg.lines;
  src.forEach((text, i) => {
    let t = text;
    for (const [re, rep] of speak) t = t.replace(re, rep);
    const aiff = path.join(tmp, `${seg.id}_${i}.aiff`);
    const wav = `${seg.id}_${i}.wav`;
    execFileSync('say', ['-v', n.voice, '-r', String(n.rate), '-o', aiff, t]);
    execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', aiff, '-ar', '48000', '-ac', '2', path.join(outDir, wav)]);
    const bytes = fs.statSync(path.join(outDir, wav)).size - 44;
    lines.push({text, audio: `audio/${wav}`, seconds: +(bytes / (48000 * 2 * 2)).toFixed(3)});
  });
  timeline.push({id: seg.id, chapter: seg.chapter, lines});
}
fs.rmSync(tmp, {recursive: true, force: true});
fs.writeFileSync(path.join(root, 'public/timeline.json'), JSON.stringify(timeline, null, 2));
const total = timeline.flatMap(s => s.lines).reduce((a, l) => a + l.seconds, 0);
for (const s of timeline) console.log(s.id, s.lines.reduce((a, l) => a + l.seconds, 0).toFixed(1) + 's');
console.log('total speech', total.toFixed(1) + 's');
