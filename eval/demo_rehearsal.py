"""端到端演示彩排脚本：一键跑通七阶段，供 J 项连续 3 次彩排使用。"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Project  # noqa: E402
from app.seeds.seed import seed_all  # noqa: E402

DB_PATH = ROOT / "data" / "rehearsal.db"
ARCHIVE_DIR = ROOT / "data" / "rehearsal-archives"


def expect(response, status=200, label=""):
    if response.status_code != status:
        raise AssertionError(
            f"{label or 'request'} failed: {response.status_code} "
            f"{response.get_data(as_text=True)[:500]}"
        )
    return response.get_json()["data"] if response.is_json else None


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def run():
    for suffix in ("", "-wal", "-shm"):
        Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
    if ARCHIVE_DIR.exists():
        for item in ARCHIVE_DIR.glob("*.zip"):
            item.unlink()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{DB_PATH.as_posix()}",
            "AUTO_CREATE_TABLES": True,
            "AI_STREAM_DELAY_MS": 0,
            "ARCHIVE_DIR": str(ARCHIVE_DIR),
        }
    )
    if not app.config["AI_API_KEY"]:
        raise SystemExit(
            "demo_rehearsal 需要真实 DeepSeek：请在 backend/.env 配置 AI_API_KEY。"
        )
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_all()
        project_id = Project.query.first().id

    client = app.test_client()
    pm = expect(
        client.post(
            "/api/auth/login",
            json={"email": "pm@demo.local", "password": "demo1234"},
        ),
        200,
        "pm login",
    )["token"]
    lawyer = expect(
        client.post(
            "/api/auth/login",
            json={"email": "lawyer@demo.local", "password": "demo1234"},
        ),
        200,
        "lawyer login",
    )["token"]
    admin = expect(
        client.post(
            "/api/auth/login",
            json={"email": "admin@demo.local", "password": "demo1234"},
        ),
        200,
        "admin login",
    )["token"]
    print("[ok] 登录 PM / 律师 / 管理员")

    expect(client.post(f"/api/projects/{project_id}/facts/extract", headers=auth(pm)), 200, "facts")
    expect(client.post(f"/api/projects/{project_id}/interview", json={}, headers=auth(pm)), 200, "interview")
    expect(
        client.post(
            f"/api/projects/{project_id}/tasks/refresh",
            json={"scenario": "land_purchase"},
            headers=auth(pm),
        ),
        200,
        "task graph",
    )
    expect(client.post(f"/api/projects/{project_id}/requirement", headers=auth(pm)), 200, "requirement")

    client_token = expect(
        client.post(
            "/api/access-tokens",
            json={"project_id": project_id, "role_type": "client", "subject_id": "demo-client"},
            headers=auth(pm),
        ),
        201,
        "client token",
    )["token"]
    expect(client.post(f"/api/link/{client_token}/requirement/confirm"), 200, "requirement confirm")
    print("[ok] 阶段 1：事实、追问、任务图、需求确认")

    proposal = expect(
        client.post(f"/api/projects/{project_id}/proposals", headers=auth(pm)),
        201,
        "proposal",
    )
    expect(client.post(f"/api/proposals/{proposal['id']}/review", headers=auth(pm)), 200, "proposal review")
    expect(client.post(f"/api/proposals/{proposal['id']}/send", headers=auth(pm)), 200, "proposal send")
    expect(client.post(f"/api/link/{client_token}/proposal/confirm"), 200, "proposal confirm")
    print("[ok] 阶段 2：建议书生成、审核、发送、客户确认")

    expect(
        client.post(
            f"/api/projects/{project_id}/selection",
            json={"codes": ["T11"], "override_reason": "演示选择"},
            headers=auth(pm),
        ),
        200,
        "selection",
    )
    expect(
        client.post(
            f"/api/projects/{project_id}/candidates/generate",
            json={"task_codes": ["T11"]},
            headers=auth(pm),
        ),
        200,
        "candidates",
    )
    rfps = expect(
        client.post(
            f"/api/projects/{project_id}/rfps",
            json={"task_codes": ["T11"]},
            headers=auth(pm),
        ),
        201,
        "rfps",
    )
    rfp = next(row for row in rfps if row["status"] == "draft")
    expect(client.post(f"/api/rfps/{rfp['id']}/approve", headers=auth(pm)), 200, "rfp approve")
    expect(client.post(f"/api/rfps/{rfp['id']}/send", headers=auth(pm)), 200, "rfp send")
    expect(
        client.post(
            f"/api/rfp-link/{rfp['token']}/quote",
            json={"amount_cents": 50_000_000, "currency": "CNY"},
        ),
        201,
        "quote",
    )
    client_quote = expect(
        client.post(f"/api/projects/{project_id}/client-quotes", json={}, headers=auth(pm)),
        201,
        "client quote",
    )
    expect(client.post(f"/api/client-quotes/{client_quote['id']}/send", headers=auth(pm)), 200, "client quote send")
    expect(client.post(f"/api/link/{client_token}/client-quote/confirm"), 200, "client quote confirm")
    print("[ok] 阶段 3–4：选服务、候选、询价、报价、总报价确认")

    contract = expect(
        client.post(f"/api/projects/{project_id}/contracts", headers=auth(pm)),
        201,
        "contract",
    )
    expect(client.post(f"/api/contracts/{contract['id']}/review", headers=auth(pm)), 200, "contract review")
    expect(client.post(f"/api/link/{client_token}/contract/confirm"), 200, "contract client confirm")
    provider_id = contract["provider_contracts"][0]["provider_id"]
    provider_token = expect(
        client.post(
            "/api/access-tokens",
            json={"project_id": project_id, "role_type": "provider", "subject_id": provider_id},
            headers=auth(pm),
        ),
        201,
        "provider token",
    )["token"]
    expect(client.post(f"/api/link/{provider_token}/contract/confirm"), 200, "contract provider confirm")
    print("[ok] 阶段 5：合同、SLA、节点、双确认生效")

    board = expect(client.get(f"/api/projects/{project_id}/board", headers=auth(pm)), 200, "board")
    milestone_id = board["milestones"][0]["id"]
    expect(
        client.post(
            f"/api/milestones/{milestone_id}/submission",
            json={"note": "服务商答复：二手设备都可以免税进口。"},
            headers=auth(pm),
        ),
        200,
        "submission",
    )
    expect(
        client.post(
            f"/api/milestones/{milestone_id}/pm-review",
            json={"decision": "accept"},
            headers=auth(pm),
        ),
        200,
        "pm review",
    )
    findings = expect(
        client.post(f"/api/milestones/{milestone_id}/review", json={}, headers=auth(pm)),
        200,
        "ai review",
    )
    letter = expect(
        client.post(
            f"/api/projects/{project_id}/query-letters",
            json={"milestone_id": milestone_id, "provider_id": provider_id},
            headers=auth(pm),
        ),
        201,
        "query letter",
    )
    expect(client.post(f"/api/query-letters/{letter['id']}/approve", headers=auth(lawyer)), 200, "query approve")
    expect(client.post(f"/api/query-letters/{letter['id']}/send", headers=auth(pm)), 200, "query send")
    replies = [{"finding_id": row["id"], "reply": "已补充说明"} for row in letter["findings"]]
    expect(
        client.post(
            f"/api/link/{provider_token}/query-letter/reply",
            json={"replies": replies},
        ),
        200,
        "query reply",
    )
    expect(client.post(f"/api/query-letters/{letter['id']}/close", headers=auth(pm)), 200, "query close")

    seed_letter = expect(
        client.post(
            f"/api/projects/{project_id}/query-letters",
            json={"provider_id": provider_id},
            headers=auth(pm),
        ),
        201,
        "seed query letter",
    )
    expect(client.post(f"/api/query-letters/{seed_letter['id']}/approve", headers=auth(lawyer)), 200, "seed query approve")
    expect(client.post(f"/api/query-letters/{seed_letter['id']}/send", headers=auth(pm)), 200, "seed query send")
    seed_replies = [
        {"finding_id": row["id"], "reply": "已补充说明"} for row in seed_letter["findings"]
    ]
    expect(
        client.post(
            f"/api/link/{provider_token}/query-letter/reply",
            json={"replies": seed_replies},
        ),
        200,
        "seed query reply",
    )
    expect(client.post(f"/api/query-letters/{seed_letter['id']}/close", headers=auth(pm)), 200, "seed query close")
    print(f"[ok] 阶段 6：看板、初审、AI 审查（{len(findings)} 条）、质询关闭")

    expect(
        client.post(
            f"/api/milestones/{milestone_id}/pm-review",
            json={"decision": "accept"},
            headers=auth(pm),
        ),
        200,
        "pm review after findings",
    )
    invite = expect(
        client.post(f"/api/milestones/{milestone_id}/expert-invite", headers=auth(pm)),
        201,
        "expert invite",
    )
    expert_token = invite["token"]
    expect(
        client.post(
            f"/api/link/{expert_token}/expert/review",
            json={
                "scores": {"completeness": 90, "quality": 90, "executability": 90, "timeliness": 90},
                "comment": "交付完整，可执行。",
                "conflict_declared": True,
            },
        ),
        200,
        "expert review",
    )
    finalized = expect(
        client.post(f"/api/milestones/{milestone_id}/finalize", headers=auth(pm)),
        200,
        "finalize",
    )
    expect(client.post(f"/api/milestones/{milestone_id}/client-confirm", headers=auth(pm)), 200, "milestone client confirm")
    print(f"[ok] 阶段 6：专家盲评、验收 {finalized['status']}、解锁 {finalized['unlocked_tasks']}")

    retrospective = expect(
        client.post(f"/api/projects/{project_id}/retrospective", headers=auth(pm)),
        200,
        "retrospective",
    )
    metrics = expect(client.get(f"/api/projects/{project_id}/metrics", headers=auth(pm)), 200, "metrics")
    archive = expect(
        client.post(f"/api/projects/{project_id}/archives", headers=auth(pm)),
        201,
        "archive",
    )
    download = client.get(f"/api/archives/{archive['id']}/download", headers=auth(pm))
    expect(download, 200, "archive download")
    zip_files = list(ARCHIVE_DIR.glob("*.zip"))
    assert zip_files
    with zipfile.ZipFile(zip_files[-1]) as bundle:
        assert "manifest.json" in bundle.namelist()
    print(
        "[ok] 阶段 7：复盘、指标 "
        f"(质询率 {metrics['effective_query_rate']['value']}%)、归档 zip、只读"
    )

    expect(client.post("/api/admin/demo/reset", headers=auth(admin)), 200, "demo reset")
    print("[ok] 管理员一键重置")
    print("REHEARSAL OK")


if __name__ == "__main__":
    run()
