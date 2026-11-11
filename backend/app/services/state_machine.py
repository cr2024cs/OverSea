"""统一定义项目阶段、项目状态与关键业务对象的状态流转。"""

from app.extensions import db


class FlowError(ValueError):
    """非法状态流转。"""

    status_code = 409


PHASE_LABELS = {
    1: "调研",
    2: "建议",
    3: "询价",
    4: "报价",
    5: "签约",
    6: "履约",
    7: "归档",
}

STATUS_LABELS = {
    "draft": "新建",
    "diagnosing": "调研中",
    "requirement_pending": "需求待确认",
    "proposal_generating": "建议书生成中",
    "proposal_pending": "建议书待确认",
    "service_selecting": "服务选择中",
    "inquiry_sent": "询价中",
    "quote_pending": "报价待确认",
    "quote_confirmed": "报价已确认",
    "contracting": "签约中",
    "active": "已生效",
    "executing": "执行中",
    "accepting": "验收中",
    "closed": "已关闭",
    "paused": "已暂停",
    "cancelled": "已取消",
}


def _ensure(project, phases, statuses):
    if project.phase not in phases or project.status not in statuses:
        raise FlowError(
            f"当前状态不允许该操作：阶段 {project.phase}，状态 {project.status}"
        )


def _task_map_generated(project):
    _ensure(project, {1}, {"draft", "diagnosing", "requirement_pending"})
    if project.status == "draft":
        project.status = "diagnosing"


def _requirement_generated(project):
    _ensure(project, {1}, {"draft", "diagnosing", "requirement_pending"})
    project.status = "requirement_pending"


def _proposal_generated(project):
    _ensure(
        project,
        {1, 2},
        {"draft", "diagnosing", "requirement_pending", "proposal_pending"},
    )
    project.phase = 2
    project.status = "proposal_pending"


def _proposal_confirmed(project):
    _ensure(project, {2}, {"proposal_pending"})
    project.phase = 3
    project.status = "service_selecting"


def _proposal_revision(project):
    _ensure(project, {2}, {"proposal_pending"})
    project.status = "proposal_pending"


def _client_quote_created(project):
    _ensure(
        project,
        {3, 4},
        {"service_selecting", "quote_pending", "quote_confirmed"},
    )
    project.phase = 4
    project.status = "quote_pending"


def _client_quote_confirmed(project):
    _ensure(project, {4}, {"quote_pending"})
    project.status = "quote_confirmed"


def _contract_generated(project):
    _ensure(
        project,
        {4, 5},
        {"quote_pending", "quote_confirmed", "contracting"},
    )
    project.phase = 5
    project.status = "contracting"


def _contracts_activated(project):
    _ensure(project, {5}, {"contracting"})
    project.phase = 6
    project.status = "executing"


def _project_archived(project):
    _ensure(project, {6}, {"executing", "accepting"})
    project.phase = 7
    project.status = "closed"
    project.archived = True


PROJECT_EVENTS = {
    "task_map_generated": _task_map_generated,
    "requirement_generated": _requirement_generated,
    "proposal_generated": _proposal_generated,
    "proposal_confirmed": _proposal_confirmed,
    "proposal_revision_requested": _proposal_revision,
    "client_quote_created": _client_quote_created,
    "client_quote_confirmed": _client_quote_confirmed,
    "contract_generated": _contract_generated,
    "contracts_activated": _contracts_activated,
    "project_archived": _project_archived,
}


def fire_project(project, event):
    handler = PROJECT_EVENTS.get(event)
    if handler is None:
        raise FlowError(f"未知项目事件：{event}")
    handler(project)
    return project


PROPOSAL_EVENTS = {
    "review": {"from": {"generated"}, "to": "pm_reviewed"},
    "send": {"from": {"pm_reviewed"}, "to": "sent"},
    "confirm": {"from": {"sent"}, "to": "client_confirmed"},
    "revision": {"from": {"sent"}, "to": "revision_requested"},
}


def fire_proposal(proposal, event):
    rule = PROPOSAL_EVENTS.get(event)
    if rule is None:
        raise FlowError(f"未知建议书事件：{event}")
    if proposal.status not in rule["from"]:
        raise FlowError(f"建议书当前状态不允许该操作：{proposal.status}")
    proposal.status = rule["to"]
    return proposal


CONTRACT_EVENTS = {
    "review": {"from": {"draft"}, "to": "pending_client"},
    "client_confirm": {"from": {"pending_client"}, "to": "pending_provider"},
    "activate": {"from": {"pending_provider"}, "to": "active"},
}


def fire_contract(contract, event):
    rule = CONTRACT_EVENTS.get(event)
    if rule is None:
        raise FlowError(f"未知合同事件：{event}")
    if contract.status not in rule["from"]:
        raise FlowError(f"合同当前状态不允许该操作：{contract.status}")
    contract.status = rule["to"]
    return contract


MILESTONE_EVENTS = {
    "submit": {
        "from": {"pending_submission", "submitted", "expert_review"},
        "to": "submitted",
    },
    "pm_accept": {"from": {"submitted"}, "to": "expert_review"},
    "pm_return": {"from": {"submitted"}, "to": "pending_submission"},
    "review": {
        "from": {"pending_submission", "submitted", "expert_review", "reviewing"},
        "to": "reviewing",
    },
    "expert_submitted": {"from": {"expert_review", "client_confirm"}, "to": "client_confirm"},
    "finalize": {
        "from": {"expert_review", "client_confirm"},
        "to": None,
    },
    "rectify": {"from": {"failed", "conditional", "passed"}, "to": "pending_submission"},
}


def fire_milestone(milestone, event, conclusion=None):
    rule = MILESTONE_EVENTS.get(event)
    if rule is None:
        raise FlowError(f"未知节点事件：{event}")
    if milestone.status not in rule["from"]:
        raise FlowError(f"节点当前状态不允许该操作：{milestone.status}")
    if event == "finalize":
        if conclusion not in {"passed", "conditional", "failed"}:
            raise FlowError("验收结论无效")
        milestone.status = conclusion
    else:
        milestone.status = rule["to"]
    return milestone


RFP_EVENTS = {
    "approve": {"from": {"draft"}, "to": "approved"},
    "send": {"from": {"approved"}, "to": "sent"},
    "reply": {"from": {"sent", "replied"}, "to": "replied"},
}


def fire_rfp(rfp, event):
    rule = RFP_EVENTS.get(event)
    if rule is None:
        raise FlowError(f"未知询价书事件：{event}")
    if rfp.status not in rule["from"]:
        raise FlowError(f"询价书当前状态不允许该操作：{rfp.status}")
    rfp.status = rule["to"]
    return rfp


def fire_quote(quote):
    quote.status = "received"
    return quote


CLIENT_QUOTE_EVENTS = {
    "send": {"from": {"draft"}, "to": "sent"},
    "confirm": {"from": {"sent"}, "to": "confirmed"},
}


def fire_client_quote(quote, event):
    rule = CLIENT_QUOTE_EVENTS.get(event)
    if rule is None:
        raise FlowError(f"未知客户总报价事件：{event}")
    if quote.status not in rule["from"]:
        raise FlowError(f"客户总报价当前状态不允许该操作：{quote.status}")
    quote.status = rule["to"]
    return quote


QUERY_LETTER_EVENTS = {
    "send": {"from": {"draft"}, "to": "sent"},
    "reply": {"from": {"sent", "replied"}, "to": "replied"},
    "close": {"from": {"replied"}, "to": "closed"},
}


def fire_query_letter(letter, event):
    rule = QUERY_LETTER_EVENTS.get(event)
    if rule is None:
        raise FlowError(f"未知质询函事件：{event}")
    if letter.status not in rule["from"]:
        raise FlowError(f"质询函当前状态不允许该操作：{letter.status}")
    letter.status = rule["to"]
    return letter


def project_state(project):
    return {
        "phase": project.phase,
        "phase_label": PHASE_LABELS.get(project.phase, str(project.phase)),
        "status": project.status,
        "status_label": STATUS_LABELS.get(project.status, project.status),
        "archived": project.archived,
    }


def commit_transition(project, event):
    fire_project(project, event)
    db.session.flush()
    return project
