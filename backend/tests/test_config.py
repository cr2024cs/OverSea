from app.seeds.seed import seed_all


def test_config_returns_only_enabled_options(app):
    with app.app_context():
        seed_all()

    response = app.test_client().get("/api/config")
    assert response.status_code == 200
    data = response.get_json()["data"]

    assert [item["code"] for item in data["country"]] == ["TH"]
    assert [item["code"] for item in data["industry"]] == ["manufacturing"]
    assert [item["code"] for item in data["entry_mode"]] == ["greenfield"]
    assert {item["code"] for item in data["currency"]} == {"CNY", "THB", "USD"}
