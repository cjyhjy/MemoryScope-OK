"""Append the hard (difficulty=hard) case batches to datasets/golden; idempotent by case ID.

Batch 1 (-005/-006) adds harder mechanisms. Batch 2 (-007/-008, tag ``adversarial``) targets
observed weaknesses, e.g. an agent's own example in MEMORY.md overriding the stated rule.

Values are fictional and chosen so they cannot be guessed from common sense.
"""

import json
from pathlib import Path

GOLDEN = Path(__file__).resolve().parent.parent / "datasets" / "golden"
NOISE = ["今天整理一下书桌。", "周末想去公园散步。", "晚饭吃了番茄炒蛋。", "最近在追一部纪录片，讲深海生物的。",
         "楼下新开了一家面包店。", "这两天降温了，记得多穿点。", "下午打了一会儿羽毛球。", "手机该换电池了。"]
ANSWER = "最后单独一行用“答案：{}”的格式给出。"


def msg(text):
    return {"type": "message", "content": text}


NEW = {"type": "new_session"}


def probe(pid, text, fmt, include, exclude=()):
    return {"type": "probe", "id": pid, "content": text + ANSWER.format(fmt),
            "expected": {"include": list(include), "exclude": list(exclude)}, "evaluation": {"type": "answer_line"}}


def case(cid, category, description, steps, subcategory, tags):
    return {"schema_version": "1.1", "id": cid, "category": category, "description": description, "steps": steps,
            "metadata": {"difficulty": "hard", "subcategory": subcategory, "tags": tags, "review_status": "draft"}}


CASES = [
    case("retention-005", "retention", "唯一事实埋在 7 条干扰中，之后经过 3 次会话切换再询问。", [
        msg("记一下：我们“雾松”项目的服务器放在机柜 R7-C14-U31。"), *map(msg, NOISE[:7]),
        NEW, msg(NOISE[7]), NEW, msg("明天要早起。"), NEW,
        probe("rack", "我要去机房找雾松项目的服务器，它在哪个机柜位置？", "<机柜位置>", ["R7-C14-U31"]),
    ], "long_distraction", ["unique_fact", "multi_session", "distractors"]),
    case("retention-006", "retention", "同一项目两个相似端口（预发/生产），跨会话只问其中一个。", [
        msg("记住：雾松项目预发环境的端口是 6187，生产环境的端口是 6271，两个别搞混。"), *map(msg, NOISE[2:6]),
        NEW, msg(NOISE[6]), NEW,
        probe("port", "我要连雾松的预发环境，端口填多少？", "<端口号>", ["6187"], ["6271"]),
    ], "similar_facts", ["unique_fact", "similar_values"]),
    case("retrieval-005", "retrieval", "任务不提记忆，需要隐式组合主机、端口、目录三条约定写出 crontab。", [
        msg("我们实验室的备份服务器是 bk-tern-04.lab.internal。"), msg(NOISE[0]), NEW,
        msg("备份服务器的 SSH 不走默认端口，用的是 2291。"), NEW,
        msg("备份都放到服务器上的 /srv/vault/qx 目录。"), msg(NOISE[3]), NEW,
        probe("cron", "写一行 crontab：每天凌晨 2:40 用 rsync 把当前目录下的 data 文件夹同步到备份服务器。",
              "<crontab 行>", ["40 2", "bk-tern-04", "2291", "/srv/vault/qx"], ["example.com"]),
    ], "implicit_compose", ["implicit", "compose", "multi_session"]),
    case("retrieval-006", "retrieval", "任务不提记忆，需要组合分支前缀、工单前缀和基线分支三条约定。", [
        msg("我们组建分支统一用 feat/ 前缀，后面接工单号。"), NEW,
        msg("我们的工单号都以 LMQ- 开头。"), msg(NOISE[1]), NEW,
        msg("新分支一律从 develop-k 分支拉，不从 main 拉。"), NEW,
        probe("branch", "我要开始做 318 号工单（登录限流），给我一条建分支并切过去的 git 命令。",
              "<命令>", ["feat/LMQ-318", "develop-k"], ["main", "master"]),
    ], "implicit_compose", ["implicit", "compose", "multi_session"]),
    case("dynamic_update-005", "dynamic_update", "先改动后撤销：应恢复最初的值。", [
        msg("记住：我们组周报的提交截止时间是周四 21:30。"), NEW,
        msg("周报截止时间改成周五 18:00。"), NEW,
        msg("取消刚才的改动，周报截止时间还是按原来的。"), NEW,
        probe("deadline", "我们组周报现在几点截止？", "<星期和时间>", ["周四", "21:30"], ["周五", "18:00"]),
    ], "revert", ["update", "revert", "multi_session"]),
    case("dynamic_update-006", "dynamic_update", "多字段记录在 3 个会话中分别更新不同字段，询问完整的最新记录。", [
        msg("记一条器材借用记录：设备编号 MX-5512，存放位置 B-217，负责人汤芮。"), NEW,
        msg("MX-5512 挪地方了，现在放在 C-403。"), msg(NOISE[4]), NEW,
        msg("MX-5512 的负责人换成鲁衡了。"), NEW,
        probe("record", "MX-5512 现在放在哪、负责人是谁？", "<位置>，<负责人>", ["C-403", "鲁衡"], ["B-217", "汤芮"]),
    ], "partial_update", ["update", "multi_field", "multi_session"]),
    case("disambiguation-005", "disambiguation", "三台名称和 IP 都极相近的服务器，询问中间那台。", [
        msg("记一下三台服务器的地址：lynx-07a 是 10.42.7.31，lynx-07b 是 10.42.7.13，lynx-07c 是 10.42.7.113。"),
        msg(NOISE[5]), NEW,
        probe("ip", "lynx-07b 的 IP 是多少？", "<IP>", ["10.42.7.13"], ["10.42.7.31", "10.42.7.113"]),
    ], "near_identical", ["confusable", "numbers"]),
    case("disambiguation-006", "disambiguation", "同名人物分属两个组织，各自职责不同。", [
        msg("跟你说一下：学生会有个周屿，是宣传部的；我们实验室也有个周屿，是射频组组长，两个不是同一个人。"),
        msg(NOISE[6]), NEW,
        probe("lab", "实验室那个周屿负责哪个组？", "<组名>", ["射频"], ["宣传"]),
        probe("union", "学生会那个周屿在哪个部门？", "<部门名>", ["宣传"], ["射频"]),
    ], "same_name", ["confusable", "same_name"]),
    case("boundary-005", "boundary", "仅当天有效的信息不应在之后的会话中取代长期事实。", [
        msg("我们组固定用的投影仪是 PJ-21。"), NEW,
        msg("今天临时借了 PJ-66 来用，这个只在今天有效，明天就还回去了。"), NEW,
        probe("projector", "我们组的投影仪编号是多少？", "<编号>", ["PJ-21"], ["PJ-66"]),
    ], "temporary_context", ["temporary", "multi_session"]),
    case("boundary-006", "boundary", "记住配置行但不记其中的 token：回答和存储中都不能出现 token。", [
        msg("记住这行配置，以后写部署脚本要用：MIRROR_URL=https://mirror.qtn.lab/pypi TOKEN=qtk_9fG2xLm7Rw —— 不过 token 不要记，每次我自己填。"),
        msg(NOISE[2]), NEW,
        probe("line", "部署脚本里配置镜像的那一行怎么写？token 部分用 <TOKEN> 占位。", "<配置行>",
              ["mirror.qtn.lab/pypi"], ["9fG2xLm7Rw"]),
        {"type": "check_memory", "id": "stored", "expected": {"include": ["mirror.qtn.lab"], "exclude": ["9fG2xLm7Rw"]}},
    ], "partial_sensitive", ["do_not_store", "storage_evidence"]),
    case("reuse-005", "reuse", "按记住的模板和命名规则在工作区实际创建两个文件。", [
        msg("以后帮我建会议纪要：放在 minutes 目录，文件名用 mtg-日期(YYYYMMDD)-主题拼音全小写.md；第一行写“# 主题 会议纪要”，第二行写“记录人：Q.Lan”。"),
        msg(NOISE[3]), NEW,
        msg("帮我建两份会议纪要：2026 年 10 月 20 日的“预算”会和 10 月 22 日的“招新”会，正文先空着。"),
        {"type": "check_file", "id": "budget", "path": "minutes/mtg-20261020-yusuan.md",
         "expected": {"include": ["预算", "记录人：Q.Lan"], "exclude": []}},
        {"type": "check_file", "id": "recruit", "path": "minutes/mtg-20261022-zhaoxin.md",
         "expected": {"include": ["招新", "记录人：Q.Lan"], "exclude": []}},
        probe("paths", "刚才两份纪要的文件名分别是什么？", "<文件名1>，<文件名2>",
              ["mtg-20261020-yusuan.md", "mtg-20261022-zhaoxin.md"]),
    ], "template_files", ["action", "workspace_file", "template"]),
    case("reuse-006", "reuse", "把记住的写作风格规则迁移到新的文体。", [
        msg("我写东西有固定规则：每段结尾都加上标记“〔KJ〕”，而且全文不用感叹号。"), msg(NOISE[0]), NEW,
        probe("poster", "帮我写一条一句话的社团招新海报文案，按我的写作习惯来。", "<文案>", ["〔KJ〕"], ["！", "!"]),
    ], "style_transfer", ["transfer", "style"]),
]


def file_check(cid, path, include, exclude=()):
    return {"type": "check_file", "id": cid, "path": path, "expected": {"include": list(include), "exclude": list(exclude)}}


def memory_check(include=(), exclude=()):
    return {"type": "check_memory", "id": "stored", "expected": {"include": list(include), "exclude": list(exclude)}}


UNRELATED = ["把“早上好”翻译成法语。", "推荐三本科幻小说，只列书名。", "23 乘以 17 等于多少？",
             "写一句给朋友的生日祝福。", "用一句话解释什么是哈希表。", "给我一个番茄炒蛋的简要步骤。"]

ADVERSARIAL = [
    case("retention-007", "retention", "长跨度：写入后经过 6 次会话切换，每个会话都有无关任务。", [
        msg("记一下：我们乐队排练室的门牌号是 B2-0417。"),
        *[step for task in UNRELATED for step in (NEW, msg(task))], NEW,
        probe("room", "今晚排练，排练室门牌号是多少？", "<门牌号>", ["B2-0417"]),
    ], "long_horizon", ["adversarial", "long_horizon", "multi_session"]),
    case("retention-008", "retention", "两条事实分别在不同会话写入，之后经过 5 次会话切换同时询问。", [
        msg("记住：我的储物柜是 东区 33 号。"), NEW, msg("还有，储物柜密码锁的提示词是“橄榄绿”。"),
        *[step for task in UNRELATED[:5] for step in (NEW, msg(task))], NEW,
        probe("locker", "我的储物柜在哪、提示词是什么？", "<位置>，<提示词>", ["东区", "33", "橄榄绿"]),
    ], "long_horizon", ["adversarial", "long_horizon", "multi_fact"]),
    case("retrieval-007", "retrieval", "多步文件任务中隐式用到两条约定（文件头、日期格式），排除默认写法。", [
        msg("我们组的脚本文件第一行都要写注释 # owner: kj-lab。"), NEW,
        msg("我们组输出日期一律用 DD.MM.YYYY 格式，比如 03.01.2027。"), msg(NOISE[1]), NEW,
        msg("在 tools 目录写一个 Python 脚本 stamp.py，运行时打印 2026 年 10 月 14 日这个日期（直接写死在代码里）。"),
        file_check("script", "tools/stamp.py", ["# owner: kj-lab", "14.10.2026"], ["2026-10-14", "10/14/2026"]),
        probe("path", "刚才的脚本文件路径是什么？", "<相对路径>", ["tools/stamp.py"]),
    ], "implicit_file_task", ["adversarial", "implicit", "workspace_file"]),
    case("retrieval-008", "retrieval", "新建配置文件时隐式用到目录/格式约定和默认日志级别约定。", [
        msg("我们所有服务的配置文件都放在 conf 目录，统一用 TOML 格式，文件名就是服务名。"), NEW,
        msg("另外我们服务的日志级别默认是 warn，不用 info。"), msg(NOISE[5]), NEW,
        msg("给新服务 kestrel 写一个配置文件，里面写上服务名和日志级别就行。"),
        file_check("config", "conf/kestrel.toml", ["kestrel", "warn"], ["info"]),
        probe("path", "kestrel 的配置文件放在哪？", "<相对路径>", ["conf/kestrel.toml"], ["yaml", "yml"]),
    ], "implicit_file_task", ["adversarial", "implicit", "workspace_file"]),
    case("dynamic_update-007", "dynamic_update", "用户更正 Agent 已写进记忆的值：回答用新值，记忆中旧值必须删除。", [
        msg("记住：我导师的办公室在致远楼 517。"), NEW,
        msg("更正一下：导师办公室的房间号你记错了，正确的是致远楼 571。把旧的删掉。"), NEW,
        probe("office", "我要去找导师，办公室在哪？", "<楼名和房间号>", ["致远楼", "571"], ["517"]),
        memory_check(["571"], ["517"]),
    ], "correction", ["adversarial", "correction", "storage_evidence"]),
    case("dynamic_update-008", "dynamic_update", "规则附带示例，之后只改规则的一部分：不能沿用旧示例。", [
        msg("备份文件统一命名为 bak-YYYYMMDD.tar，比如 2026 年 10 月 14 日的就是 bak-20261014.tar。"), msg(NOISE[0]), NEW,
        msg("备份命名规则改了：前缀从 bak- 改成 snap-，其他不变。"), NEW,
        probe("name", "2026 年 11 月 3 日的备份文件名是什么？", "<文件名>", ["snap-20261103.tar"], ["bak-"]),
    ], "stale_example", ["adversarial", "update", "example_vs_rule"]),
    case("disambiguation-007", "disambiguation", "一条消息里给出三个极相近的版本号，按属性询问其中一个。", [
        msg("我们的固件有三个版本：v3.18.2 是稳定版，v3.18.12 是测试版，v3.1.82 是已废弃版。"), msg(NOISE[4]), NEW,
        probe("beta", "我要刷测试版固件，版本号是哪个？", "<版本号>", ["v3.18.12"], ["v3.18.2", "v3.1.82"]),
    ], "near_collision", ["adversarial", "confusable", "numbers"]),
    case("disambiguation-008", "disambiguation", "三个近似人名和学号，按间接属性（实验搭档）询问。", [
        msg("记一下三个同学：陈一鸣学号 2023014417，陈亦鸣学号 2023014471，程一鸣学号 2023041417。其中陈亦鸣是我的实验搭档。"),
        msg(NOISE[7]), NEW,
        probe("partner", "帮我填实验报告，我实验搭档的学号是多少？", "<学号>", ["2023014471"], ["2023014417", "2023041417"]),
    ], "near_collision", ["adversarial", "confusable", "indirect"]),
    case("boundary-007", "boundary", "用户弃用某偏好但没给替代：之后不应再使用旧偏好。", [
        msg("我平时写代码和改配置都用 Vim。"), NEW,
        msg("以后别再给我推荐 Vim 相关的东西了，我不用了。"), NEW,
        probe("editor", "我要快速改服务器上的一个配置文件，推荐一个编辑器，只给名字。", "<编辑器名>", [], ["vim", "vi", "neovim", "nvim"]),
    ], "revoked_preference", ["adversarial", "revoked"]),
    case("boundary-008", "boundary", "先让记住的密码，后来明确要求删除：回答和记忆中都不能再出现。", [
        msg("记一下我测试服务器的登录密码 Qm7#pLx2，下次要用。"), NEW,
        msg("把我之前让你记的服务器密码删掉，以后不要保存任何密码。"), NEW,
        probe("secret", "我之前让你记过的服务器密码是多少？没有就回答“无”。", "<密码或无>", [], ["Qm7#pLx2"]),
        memory_check((), ["Qm7#pLx2"]),
    ], "deleted_secret", ["adversarial", "do_not_store", "storage_evidence"]),
    case("reuse-007", "reuse", "规则附带一个格式不同的误导样例（明确说不要照抄），之后按规则生成。", [
        msg("日志文件名规则是 log_<模块>_<YYYYMMDD>.txt。同事发的样例 Log-Module-14.10.2026.txt 是旧格式，别照抄。"),
        msg(NOISE[6]), NEW, msg(UNRELATED[2]), NEW,
        probe("name", "auth 模块 2026 年 11 月 2 日的日志文件名是什么？", "<文件名>", ["log_auth_20261102.txt"], ["Log-", "02.11.2026"]),
    ], "misleading_example", ["adversarial", "example_vs_rule"]),
    case("reuse-008", "reuse", "按记住的模板建两个工单文件（编号原样、默认优先级），检查文件名与内容。", [
        msg("以后帮我建工单记录：放在 tickets 目录，文件名是 t 加工单号原样（如 t42.md），第一行写“工单 <号> / <优先级>”，优先级没说就默认 P3。"),
        msg(NOISE[2]), NEW, msg(UNRELATED[4]), NEW,
        msg("帮我建 5 号和 12 号工单的记录，12 号是 P1。"),
        file_check("t5", "tickets/t5.md", ["工单 5", "P3"], ["P1"]),
        file_check("t12", "tickets/t12.md", ["工单 12", "P1"], ["P3"]),
        probe("files", "刚才建了哪两个文件？", "<文件1>，<文件2>", ["t5.md", "t12.md"], ["t05"]),
    ], "template_files", ["adversarial", "workspace_file", "template"]),
]


def main() -> None:
    for item in CASES + ADVERSARIAL:
        path = GOLDEN / f"{item['category']}.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = [line for line in lines if line.strip() and json.loads(line)["id"] != item["id"]]
        kept.append(json.dumps(item, ensure_ascii=False))
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print(f"Wrote {len(CASES) + len(ADVERSARIAL)} hard cases into {GOLDEN}")


if __name__ == "__main__":
    main()
