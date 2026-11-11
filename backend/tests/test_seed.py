from app.extensions import db
from app.models import ConfigItem, Conversation, Message, Project
from app.seeds.seed import seed_all


def test_seed_is_idempotent(app):
    with app.app_context():
        first = seed_all()
        second = seed_all()

    assert first == second
    assert first["config_items"] == 12
    assert first["users"] == 6
    assert first["providers"] == 10
    assert first["task_templates"] == 30
    assert first["knowledge_documents"] == 9
    assert first["projects"] == 2
    assert first["tasks"] == 60
    assert first["findings"] == 16


def test_reset_demo_keeps_single_project(app):
    with app.app_context():
        seed_all()
        project = Project.query.first()
        conversation = Conversation(project_id=project.id, title="演示对话")
        db.session.add(conversation)
        db.session.flush()
        db.session.add(
            Message(
                conversation_id=conversation.id,
                project_id=project.id,
                role="user",
                content="测试消息",
            )
        )
        db.session.commit()

        result = seed_all(reset_demo=True)

        assert Conversation.query.count() == 1
        assert Message.query.count() == 2

    assert result["projects"] == 2
    assert result["tasks"] == 60


def test_only_thailand_is_enabled(app):
    with app.app_context():
        seed_all()
        countries = ConfigItem.query.filter_by(type="country", enabled=True).all()
        industries = ConfigItem.query.filter_by(type="industry", enabled=True).all()
        modes = ConfigItem.query.filter_by(type="entry_mode", enabled=True).all()

    assert [item.code for item in countries] == ["TH"]
    assert [item.code for item in industries] == ["manufacturing"]
    assert [item.code for item in modes] == ["greenfield"]
