"""
FastAPI Application Entry Point
Luna: Autonomous Multi-MCP Agent Operations Platform
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.api.agents import router as agents_router
from app.api.executions import router as executions_router
from app.api.knowledge import router as knowledge_router
from app.api.mcp import router as mcp_router
from app.api.system import router as system_router
from app.api.memory import router as memory_router
from app.api.auth import router as auth_router
from app.seed_data import seed_database

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database, external fixtures, and vector store are ready
    seed_database()
    yield


app = FastAPI(
    title="Luna",
    description="""
Autonomous agent operations platform coordinating multiple Model Context Protocol (MCP) servers,
LlamaIndex Workflows, dynamic agent-level permissions, FAISS vector search, and dual-tier memory.
    """,
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for open API usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include API Routers
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(executions_router)
app.include_router(knowledge_router)
app.include_router(mcp_router)
app.include_router(memory_router)

# Mount individual MCP Server SSE Endpoints for MCP Inspector and external clients
from app.mcp.servers.crm_server import mcp_server as crm_mcp_server
from app.mcp.servers.analytics_server import mcp_server as analytics_mcp_server
from app.mcp.servers.operations_server import mcp_server as operations_mcp_server

if crm_mcp_server:
    app.mount("/mcp/crm", crm_mcp_server.sse_app())
if analytics_mcp_server:
    app.mount("/mcp/analytics", analytics_mcp_server.sse_app())
if operations_mcp_server:
    app.mount("/mcp/operations", operations_mcp_server.sse_app())


from app.api.auth import router as auth_router, register as auth_register, login as auth_login


@app.get("/", include_in_schema=False)
@app.get("/chat", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/signin", include_in_schema=False)
@app.get("/register", include_in_schema=False)
@app.get("/signup", include_in_schema=False)
@app.get("/demo", include_in_schema=False)
@app.get("/auth", include_in_schema=False)
def serve_dashboard():
    """Serve the focused chatbot UI."""
    return FileResponse(STATIC_DIR / "chat.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


# Root-level convenience aliases for POST /register and POST /login
app.add_api_route("/register", auth_register, methods=["POST"], include_in_schema=False, status_code=201)
app.add_api_route("/login", auth_login, methods=["POST"], include_in_schema=False)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Luna",
        "version": "2.0.0"
    }


@app.get("/404", include_in_schema=False)
def serve_404_page():
    """Explicitly serve the 404 error page."""
    return FileResponse(
        STATIC_DIR / "404.html",
        status_code=404,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


@app.exception_handler(404)
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle 404s and HTTP errors across the application:
    - Browser/page navigations (Accept: text/html or non-API routes) receive the customized 404 HTML page.
    - API endpoints (or clients requesting JSON) receive standard JSON error payloads.
    """
    if exc.status_code == 404:
        accept = request.headers.get("accept", "")
        is_api_route = any(request.url.path.startswith(prefix) for prefix in [
            "/agents", "/executions", "/knowledge", "/mcp", "/system", "/memory", "/auth"
        ])

        if "text/html" in accept or (not is_api_route and "application/json" not in accept):
            return FileResponse(
                STATIC_DIR / "404.html",
                status_code=404,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )

        return JSONResponse(status_code=404, content={"detail": exc.detail or "Not Found"})

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
