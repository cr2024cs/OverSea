from app.config import PROJECT_ROOT
from app.models import KnowledgeChunk
from app.seeds.seed import seed_all


def test_knowledge_chunks_have_valid_offsets(app):
    with app.app_context():
        seed_all()
        chunks = KnowledgeChunk.query.all()

    assert chunks
    assert {chunk.doc_code for chunk in chunks} == {f"{index:02d}" for index in range(1, 10)}

    texts = {
        path.name.split("_", 1)[0]: path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "rag").glob("*.md")
    }

    for chunk in chunks:
        source = texts[chunk.doc_code]
        assert chunk.char_start < chunk.char_end
        assert source[chunk.char_start : chunk.char_end].strip() == chunk.content
        assert "source_priority:" not in chunk.content
        assert "last_reviewed:" not in chunk.content
