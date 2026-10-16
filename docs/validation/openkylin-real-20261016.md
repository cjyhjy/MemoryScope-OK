# openKylin 48×2 真实全量评测（2026-10-16）

## 结论

- Run：`20261016T064413939014Z-0d5dfa7e5bd8`，状态 `completed`，`synthetic: false`。
- 数据：48 条 draft cases，六维各 8 条；两个真实 Agent 共生成 96 条 case 结果。
- Codex CLI + DeepSeek：47 pass / 1 fail，六维总分 97.9，覆盖率 100%。
- DeepSeek Harness + DeepSeek：48 pass / 0 fail，六维总分 100.0，覆盖率 100%。
- 这证明真实执行、隔离、证据和报告闭环；48 条仍未完成独立人工质量复核，不能称为最终 golden，也不据单次运行宣称统计显著或产品优劣。

原始产物：[报告](../../runs/20261016T064413939014Z-0d5dfa7e5bd8/report/report.md)、[雷达图](../../runs/20261016T064413939014Z-0d5dfa7e5bd8/report/radar.png)、`results.json`、`events.jsonl`、`metadata.json`、配置与数据快照均位于同一 run 目录。

## 环境与身份

- openKylin 3.0 (huanghe)，aarch64，Linux 7.0.0-3-generic，Python 3.12.2。
- MemoryScope-OK 0.3.0，evaluator 1.2，schema 1.1；只使用确定性 `contains` / `answer_line` 等检查，未启用 LLM Judge。
- codex-cli 0.162.1，模型 `deepseek-flash`，提供方 DeepSeek API。
- dsh 0.2.0-rc.2，模型与读回的 `effective_model` 均为 `deepseek-flash`，提供方 `deepseek-official`。
- 客体 checkout 由白名单源码归档展开，不含 Git 历史，因此 metadata 的 `git_commit` 为 null；`source_sha256` 为 `abea4acde462ac78b71dc15443e40c4dd46bed61434e600d561bc44e73e56a05`。

## 六维结果

| 维度 | Codex CLI | dsh |
| --- | ---: | ---: |
| retention | 100.0（8/8） | 100.0（8/8） |
| retrieval | 100.0（8/8） | 100.0（8/8） |
| dynamic_update | 87.5（7/8） | 100.0（8/8） |
| disambiguation | 100.0（8/8） | 100.0（8/8） |
| boundary | 100.0（8/8） | 100.0（8/8） |
| reuse | 100.0（8/8） | 100.0（8/8） |
| **六维总分** | **97.9** | **100.0** |

Codex 唯一未通过项为 `dynamic_update-007`：最终回答正确使用新值“致远楼 571”，但 `MEMORY.md` 仍保留“旧值 517 已作废”文字，命中了存储检查禁止出现的旧值。这是保存下来的存储层证据失败，没有为提分修改规则或结果。

## 隔离、事件与完整性

- 96 个 case 使用 96 个唯一 namespace；每个 case 都记录 `case_reset`，且 reset 后没有遗留 memory。
- `events.jsonl` 共 1506 条，序号连续、时间单调；包含 96 个 `case_finished`、96 个 `case_reset`、270 个 `session_reset`、124 个 evaluation，两个 Agent 各有 start/shutdown。
- 运行开始于 2026-10-16 06:44:13 UTC，结束于 07:40:50 UTC，约 56 分 36 秒。
- 产物从客体通过临时 VMware 私有共享目录带回，目标目录此前不存在，未覆盖旧 run。传输归档 SHA-256：`5ed48c950c992c2aad88d3ba06702ccb0dab76bd98f417afe705aea5fc719f1d`。
- 宿主机读回的关键文件 SHA-256 与 metadata 一致：配置 `59f5723683a2a99ee59f0dc2638f33b3293eec7167579eebfcccbee3788d19ed`，数据快照 `05dbeaed234f3e40d94d13ee3d66cb80162c9628bef0d7848751a14237e86faa`，事件 `257ced42e43698a50b5f45cdb47d3624c8e6caf821aa04b16ae161bc5a37b4e9`，结果 `6bc8dd9bc1f0390051d6ea7e165dfa9bd9e6522e86fed3161416d28a65b38b91`。
- 宿主机执行 `memoryscope report <run> --reuse --json` 成功，证明报告与来源结果匹配。雷达图已目视核对：标题、run ID、六轴、图例和 87.5 差异均清晰，无明显遮挡。
- 对 run 目录扫描未发现 `DEEPSEEK_API_KEY=` 赋值或常见 `sk-...` 密钥形态；metadata 只记录环境变量名，不记录值。

## 未完成边界

- 只做了每个 Agent 一次全量执行，没有重复采样、均值或方差。
- `MEMORY.md` 是评测框架统一声明的外部长期记忆约定，不等同于产品原生记忆功能。
- 48 条均为 draft；数据质量复核和更高区分度设计仍待完成。
- GUI、CLI/GUI 联调、.deb 实装、Python 3.10、3–5 分钟录屏和完整一键脚本验收仍待完成。
