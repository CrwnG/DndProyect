"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.middleware.error_handler import setup_error_handlers
import traceback

# ============================================================================
# IMPORTANT: If you see this banner, the server has been restarted!
# ============================================================================
from datetime import datetime
startup_time = datetime.now().strftime("%H:%M:%S")
print("\n" + "="*70, flush=True)
print(f"  D&D COMBAT ENGINE - STARTED AT {startup_time}", flush=True)
print("  [OK] DEBUG MODE - Error details will show in responses", flush=True)
print("  [OK] Structured error handling enabled", flush=True)
print("="*70 + "\n", flush=True)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events - startup and shutdown."""
    # Startup: Initialize database
    from app.database.engine import init_db
    await init_db()
    print("[Startup] Database initialized")

    yield  # Application runs here

    # Shutdown: Close database connections
    from app.database.engine import close_db
    await close_db()
    print("[Shutdown] Database connections closed")


app = FastAPI(
    title="D&D Combat Engine",
    description="A BG3-inspired tactical D&D web game with AI Dungeon Master",
    version="0.1.0",
    lifespan=lifespan,
)


# Middleware to log ALL requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQUEST] {request.method} {request.url.path}", flush=True)
    try:
        response = await call_next(request)
        print(f"[RESPONSE] {request.method} {request.url.path} -> {response.status_code}", flush=True)
        return response
    except Exception as e:
        print(f"[REQUEST ERROR] {request.method} {request.url.path} -> {type(e).__name__}: {e}", flush=True)
        raise

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",  # Live Server
        "http://127.0.0.1:5500",
        "http://localhost:8080",  # Python http.server
        "http://127.0.0.1:8080",
        "http://localhost:5173",  # Vite / Python http.server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Setup structured error handlers (replaces the old global exception handler)
setup_error_handlers(app, debug=settings.DEBUG)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "online", "game": "D&D Combat Engine", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    print("[HEALTH] Health check endpoint called!", flush=True)
    return {
        "status": "healthy",
        "api_key_configured": bool(settings.ANTHROPIC_API_KEY),
        "debug_mode": settings.DEBUG
    }


@app.get("/api/health")
async def api_health_check():
    """Health check at /api/health for frontend compatibility."""
    print("[API_HEALTH] /api/health endpoint called!", flush=True)
    return await health_check()


# Routes
from app.api.routes import combat, character, campaign, spells, equipment, character_creation, loot, class_features, skill_checks, progression, dm, shop, map_generation, social, random_encounters, export, campaign_generator, multiplayer, auth, campaign_editor
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(combat.router, prefix="/api/combat", tags=["combat"])
app.include_router(character.router, prefix="/api/character", tags=["character"])
app.include_router(campaign.router, prefix="/api/campaign", tags=["campaign"])
app.include_router(campaign_generator.router, prefix="/api/campaign-generator", tags=["campaign-generator"])
app.include_router(spells.router, prefix="/api/spells", tags=["spells"])
app.include_router(equipment.router, prefix="/api", tags=["equipment"])
app.include_router(character_creation.router, prefix="/api/creation", tags=["character-creation"])
app.include_router(loot.router, prefix="/api", tags=["loot"])
app.include_router(class_features.router, prefix="/api/class-features", tags=["class-features"])
app.include_router(skill_checks.router, prefix="/api/skill-check", tags=["skill-checks"])
app.include_router(progression.router, prefix="/api/progression", tags=["progression"])
app.include_router(dm.router, prefix="/api/dm", tags=["dm"])
app.include_router(shop.router, prefix="/api", tags=["shop"])
app.include_router(map_generation.router, prefix="/api", tags=["map_generation"])
app.include_router(social.router, prefix="/api/social", tags=["social"])
app.include_router(random_encounters.router, prefix="/api/encounters", tags=["encounters"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(multiplayer.router, prefix="/api/multiplayer", tags=["multiplayer"])
app.include_router(campaign_editor.router, tags=["campaign-editor"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
