import json

import pytest

from app.ai.provider import AIProvider, AIConfigError, AIProviderError
from app.models import Conversation, Message, Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _setup(app):
    with app.app_context():
        seed_all()
        return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def _conversation(client, headers, project_id, title="演示对话"):
    payload = {"title": title} if title else {}
    response = client.post(
        f"/api/projects/{project_id}/conversations",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def _stream_text(body):
    chunks = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = json.loads(line[6:])
        chunks.append(payload.get("delta", ""))
    return "".join(chunks)


def test_chat_streams_and_persists_messages(app):
    project_id = _setup(app)
    client = app.test_client()
    headers = bearer(login_token(client))
    conversation_id = _conversation(client, headers, project_id, title=None)

    response = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "请生成任务地图"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"

    body = response.get_data(as_text=True)
    assert "data:" in body
    assert "任务地图" in _stream_text(body)
    assert '"done": true' in body

    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    ).get_json()["data"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["intent"] == "tasks"

    with app.app_context():
        row = Conversation.query.filter_by(id=conversation_id).one()
        assert row.title == "请生成任务地图"


def test_new_conversation_starts_empty(app):
    project_id = _setup(app)
    client = app.test_client()
    headers = bearer(login_token(client))
    first = _conversation(client, headers, project_id)
    second = _conversation(client, headers, project_id)

    client.post(
        "/api/chat",
        json={"conversation_id": first, "message": "生成建议书"},
        headers=headers,
    )

    second_messages = client.get(
        f"/api/conversations/{second}/messages", headers=headers
    ).get_json()["data"]
    assert second_messages == []


def test_chat_validation(app):
    project_id = _setup(app)
    client = app.test_client()
    headers = bearer(login_token(client))
    conversation_id = _conversation(client, headers, project_id)

    empty = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "   "},
        headers=headers,
    )
    assert empty.status_code == 400

    missing = client.post(
        "/api/chat",
        json={"conversation_id": "missing", "message": "你好"},
        headers=headers,
    )
    assert missing.status_code == 404


def test_artifacts_facts_and_document(app):
    project_id = _setup(app)
    client = app.test_client()
    headers = bearer(login_token(client))

    facts = client.get(
        f"/api/projects/{project_id}/artifacts?type=facts", headers=headers
    ).get_json()["data"]
    assert len(facts) == 5
    citation = facts[0]["citation"]
    assert citation["doc_id"]
    assert citation["filename"]

    document = client.get(
        f"/api/documents/{citation['doc_id']}", headers=headers
    ).get_json()["data"]
    assert document["text"]
    assert facts[0]["quote"] in document["text"]


def test_artifacts_tasks_findings_and_quotes(app):
    project_id = _setup(app)
    client = app.test_client()
    headers = bearer(login_token(client))

    tasks = client.get(
        f"/api/projects/{project_id}/artifacts?type=tasks", headers=headers
    ).get_json()["data"]
    assert len(tasks) == 30
    assert any(task["is_critical"] for task in tasks)

    findings = client.get(
        f"/api/projects/{project_id}/artifacts?type=findings", headers=headers
    ).get_json()["data"]
    assert len(findings) == 8
    assert sum(1 for row in findings if row["is_legal"]) == 6

    quotes = client.get(
        f"/api/projects/{project_id}/artifacts?type=quotes", headers=headers
    ).get_json()["data"]
    assert len(quotes["quotes"]) == 1
    assert quotes["total"]["total_cents"] == 47_000_000


def test_provider_requires_api_key(app):
    with app.app_context():
        provider = AIProvider(api_key="")
        with pytest.raises(AIConfigError):
            provider.run("chat", {"intent": "default"})


def test_provider_rejects_invalid_json(app, monkeypatch):
    with app.app_context():
        provider = AIProvider(api_key="test-key")
        monkeypatch.setattr(
            provider,
            "_remote",
            lambda step, messages, json_mode=False: ("not json", 0),
        )
        with pytest.raises(AIProviderError):
            provider.run("propose", {})
