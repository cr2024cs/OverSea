import re
import unicodedata


def normalize(text):
    value = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def _ngrams(value, size=3):
    if len(value) <= size:
        return {value} if value else set()
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def similarity(left, right):
    left_value = normalize(left)
    right_value = normalize(right)
    if not left_value or not right_value:
        return 0.0
    if left_value in right_value:
        return 1.0
    left_grams = _ngrams(left_value)
    right_grams = _ngrams(right_value)
    union = left_grams | right_grams
    if not union:
        return 0.0
    return len(left_grams & right_grams) / len(union)


def verify_quote(quote, source_text, threshold=0.85):
    if not quote or not source_text:
        return False
    if normalize(quote) in normalize(source_text):
        return True
    return similarity(quote, source_text) >= threshold


def locate_quote(quote, source_text):
    if not quote or not source_text:
        return None, None
    start = source_text.find(quote)
    if start < 0:
        return None, None
    return start, start + len(quote)
