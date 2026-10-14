"""Append the hard (difficulty=hard) case batch to datasets/golden; idempotent by case ID.

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


def main() -> None:
    for item in CASES:
        path = GOLDEN / f"{item['category']}.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = [line for line in lines if line.strip() and json.loads(line)["id"] != item["id"]]
        kept.append(json.dumps(item, ensure_ascii=False))
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print(f"Wrote {len(CASES)} hard cases into {GOLDEN}")


if __name__ == "__main__":
    main()
