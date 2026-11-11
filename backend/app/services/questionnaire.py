import json
from pathlib import Path

from app.config import PROJECT_ROOT

QUESTIONNAIRE_PATH = PROJECT_ROOT / "questionnaire v1.json"


def load_questionnaire():
    with QUESTIONNAIRE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _values(answers, question_id):
    value = answers.get(question_id)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _condition_met(condition, answers, project_fields, followup_codes):
    if not condition:
        return True
    if condition.get("always"):
        return True
    if "all" in condition:
        return all(
            _condition_met(item, answers, project_fields, followup_codes)
            for item in condition["all"]
        )
    if "any" in condition:
        return any(
            _condition_met(item, answers, project_fields, followup_codes)
            for item in condition["any"]
        )
    if "any_followup" in condition:
        return bool(followup_codes)
    if "q" in condition:
        values = _values(answers, condition["q"])
        if "in" in condition:
            return any(value in condition["in"] for value in values)
        if "not_in" in condition:
            return bool(values) and all(
                value not in condition["not_in"] for value in values
            )
    if "project" in condition:
        value = project_fields.get(condition["project"])
        if "in" in condition:
            return value in condition["in"]
        if "not_in" in condition:
            return value not in condition["not_in"]
    return False


def _summary(questionnaire, answers):
    questions = questionnaire["questions"]
    sections = {section["id"]: section["title"] for section in questionnaire["sections"]}
    labels = {}
    for question in questions:
        labels[question["id"]] = {
            option["code"]: option["label"] for option in question.get("options", [])
        }

    rows = []
    for question in questions:
        values = _values(answers, question["id"])
        if not values:
            continue
        if question["type"] == "text":
            answer_text = str(values[0])
        else:
            answer_text = "、".join(
                labels[question["id"]].get(value, value) for value in values
            )
        rows.append(
            {
                "id": question["id"],
                "section": sections.get(question.get("section"), ""),
                "question": question["text"],
                "answer": answer_text,
                "tasks": question.get("tasks", []),
            }
        )
    return rows


def _followups(questionnaire, answers):
    result = []
    for question in questionnaire["questions"]:
        selected = _values(answers, question["id"])
        for option in question.get("options", []):
            if option.get("followup") and option["code"] in selected:
                result.append(
                    {
                        "question_id": question["id"],
                        "question": question["text"],
                        "option_code": option["code"],
                        "option_label": option["label"],
                        "tasks": question.get("tasks", []),
                    }
                )
    return result


def evaluate(answers, project_fields):
    questionnaire = load_questionnaire()
    answers = answers or {}
    followup_items = _followups(questionnaire, answers)
    followup_codes = {
        f"{item['question_id']}::{item['option_code']}" for item in followup_items
    }

    selected = set(questionnaire["task_template"]["base_tasks"])
    custom_tasks = []
    subtasks = []
    variants = {}
    priorities = {}
    flags = []
    upload_requests = []
    pm_todos = []
    completed_tasks = []
    custom_index = 0

    def add_custom(name):
        nonlocal custom_index
        custom_index += 1
        code = f"C{custom_index:02d}"
        custom_tasks.append({"code": code, "name": name})
        selected.add(code)
        return code

    def run_actions(actions, current_condition=None):
        nonlocal selected
        for action in actions:
            kind = action.get("type")
            if kind == "add_tasks":
                selected.update(action.get("tasks", []))
            elif kind == "remove_tasks":
                selected.difference_update(action.get("tasks", []))
            elif kind == "add_tasks_if":
                if _condition_met(
                    action.get("if"), answers, project_fields, followup_codes
                ):
                    selected.update(action.get("tasks", []))
            elif kind == "actions_if":
                if _condition_met(
                    action.get("if"), answers, project_fields, followup_codes
                ):
                    run_actions(action.get("actions", []))
            elif kind == "add_custom_task":
                add_custom(action.get("name", "自定义任务"))
            elif kind == "add_subtask":
                subtasks.append(
                    {
                        "parent": action.get("parent"),
                        "name": action.get("name"),
                        "position": action.get("position", "child"),
                    }
                )
            elif kind == "set_variant":
                variants[action.get("task")] = {
                    "variant": action.get("variant"),
                    "note": action.get("note"),
                }
            elif kind == "set_priority":
                priorities[action.get("task")] = action.get("priority")
            elif kind == "flag":
                flags.append({"level": action.get("level"), "text": action.get("text")})
            elif kind == "request_upload":
                upload_requests.extend(action.get("tasks", []))
            elif kind == "pm_todo":
                pm_todos.append(action.get("text"))
            elif kind == "mark_done":
                completed_tasks.extend(action.get("tasks", []))
            elif kind == "apply_scope":
                choices = _values(answers, action.get("question"))
                scope_map = questionnaire.get(action.get("map"), {})
                if "full" in choices:
                    for tasks in scope_map.values():
                        selected.update(tasks)
                else:
                    for choice in choices:
                        selected.update(scope_map.get(choice, []))

    for rule in questionnaire.get("rules", []):
        if _condition_met(rule.get("when"), answers, project_fields, followup_codes):
            run_actions(rule.get("actions", []))

    summary = _summary(questionnaire, answers)
    return {
        "questionnaire_id": questionnaire.get("questionnaire_id"),
        "version": questionnaire.get("version"),
        "title": questionnaire.get("title"),
        "answers": answers,
        "summary": summary,
        "followups": followup_items,
        "selected_task_codes": sorted(selected),
        "custom_tasks": custom_tasks,
        "subtasks": subtasks,
        "variants": variants,
        "priorities": priorities,
        "flags": flags,
        "upload_requests": sorted(set(upload_requests)),
        "pm_todos": pm_todos,
        "completed_tasks": sorted(set(completed_tasks)),
    }
