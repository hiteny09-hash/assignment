import hashlib
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

EMAIL = "24f1000846@ds.study.iitm.ac.in".strip().lower()
PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

TOOL = {
    "name": "solve_challenge",
    "description": "Returns the exam answer derived from the X-Exam-Challenge request header.",
    "inputSchema": {"type": "object", "properties": {}},
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)


def answer(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]


def handle(msg: dict, headers) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    if mid is None:  # notification (or stray response): no reply
        return None
    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        result: Any = {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "challenge-server", "version": "1.0.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        if name != TOOL["name"]:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        challenge = (headers.get("x-exam-challenge") or "").strip()
        if not challenge:
            result = {"content": [{"type": "text", "text": "missing X-Exam-Challenge header"}],
                      "isError": True}
        else:
            result = {"content": [{"type": "text", "text": answer(challenge)}]}
    else:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


@app.post("/")
@app.post("/mcp")
async def mcp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": "Parse error"}}, status_code=400)
    if isinstance(body, list):
        out = [r for r in (handle(m, request.headers) for m in body) if r is not None]
        return JSONResponse(out) if out else Response(status_code=202)
    resp = handle(body, request.headers)
    if resp is None:
        return Response(status_code=202)
    return JSONResponse(resp)


@app.get("/")
@app.get("/mcp")
async def not_allowed():
    return Response(status_code=405, headers={"Allow": "POST"})


@app.delete("/mcp")
async def end_session():
    return Response(status_code=200)
