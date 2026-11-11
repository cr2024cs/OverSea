from app.models import Conversation, Message, Project, Task
from app.seeds.seed import seed_all
from app.services.questionnaire import evaluate
from tests.helpers import bearer, login_token


def _client(app, email="client@demo.local"):
    client = app.test_client()
    return client, bearer(login_token(client, email=email))


def test_questionnaire_endpoint(app):
    with app.app_context():
        seed_all()

    client, headers = _client(app)
    response = client.get("/api/questionnaire", headers=headers)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["questionnaire_id"] == "overseas_project_intake"
    assert len(data["questions"]) == 41
    assert len(data["rules"]) == 32


def test_rule_engine_generates_task_scope_and_followups(app):
    with app.app_context():
        result = evaluate(
            {
                "Q06": "undecided",
                "Q09": ["equipment_in_kind"],
                "Q21": "mainly_transfer",
            },
            {"country": "TH", "industry": "manufacturing", "entry_mode": "greenfield"},
        )

    assert any(item["question_id"] == "Q06" for item in result["followups"])
    for code in ("T03", "T19", "T21", "T22", "T23"):
        assert code in result["selected_task_codes"]


def test_client_creates_project_with_questionnaire_and_welcome(app):
    with app.app_context():
        seed_all()

    client, headers = _client(app)
    answers = {
        "Q01": "private",
        "Q02": "auto",
        "Q04": "none",
        "Q05": "none",
        "Q06": "greenfield",
        "Q07": "wfoe",
        "Q08": "direct",
        "Q09": ["equipment_in_kind"],
        "Q10": ["own_funds"],
        "Q11": "idea",
        "Q12": "12_18m",
        "Q13": ["follow_customer"],
        "Q14": ["local"],
        "Q15": "region_only",
        "Q16": "eec",
        "Q17": "in_estate",
        "Q18": "buy_build",
        "Q19": "10k_30k",
        "Q20": ["none"],
        "Q21": "mainly_transfer",
        "Q22": ["lt_5"],
        "Q23": "1m_10m",
        "Q24": "no",
        "Q25": ["general_only"],
        "Q26": "no",
        "Q27": "100_300",
        "Q28": "5_20",
        "Q29": ["production_tech"],
        "Q30": "keep_china",
        "Q31": ["none"],
        "Q32": "not_started",
        "Q33": "no",
        "Q34": "not_apply",
        "Q35": ["none"],
        "Q36": ["company_setup"],
        "Q37": "none",
        "Q40": "chairman_ceo",
    }
    response = client.post(
        "/api/projects",
        json={
            "country": "TH",
            "industry": "manufacturing",
            "entry_mode": "greenfield",
            "currency": "USD",
            "investment_cents": 3_000_000_000,
            "goal_text": "泰国设厂",
            "questionnaire": {"answers": answers},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.get_json()
    project_id = response.get_json()["data"]["id"]

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        assert project.questionnaire_json["selected_task_codes"]
        assert project.questionnaire_json["summary"]
        conversation = Conversation.query.filter_by(project_id=project_id).first()
        assert conversation is not None
        message = Message.query.filter_by(conversation_id=conversation.id).first()
        assert "问卷已完成" in message.content

    pm, pm_headers = _client(app, "pm@demo.local")
    refreshed = pm.post(
        f"/api/projects/{project_id}/tasks/refresh",
        json={"scenario": "lease"},
        headers=pm_headers,
    )
    assert refreshed.status_code == 200
    codes = {task["code"] for task in refreshed.get_json()["data"]["tasks"]}
    assert "T19" in codes
    assert "T11" not in codes
    assert len(codes) < 30
