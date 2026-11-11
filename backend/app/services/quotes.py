import re
import unicodedata


def parse_quote_text(raw_text):
    text = unicodedata.normalize("NFKC", raw_text or "").replace(",", "")
    if not text.strip():
        return None

    currency = "CNY"
    if any(token in text for token in ("美元", "USD", "$")):
        currency = "USD"
    elif any(token in text for token in ("泰铢", "THB", "฿")):
        currency = "THB"

    patterns = [
        (r"(\d+(?:\.\d+)?)\s*万\s*元", 10_000),
        (r"(\d+(?:\.\d+)?)\s*万元", 10_000),
        (r"(\d+(?:\.\d+)?)\s*元", 1),
        (r"(\d+(?:\.\d+)?)", 1),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1)) * multiplier
            return {
                "currency": currency,
                "amount_cents": int(round(amount * 100)),
            }
    return None


def provider_amount_for_project(project_id):
    from app.models import Quote, RFP

    rows = (
        Quote.query.join(RFP, Quote.rfp_id == RFP.id)
        .filter(RFP.project_id == project_id)
        .all()
    )
    lowest_by_task = {}
    for quote in rows:
        current = lowest_by_task.get(quote.task_id)
        if current is None or quote.amount_cents < current:
            lowest_by_task[quote.task_id] = quote.amount_cents
    return sum(lowest_by_task.values())
