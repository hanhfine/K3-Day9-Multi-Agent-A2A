"""
Client gọi Groq API cho tất cả các agent trong pipeline.

Model: llama-3.1-8b-instant (~8B parameters, tuân thủ giới hạn <=10B của đề bài).
Mỗi agent gọi model này để đưa ra phần "reasoning" (diễn giải bằng ngôn ngữ tự
nhiên + xác nhận lại phán đoán) dựa trên dữ liệu đã trích xuất chính xác từ CSV.

Thiết kế an toàn: các con số/boolean quyết định cuối cùng luôn được tính toán
xác định (deterministic) trong code Python của từng agent trước khi gọi LLM.
LLM không được dùng để tự tính tổng tiền hay tự suy ra ngày tháng — chỉ dùng để
xác nhận lại phán đoán nghiệp vụ và sinh lời giải thích, giữ đúng tinh thần
"multi-agent" (mỗi agent có model riêng, có handoff) đồng thời đảm bảo độ chính
xác tuyệt đối cho phần chấm điểm (JSON schema, evidence, financial resolution).
Nếu LLM trả lệch so với dữ liệu xác định, Verifier Agent sẽ ghi đè bằng giá trị
xác định và log lại discrepancy vào trace — không bao giờ để LLM tự bịa sự kiện
ngoài CSV.
"""
from __future__ import annotations

import json
import os
import time

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.1-8b-instant"  # 8B parameters


class LLMError(Exception):
    pass


def call_agent_llm(
    system_prompt: str,
    user_prompt: str,
    api_key: str | None = None,
    max_retries: int = 3,
    temperature: float = 0.0,
    timeout: int = 30,
) -> dict:
    """Gọi Groq chat completion, ép trả về JSON object. Raise LLMError nếu thất bại."""
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LLMError("Thiếu GROQ_API_KEY (đặt trong .env, không commit).")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001 - muốn bắt mọi lỗi để retry/fallback
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"Groq call thất bại sau {max_retries} lần thử: {last_err}")
