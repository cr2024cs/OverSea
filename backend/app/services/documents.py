from pathlib import Path


def parse_document(path: Path, filename: str):
    suffix = Path(filename).suffix.lower()

    if suffix in {".txt", ".md"}:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
        pages = [text]
        return pages, text

    if suffix == ".docx":
        from docx import Document as DocxDocument

        document = DocxDocument(path)
        lines = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                lines.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(line for line in lines if line.strip())
        return [text], text

    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(pages).strip()
        if not text:
            raise ValueError("PDF 未提取到文本，可能为扫描件，请人工录入。")
        return pages, text

    raise ValueError("仅支持 txt、md、docx、文本型 pdf 文件。")
