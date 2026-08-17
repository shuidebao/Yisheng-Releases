from __future__ import annotations

import asyncio
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import APP_NAME, COPYRIGHT, DEVELOPER, OFFICIAL_REPOSITORY, __version__
from .cache import TEMP_AUDIO_PREFIX, cache_status, clear_cache
from .config import LANGUAGES, ROOT
from .engine import InterpreterEngine
from .system_audio import SystemAudioError, SystemAudioManager
from .translation import TranslationUnavailable
from .updater import update_manager
from .whisper_models import model_status, models_status, start_model_download


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
STATIC_DIR = ROOT / "static"
MAX_AUDIO_BYTES = 24 * 1024 * 1024

engine = InterpreterEngine()
system_audio = SystemAudioManager()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        await asyncio.to_thread(system_audio.stop)


app = FastAPI(title="译声", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware("http")
async def prevent_stale_desktop_ui(request: Request, call_next):
    """Always load UI files from the installed version, not an older WebView cache."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path == "/overlay" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def prevent_stale_interface_assets(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


class EngineConfig(BaseModel):
    model: str = "base"
    device: str = "auto"


class SystemAudioConfig(BaseModel):
    device_index: int | None = None
    chunk_seconds: float = 3.6


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/api/status")
def status() -> dict:
    data = engine.status()
    data["languages"] = LANGUAGES
    data["version"] = __version__
    data["app_info"] = {
        "name": APP_NAME,
        "developer": DEVELOPER,
        "copyright": COPYRIGHT,
        "repository": OFFICIAL_REPOSITORY,
    }
    return data


@app.get("/api/cache/status")
async def get_cache_status() -> dict:
    return await asyncio.to_thread(cache_status)


@app.post("/api/cache/clear")
async def clear_app_cache() -> dict:
    return await asyncio.to_thread(clear_cache)


@app.get("/api/models/whisper/status")
async def whisper_models_status() -> dict:
    return await asyncio.to_thread(models_status)


@app.get("/api/models/whisper/{model}/status")
async def whisper_model_status(model: str) -> dict:
    try:
        return await asyncio.to_thread(model_status, model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/models/whisper/{model}/download")
async def download_whisper_model(model: str) -> dict:
    try:
        return await asyncio.to_thread(start_model_download, model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/update/check")
async def check_for_update() -> dict:
    return await asyncio.to_thread(update_manager.check)


@app.get("/api/update/status")
def update_status() -> dict:
    return update_manager.status()


@app.post("/api/update/download")
def download_update() -> dict:
    try:
        return update_manager.start_download()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/audio/system/devices")
def system_audio_devices() -> dict:
    try:
        return {"available": True, "devices": [item.to_dict() for item in system_audio.devices()]}
    except SystemAudioError as exc:
        return {"available": False, "devices": [], "error": str(exc)}


@app.get("/api/audio/system/status")
def system_audio_status() -> dict:
    return system_audio.status()


@app.post("/api/audio/system/start")
async def start_system_audio(config: SystemAudioConfig) -> dict:
    try:
        return await asyncio.to_thread(system_audio.start, config.device_index, config.chunk_seconds)
    except SystemAudioError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/audio/system/stop")
async def stop_system_audio() -> dict:
    return await asyncio.to_thread(system_audio.stop)


@app.get("/api/audio/system/chunk")
async def system_audio_chunk(timeout: float = Query(5.0, ge=0.05, le=10.0)) -> Response:
    try:
        chunk = await asyncio.to_thread(system_audio.get_chunk, timeout)
    except SystemAudioError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if chunk is None:
        return Response(status_code=204)
    return Response(
        content=chunk.wav,
        media_type="audio/wav",
        headers={
            "X-Audio-Duration": f"{chunk.duration:.3f}",
            "X-Audio-Level": f"{chunk.level:.3f}",
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/config")
def update_config(config: EngineConfig) -> dict:
    try:
        return engine.configure(config.model, config.device)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/models/translation/{source_code}")
async def install_translation_model(source_code: str) -> dict:
    if source_code not in LANGUAGES or source_code == "auto":
        raise HTTPException(status_code=400, detail="请先选择明确的原语言。")
    try:
        installed = await asyncio.to_thread(engine.translator.install_pair, source_code, "zh")
        return {"ok": True, "installed": installed, "pairs": engine.translator.installed_pairs()}
    except TranslationUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"内置模型检查失败：{exc}") from exc


@app.post("/api/transcribe")
async def transcribe(
    request: Request,
    language: str = Query("auto"),
    duration: float = Query(0.0, ge=0.0, le=3600.0),
    context: str = Query("", max_length=240),
) -> JSONResponse:
    if language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="不支持的语言。")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="没有收到音频。")
    if len(body) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="音频块过大。")

    suffix = ".wav" if "wav" in request.headers.get("content-type", "") else ".webm"
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, prefix=TEMP_AUDIO_PREFIX, suffix=suffix) as handle:
            handle.write(body)
            path = Path(handle.name)
        source = LANGUAGES[language]["whisper"] or None
        result = await asyncio.to_thread(engine.transcribe, path, source, duration, context)
        return JSONResponse(result.to_dict())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logging.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"转写失败：{exc}") from exc
    finally:
        if path:
            path.unlink(missing_ok=True)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/overlay")
def overlay() -> FileResponse:
    return FileResponse(STATIC_DIR / "overlay.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
