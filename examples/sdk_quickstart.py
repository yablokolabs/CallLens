"""CallLens SDK quickstart.

Requires the API running locally: `calllens server` (or `docker compose up`).
"""

import asyncio

from calllens import CallLens


async def main() -> None:
    async with CallLens(base_url="http://localhost:8000") as client:
        # 1. Upload a recording (or .json/.txt transcript)
        call = await client.calls.upload("sales-call.mp3", filename="sales-call.mp3")

        # 2. Kick off analysis against a rubric
        await call.analyze(rubric="consultative_sales")

        # 3. Fetch the evidence-backed report
        report = await call.report()
        print(f"overall: {report['overall_score']:.1f}/100  confidence: {report['confidence']:.2f}")
        for score in report["rubric_scores"]:
            r = score["result"]
            n_evidence = len(r["positive_evidence"]) + len(r["negative_evidence"])
            print(f"  {score['label']:>24}: {r['score']:>4.1f}/10  ({n_evidence} evidence items)")

        # 4. Clean up (privacy by default)
        await call.delete()


if __name__ == "__main__":
    asyncio.run(main())
