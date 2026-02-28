
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.config import load_config
from agent.core import SessionManager, run_cycle, run_cycle_async
from agent.storage import load_current_profile, load_full_current_profile

_config = None
_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config, _manager
    _config = load_config()
    _manager = SessionManager(_config)
    yield

app = FastAPI(title="Riverse Agent API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = ""
    session_id: str | None = None
    input_type: str = "text"
    file_path: str | None = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    category: str
    intent: str

class SessionResponse(BaseModel):
    session_id: str
    created_at: str

class ProfileEntry(BaseModel):
    category: str
    field: str
    value: str

class HypothesisEntry(BaseModel):
    id: int
    category: str
    subject: str
    claim: str
    confidence: float
    status: str

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session = _manager.get_or_create(req.session_id)
    try:
        if req.input_type == "text" and not req.file_path:
            user_input = req.message
        else:
            user_input = {
                "type": req.input_type,
                "text": req.message,
                "file_path": req.file_path or "",
            }

        result = await run_cycle_async(user_input, session)
        return ChatResponse(
            response=result["response"],
            session_id=session.id,
            category=result["perception"].get("category", "chat"),
            intent=result["perception"].get("intent", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/new", response_model=SessionResponse)
async def new_session():
    session = _manager.get_or_create()
    return SessionResponse(
        session_id=session.id,
        created_at=session.created_at.isoformat(),
    )

@app.post("/sleep")
async def trigger_sleep():
    try:
        from agent.sleep import run as sleep_run
        sleep_run()
        from agent.config.prompts import get_labels
        L = get_labels("context.labels", _config.get("language", "zh"))
        return {"status": "ok", "message": L["memory_done"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile", response_model=list[ProfileEntry])
async def get_profile():
    profile = load_current_profile()
    return [
        ProfileEntry(category=p["category"], field=p["field"], value=p["value"])
        for p in profile
    ]

@app.get("/hypotheses", response_model=list[HypothesisEntry])
async def get_hypotheses():
    profile = load_full_current_profile()
    return [
        HypothesisEntry(
            id=p["id"], category=p["category"], subject=p["subject"],
            claim=p["value"], confidence=0.5, status=p.get("layer", "suspected"),
        )
        for p in profile
    ]

@app.get("/sessions")
async def list_sessions():
    return {"sessions": _manager.list_sessions()}

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    session = _manager.get_or_create()
    await websocket.send_json({
        "type": "session_created",
        "session_id": session.id,
    })

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            if not message:
                continue

            try:
                result = await run_cycle_async(message, session)
                await websocket.send_json({
                    "type": "response",
                    "response": result["response"],
                    "category": result["perception"].get("category", "chat"),
                    "intent": result["perception"].get("intent", ""),
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "detail": str(e),
                })
    except WebSocketDisconnect:
        pass
