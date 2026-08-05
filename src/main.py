"""
Batch runner — Người 4.

Chạy toàn bộ 50 case input/EC_001.json .. EC_050.json qua Coordinator, ghi:
  - output/<case_id>.json cho từng case (dọn output cũ trước khi chạy)
  - logging/trace.jsonl — GHI ĐÈ (không append), mỗi dòng là 1 event của 1 agent
  - thống kê số case theo primary_issue, cảnh báo confidence thấp / verify lỗi

Chạy từ thư mục gốc repo:
    python -m src.main
    python -m src.main --no-llm   # chạy thuần deterministic, không gọi Groq

Cần GROQ_API_KEY trong .env (không commit) để bật LLM reasoning pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import io

# Fix Windows console encoding for Vietnamese
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from dotenv import load_dotenv

from src.agents import policy_agent
from src.coordinator import Coordinator

DATA_DIR = os.path.join(_ROOT_DIR, "data")
INPUT_DIR = os.path.join(_ROOT_DIR, "input")
OUTPUT_DIR = os.path.join(_ROOT_DIR, "output")
TRACE_PATH = os.path.join(_ROOT_DIR, "logging", "trace.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy batch 50 case E-commerce Dispute Resolution")
    parser.add_argument(
        "--no-llm", action="store_true", help="Tắt Coordinator LLM reasoning pass (chỉ deterministic)"
    )
    args = parser.parse_args()

    load_dotenv(os.path.join(_ROOT_DIR, ".env"))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(TRACE_PATH), exist_ok=True)

    # Dọn output cũ trước khi chạy để không còn file thừa lẫn vào zip nộp bài
    for fname in os.listdir(OUTPUT_DIR):
        if fname.endswith(".json"):
            os.remove(os.path.join(OUTPUT_DIR, fname))

    coordinator = Coordinator(DATA_DIR, use_llm=not args.no_llm)

    stats = {issue: 0 for issue in policy_agent.PRIMARY_ISSUES}
    low_confidence: list[str] = []
    failed_cases: list[tuple[str, list[str]]] = []
    total = 0

    with open(TRACE_PATH, "w", encoding="utf-8") as trace_f:  # ghi đè, không append trace cũ
        for i in range(1, 51):
            case_path = os.path.join(INPUT_DIR, f"EC_{i:03d}.json")
            if not os.path.exists(case_path):
                print(f"[WARN] Thiếu file input: {case_path}")
                continue

            result = coordinator.run_case(case_path)
            total += 1
            case_id = result["case_id"]
            output = result["output"]

            for event in result["trace_events"]:
                trace_f.write(json.dumps(event, ensure_ascii=False) + "\n")

            stats[output["assessment"]["primary_issue"]] += 1
            if output["assessment"]["confidence"] < 0.6:
                low_confidence.append(case_id)
            if not result["is_valid"]:
                failed_cases.append((case_id, result["errors"]))
                print(f"[FAIL-VERIFY] {case_id}: {result['errors']}")

            # Luôn ghi output cho đủ 50 file (kể cả khi verifier phát hiện lỗi) để
            # không thiếu file khi nộp; lỗi verify được nêu rõ trong trace + log console.
            out_path = os.path.join(OUTPUT_DIR, f"{case_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"Đã xử lý {total}/50 case. Output ghi vào {OUTPUT_DIR}")
    print("Thống kê primary_issue:")
    for issue, count in stats.items():
        print(f"  {issue:30s}: {count}")
    print(f"  {'TOTAL':30s}: {total}")

    if low_confidence:
        print(f"\nCẢNH BÁO case confidence < 0.6: {low_confidence}")
    if failed_cases:
        print(f"CẢNH BÁO verifier phát hiện lỗi ở {len(failed_cases)} case: {[c for c, _ in failed_cases]}")
    else:
        print("\nVerifier PASS toàn bộ 50 case.")

    missing_issues = [issue for issue, count in stats.items() if count == 0]
    if missing_issues:
        print(f"CẢNH BÁO thiếu primary_issue trong 50 case: {missing_issues}")
    else:
        print("Đủ cả 6 loại primary_issue trong 50 case.")


if __name__ == "__main__":
    main()
