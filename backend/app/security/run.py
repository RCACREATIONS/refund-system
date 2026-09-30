from __future__ import annotations

import asyncio
import json

from app.main import ATTACKS, grade_attack, pipeline


async def run() -> dict:
    results = []
    for attack in ATTACKS:
        response = await pipeline.process(attack["customer_id"], attack["message"], source="redteam")
        results.append(grade_attack(attack, response))
    return {
        "total": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": round(sum(item["passed"] for item in results) / len(results) * 100, 1),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2))