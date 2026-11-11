import hashlib
import json
import time
import urllib.error
import urllib.request

from flask import current_app

from app.ai.prompts import build_messages


class AIProviderError(RuntimeError):
    status_code = 502


class AIConfigError(AIProviderError):
    status_code = 503


def _parse_json(text):
    value = (text or "").strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        value = value[start : end + 1]
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"AI 返回内容不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise AIProviderError("AI 返回内容不是 JSON 对象")
    return data


class AIProvider:
    """DeepSeek V4.1 Flash 统一入口；失败重试一次，不做本地回退。"""

    def __init__(self, api_key=None, model=None):
        self.api_key = (
            current_app.config["AI_API_KEY"] if api_key is None else api_key
        )
        self.model = current_app.config["AI_MODEL"] if model is None else model

    def run(self, step, payload=None, messages=None, prompt_version="v1"):
        payload = payload or {}
        if not self.api_key:
            raise AIConfigError(
                "未配置 AI_API_KEY。请在 backend/.env 中填写 DeepSeek API Key。"
            )

        started = time.time()
        input_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        json_mode = step != "chat"
        request_messages = messages or build_messages(step, payload)

        last_error = None
        for attempt in range(2):
            try:
                text, tokens = self._remote(
                    step, request_messages, json_mode=json_mode
                )
                result = {"text": text} if step == "chat" else _parse_json(text)
                return self._envelope(
                    result,
                    started,
                    input_hash,
                    prompt_version,
                    tokens,
                )
            except AIProviderError as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.3)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.3)
            except Exception as exc:  # noqa: BLE001 - retry once, then surface
                last_error = exc
                if attempt == 0:
                    time.sleep(0.3)

        if isinstance(last_error, AIProviderError):
            raise last_error
        raise AIProviderError(f"AI 调用失败：{last_error}") from last_error

    def _envelope(self, result, started, input_hash, prompt_version, tokens):
        return {
            "result": result,
            "text": result.get("text", "") if isinstance(result, dict) else "",
            "model": self.model,
            "tokens": tokens,
            "duration_ms": int((time.time() - started) * 1000),
            "input_hash": input_hash,
            "prompt_version": prompt_version,
        }

    def _remote(self, step, messages, json_mode=False):
        base = current_app.config["AI_BASE_URL"].rstrip("/")
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=current_app.config["AI_TIMEOUT"]
        ) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = data["choices"][0]["message"]["content"]
        tokens = int(data.get("usage", {}).get("total_tokens", 0))
        return text, tokens
