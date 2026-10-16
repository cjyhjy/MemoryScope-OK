// 打印各段在成片中的起止时间
import {buildSync} from 'esbuild';
const out = buildSync({entryPoints: ['src/plan.ts'], bundle: true, write: false, format: 'esm', platform: 'node', loader: {'.json': 'json'}});
const m = await import('data:text/javascript;base64,' + Buffer.from(out.outputFiles[0].text).toString('base64'));
for (const s of m.plan.segs) console.log(s.id.padEnd(12), (s.from / 30).toFixed(1).padStart(6), (s.frames / 30).toFixed(1).padStart(6) + 's', 'rate', s.rate.toFixed(2), 'from', s.from);
console.log('total', (m.plan.total / 30).toFixed(1));
