import io

from docx import Document as DocxDocument
from pypdf import PdfWriter

from app.models import Document, Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _setup(app):
    with app.app_context():
        seed_all()
        return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def _headers(app):
    client = app.test_client()
    return client, bearer(login_token(client))


def test_upload_txt_document(app):
    project_id = _setup(app)
    client, headers = _headers(app)

    response = client.post(
        f"/api/projects/{project_id}/documents",
        data={
            "file": (
                io.BytesIO("投资总额 3,000 万美元，其中设备实物出资 800 万美元。".encode("utf-8")),
                "客户说明.txt",
            )
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["filename"] == "客户说明.txt"
    assert payload["page_count"] == 1

    listing = client.get(
        f"/api/projects/{project_id}/documents", headers=headers
    ).get_json()["data"]
    assert any(item["id"] == payload["id"] for item in listing)

    with app.app_context():
        row = Document.query.filter_by(filename="客户说明.txt").first()
        assert "800 万美元" in row.text_content
        assert row.page_texts_json


def test_upload_docx_document(app):
    project_id = _setup(app)
    client, headers = _headers(app)

    buffer = io.BytesIO()
    document = DocxDocument()
    document.add_paragraph("目标：第 14 个月试产。")
    document.add_paragraph("投资总额 3,000 万美元。")
    document.save(buffer)
    buffer.seek(0)

    response = client.post(
        f"/api/projects/{project_id}/documents",
        data={"file": (buffer, "项目说明.docx")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert response.status_code == 201

    with app.app_context():
        row = Document.query.filter_by(filename="项目说明.docx").first()
        assert "第 14 个月试产" in row.text_content


def test_upload_scanned_pdf_rejected(app):
    project_id = _setup(app)
    client, headers = _headers(app)

    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    buffer.seek(0)

    response = client.post(
        f"/api/projects/{project_id}/documents",
        data={"file": (buffer, "扫描件.pdf")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "parse_failed"


def test_upload_rejects_unsupported_and_oversized(app):
    project_id = _setup(app)
    client, headers = _headers(app)

    unsupported = client.post(
        f"/api/projects/{project_id}/documents",
        data={"file": (io.BytesIO(b"binary"), "setup.exe")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 400

    oversized = client.post(
        f"/api/projects/{project_id}/documents",
        data={"file": (io.BytesIO(b"x" * 250_000), "big.txt")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert oversized.status_code == 413
