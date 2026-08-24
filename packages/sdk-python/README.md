# calllens-sdk

Thin distribution for the CallLens Python SDK. The implementation lives in
the core package (`calllens.sdk`), so the SDK always matches the engine it
talks to. This package exists so teams can install just the client:

```bash
pip install calllens-sdk   # (publishing planned; for now install the monorepo core)
```

```python
import asyncio
from calllens import CallLens


async def main():
    async with CallLens(base_url="http://localhost:8000") as client:
        call = await client.calls.upload("call.mp3")
        await call.analyze(rubric="consultative_sales")
        report = await call.report()
        print(report["overall_score"])


asyncio.run(main())
```

See `examples/` in the repository root for a full example.
