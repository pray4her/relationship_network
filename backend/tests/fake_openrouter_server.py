import asyncio
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/api/v1/generation")
async def generation(id: str) -> JSONResponse:  # noqa: A002
    return JSONResponse(
        content={
            "data": {
                "id": id,
                "model": "test/success",
                "provider_name": "fake-zdr-provider",
                "tokens_prompt": 12,
                "tokens_completion": 4,
                "total_cost": 0.000012,
            }
        }
    )


@app.post("/api/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    payload = cast("dict[str, object]", await request.json())
    provider = cast("dict[str, object]", payload.get("provider", {}))
    response_format = cast("dict[str, object]", payload.get("response_format", {}))
    json_schema = cast("dict[str, object]", response_format.get("json_schema", {}))
    required_routing = {
        "data_collection": "deny",
        "require_parameters": True,
        "zdr": True,
    }
    if (
        payload.get("stream") is not False
        or "models" in payload
        or provider != required_routing
        or response_format.get("type") != "json_schema"
        or json_schema.get("strict") is not True
    ):
        return JSONResponse(status_code=400, content={"error": "required parameters missing"})

    model = str(payload.get("model", ""))
    if model == "test/rate-limited":
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": "1"},
            content={"error": "rate limited"},
        )
    if model == "test/invalid-structure":
        content = '{"capability":"not-ok"}'
    else:
        if model == "test/delayed-success":
            await asyncio.sleep(3)
        content = '{"capability":"ok"}'
    return JSONResponse(
        content={
            "choices": [{"message": {"content": content, "role": "assistant"}}],
            "id": "fake-openrouter-request",
            "model": model,
            "provider": "fake-zdr-provider",
        }
    )
