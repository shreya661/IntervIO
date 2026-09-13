import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.api.interviews import router as interview_router
except ImportError:
    from api.interviews import router as interview_router


app = FastAPI(
    title="InterviewOne AI",
    description="Autonomous Adaptive Interview Assessment System",
    version="1.0.0"
)


# Allow the Next.js frontend to communicate with FastAPI (configurable for deployment)
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_env_origins = os.getenv("CORS_ORIGINS")
if _env_origins:
    cors_origins = [orig.strip() for orig in _env_origins.split(",") if orig.strip()]
else:
    cors_origins = _default_origins

cors_regex = os.getenv("CORS_ORIGIN_REGEX", r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$")

if "*" in cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=cors_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )



# Interview API
app.include_router(interview_router)


@app.get("/")
def root():
    return {
        "service": "InterviewOne AI Backend",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "InterviewOne AI Backend"
    }