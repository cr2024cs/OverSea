from datetime import datetime

from app.ai.provider import AIProvider, AIProviderError
from app.models import Fact, Finding, Task, TaskTemplate
from app.services.rag import search_knowledge
from app.services.task_graph import compute_schedule

STAGE_LABELS = {
    0: "前期诊断与方案设计",
    1: "境内对外投资手续（ODI）",
    2: "泰国公司设立",
    3: "BOI 投资优惠",
    4: "土地、厂房与工厂许可",
    5: "设备跨境转移",
    6: "泰国员工招募与管理",
    7: "中国员工派驻",
    8: "投产后的持续合规",
}


def _yuan(cents):
    return f"{cents / 100:,.0f}"


def _build_services(tasks):
    grouped = {}
    for task in tasks:
        grouped.setdefault(task.stage_no, []).append(
            {
                "code": task.code,
                "name": task.name,
                "deliverables": task.deliverables_json or [],
            }
        )
    return [
        {
            "stage": stage,
            "stage_label": STAGE_LABELS.get(stage, f"阶段 {stage}"),
            "tasks": grouped[stage],
        }
        for stage in sorted(grouped)
    ]


def build_proposal_content(project):
    facts = Fact.query.filter_by(project_id=project.id).all()
    tasks = (
        Task.query.filter_by(project_id=project.id)
        .order_by(Task.stage_no.asc(), Task.code.asc())
        .all()
    )
    if not tasks:
        raise ValueError("请先生成任务地图，再生成项目建议书。")

    templates = TaskTemplate.query.filter_by(enabled=True).all()
    low = sum(template.fee_min_cents for template in templates)
    high = sum(template.fee_max_cents for template in templates)
    mid = (low + high) // 2

    task_dicts = [
        {
            "code": task.code,
            "name": task.name,
            "duration_days": task.duration_days,
            "predecessors": task.predecessor_codes_json or [],
        }
        for task in tasks
    ]
    try:
        schedule = compute_schedule(task_dicts)
        critical_path = schedule["critical_path"]
        total_days = schedule["total_days"]
    except ValueError:
        critical_path = []
        total_days = 0

    task_by_code = {task.code: task for task in tasks}
    critical_names = [
        f"{code} {task_by_code[code].name}"
        for code in critical_path
        if code in task_by_code
    ]

    query = " ".join(
        [
            project.goal_text or "",
            *[f"{fact.key} {fact.value}" for fact in facts],
            *[task.name for task in tasks[:12]],
            "BOI 投资优惠 环评 工作许可 土地 厂房",
        ]
    )
    references = search_knowledge(
        query,
        country=project.country,
        industry=project.industry,
        limit=8,
    )

    provider = AIProvider()
    outcome = provider.run(
        "propose",
        {
            "project_id": project.id,
            "facts": [{"key": fact.key, "value": fact.value} for fact in facts],
            "task_codes": [task.code for task in tasks],
        },
    )
    result = outcome.get("result")
    if not isinstance(result, dict) or not result.get("chapters"):
        raise AIProviderError("建议书输出格式不正确：缺少 chapters")

    content = {
        **result,
        "chapters": [dict(chapter) for chapter in result.get("chapters", [])],
    }

    services = _build_services(tasks)
    findings = Finding.query.filter_by(project_id=project.id).all()
    risk_categories = sorted({finding.category for finding in findings})
    budget = {
        "low_cents": low,
        "mid_cents": mid,
        "high_cents": high,
        "currency": "CNY",
        "basis": "任务模板费用区间（冷启动），未使用历史报价基准",
        "assumptions": [
            "不含政府规费、差旅与第三方检测费用",
            "不含工程建设、设备采购与厂房租金",
            "以园区内租赁厂房为基准场景",
        ],
    }

    chapter_updates = {
        3: (
            f"共 {len(tasks)} 项任务，分为 {len(services)} 个阶段："
            + "、".join(item["stage_label"] for item in services)
            + "。服务清单按阶段列示，客户可在下一步按阶段或单项选择。"
        ),
        4: (
            f"关键路径为：{' → '.join(critical_names) if critical_names else '待生成'}。"
            f"按模板工期估算，总周期约 {total_days} 天。ODI 完成前注资与设备不能出境。"
        ),
        5: (
            "建议按关键路径设置里程碑："
            + "、".join(critical_names[:6])
            + "。每个节点提交对应批文、证书或验收记录，由 PM 或专家验收。"
        ),
        6: (
            f"专业服务费用参考区间为低 {_yuan(low)} 元、中 {_yuan(mid)} 元、"
            f"高 {_yuan(high)} 元人民币。依据为任务模板费用区间（冷启动），"
            "未使用历史报价基准；不含政府规费、差旅、工程建设与设备采购。"
            "该区间为估算，非正式报价。"
        ),
        7: (
            "主要风险：BOI 活动类别判断偏差、二手设备年限与性能证书、"
            "土地许可与关键路径延误、跨文件设备清单不一致、泰籍员工比例。"
            + (f" 已识别发现类别：{'、'.join(risk_categories)}。" if risk_categories else "")
            + " 客户需及时提供工艺说明、设备清单、评估报告与人员计划。"
        ),
    }
    for chapter in content["chapters"]:
        if chapter.get("id") in chapter_updates:
            chapter["content"] = chapter_updates[chapter["id"]]

    content.update(
        {
            "services": services,
            "budget": budget,
            "references": references,
            "disclaimer": "本预算为估算区间，非正式报价。",
            "generated_at": datetime.utcnow().isoformat(),
            "model": outcome["model"],
        }
    )
    return content
