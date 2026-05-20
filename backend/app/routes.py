import os
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.auth import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD_HASH,
    verify_password,
    create_access_token,
    get_current_user
)
from app.database import (
    get_db_stats,
    get_unique_terms,
    get_unique_departments,
    query_courses
)
from app.scraping import scraper_manager
from app.quota import fetch_quota_from_boun

router = APIRouter()

# --- AUTH MODELS & ENDPOINTS ---

class Token(BaseModel):
    access_token: str
    token_type: str

class UserInfo(BaseModel):
    username: str

@router.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UserInfo)
async def get_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}


# --- DATABASE STATS & DATA LOOKUPS ---

@router.get("/stats")
async def get_stats(current_user: str = Depends(get_current_user)):
    return get_db_stats()

@router.get("/terms", response_model=List[str])
async def get_terms(current_user: str = Depends(get_current_user)):
    return get_unique_terms()

@router.get("/departments", response_model=List[str])
async def get_departments(current_user: str = Depends(get_current_user)):
    return get_unique_departments()

@router.get("/courses")
async def get_courses(
    current_user: str = Depends(get_current_user),
    term: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200)
):
    courses, total = query_courses(
        term=term,
        department=department,
        search=search,
        day=day,
        page=page,
        limit=limit
    )
    return {
        "courses": courses,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


# --- CONFIGURATION MANAGEMENT ---

class ConfigUpdate(BaseModel):
    cookies: Optional[str] = None
    seed_html: Optional[str] = None

@router.get("/config")
async def get_config(current_user: str = Depends(get_current_user)):
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cookie_path = os.path.join(backend_dir, "cookies.txt")
    seed_path = os.path.join(backend_dir, "response.html")
    
    cookie_loaded = os.path.exists(cookie_path)
    cookie_masked = ""
    if cookie_loaded:
        try:
            with open(cookie_path, "r") as f:
                content = f.read().strip()
                if len(content) > 15:
                    cookie_masked = content[:15] + "..."
                else:
                    cookie_masked = content
        except Exception:
            cookie_masked = "Error reading cookies.txt"
            
    seed_loaded = os.path.exists(seed_path)
    seed_size = 0
    if seed_loaded:
        try:
            seed_size = os.path.getsize(seed_path)
        except Exception:
            pass
            
    return {
        "cookie_loaded": cookie_loaded,
        "cookie_masked": cookie_masked,
        "seed_html_loaded": seed_loaded,
        "seed_html_size": seed_size
    }

@router.post("/config")
async def update_config(config: ConfigUpdate, current_user: str = Depends(get_current_user)):
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cookie_path = os.path.join(backend_dir, "cookies.txt")
    seed_path = os.path.join(backend_dir, "response.html")
    
    response_msg = []
    
    if config.cookies is not None:
        try:
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(config.cookies.strip())
            response_msg.append("cookies.txt successfully updated.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save cookies.txt: {e}")
            
    if config.seed_html is not None:
        try:
            with open(seed_path, "w", encoding="utf-8") as f:
                f.write(config.seed_html)
            response_msg.append("response.html successfully updated.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save response.html: {e}")
            
    if not response_msg:
        return {"message": "No configuration parameters provided."}
        
    return {"message": " & ".join(response_msg)}


# --- BACKGROUND SCRAPING TRIGGER CONTROLS ---

class ScrapeStartRequest(BaseModel):
    phase: str  # "phase1", "phase2", "phase3", "phase4"
    force_refresh: bool = False

@router.post("/scrape/start")
async def start_scraping(req: ScrapeStartRequest, current_user: str = Depends(get_current_user)):
    if req.phase not in ["phase1", "phase2", "phase3", "phase4"]:
        raise HTTPException(status_code=400, detail="Invalid phase specified. Must be phase1, phase2, phase3, or phase4.")
        
    # Check if a process is already running
    status_info = scraper_manager.get_status()
    if status_info["status"] == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A scraping task (Phase {status_info['phase'].upper()}) is already running. Stop it or wait for it to complete."
        )
        
    success = scraper_manager.start_phase(req.phase, force_refresh=req.force_refresh)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to start Phase {req.phase.upper()}. Check server logs.")
        
    return {"message": f"Successfully launched Phase {req.phase.upper()} in background."}

@router.post("/scrape/stop")
async def stop_scraping(current_user: str = Depends(get_current_user)):
    success = scraper_manager.stop_scraping()
    if not success:
        return {"message": "No active scraping process to terminate."}
    return {"message": "Scraping process successfully terminated."}

@router.get("/scrape/status")
async def get_scrape_status(current_user: str = Depends(get_current_user)):
    return scraper_manager.get_status()

@router.get("/scrape/terms")
async def get_scrape_terms(current_user: str = Depends(get_current_user)):
    """List every term seen on disk with last-scraped timestamps.

    Sources timestamps from file mtimes:
      - phase1_at  -> mtime of responses/<safe_term>.html
      - phase3_at  -> max mtime across schedules/<safe_term>/*.html
    Both are unix seconds (float) or None when missing.
    """
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    responses_dir = os.path.join(backend_dir, "responses")
    schedules_root = os.path.join(backend_dir, "schedules")

    terms: Dict[str, Dict[str, Any]] = {}

    if os.path.isdir(responses_dir):
        for fname in os.listdir(responses_dir):
            if not fname.endswith(".html"):
                continue
            safe_term = fname[:-5]
            term = safe_term.replace("_", "/")
            try:
                mtime = os.path.getmtime(os.path.join(responses_dir, fname))
            except OSError:
                mtime = None
            terms.setdefault(term, {"term": term, "phase1_at": None, "phase3_at": None, "schedule_count": 0})
            terms[term]["phase1_at"] = mtime

    if os.path.isdir(schedules_root):
        for safe_term in os.listdir(schedules_root):
            term_dir = os.path.join(schedules_root, safe_term)
            if not os.path.isdir(term_dir):
                continue
            term = safe_term.replace("_", "/")
            latest = None
            count = 0
            for fname in os.listdir(term_dir):
                if not fname.endswith(".html"):
                    continue
                count += 1
                try:
                    m = os.path.getmtime(os.path.join(term_dir, fname))
                except OSError:
                    continue
                if latest is None or m > latest:
                    latest = m
            terms.setdefault(term, {"term": term, "phase1_at": None, "phase3_at": None, "schedule_count": 0})
            terms[term]["phase3_at"] = latest
            terms[term]["schedule_count"] = count

    # Sort newest-term first by string compare (terms look like 2024/2025-1)
    return {"terms": sorted(terms.values(), key=lambda t: t["term"], reverse=True)}


@router.get("/scrape/logs")
async def get_scrape_logs(
    current_user: str = Depends(get_current_user),
    limit: int = Query(500, ge=1, le=2000),
    clear: bool = Query(False)
):
    if clear:
        scraper_manager.clear_logs()
        return {"message": "Scraper logs cleared."}
    return {"logs": scraper_manager.get_logs(limit)}


# --- CORS-FREE QUOTA SEARCH ENDPOINT ---

@router.get("/quota/check")
async def check_quota(
    current_user: str = Depends(get_current_user),
    abbr: str = Query(..., min_length=1),
    code: str = Query(..., min_length=1),
    section: str = Query(..., min_length=1),
    donem: str = Query(..., min_length=1)
):
    res = fetch_quota_from_boun(abbr=abbr, code=code, section=section, donem=donem)
    if not res["success"]:
        # We don't crash, we just return the failure reason so frontend can show helpful warning
        return res
    return res
