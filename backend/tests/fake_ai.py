"""测试用 AI 替身：只在 pytest 中替换网络调用，不进入生产代码。"""

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

STEP_FILES = {
    "interview": "interview.json",
    "extract_facts": "facts.json",
    "propose": "proposal.json",
    "draft_rfp": "rfp.json",
    "parse_quote": "quote.json",
    "review_answer": "findings.json",
    "acceptance_summary": "summary.json",
    "retrospective": "retro.json",
}


def load_fixture(name):
    with (FIXTURE_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fake_remote(self, step, messages, json_mode=False):
    if step == "chat":
        return "已根据 30 项任务模板生成任务地图，关键路径已生成。", 0
    filename = STEP_FILES.get(step)
    if filename is None:
        raise AssertionError(f"unexpected AI step: {step}")
    return json.dumps(load_fixture(filename), ensure_ascii=False), 0
