"""实验 5-11：对话式界面定制系统 —— FastAPI 后端。

一个最小的 chatbot 后端：前端把用户消息 POST 到 /api/chat，后端返回回复。
开发模式下用 `uvicorn main:app --reload` 启动，改动后端代码会自动 reload
（对应书中所说的"FastAPI 的热加载"）。

启动:  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Conversational UI Backend")

# 允许前端(Vite dev server, 5173)直接跨域访问，方便本地开发。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """极简回声式回复。

    本实验聚焦"对话式 UI 定制"，后端逻辑刻意保持最小；
    如需接入真实 LLM 对话，可在此处替换为对模型的调用。
    """
    reply = f"我收到了你的消息：{req.message}"
    return {"reply": reply}
