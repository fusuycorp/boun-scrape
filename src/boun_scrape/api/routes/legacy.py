import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from boun_scrape.config import Settings
from boun_scrape.storage.repository import CourseRepository
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.domain.dto import CourseFilterParams
from boun_scrape.scraper.quota import QuotaService
from boun_scrape.scheduler.runner import ScrapeScheduler
from boun_scrape.api.deps import (
    get_settings_dep,
    get_repository,
    get_db_manager,
    get_quota_service,
    get_scheduler,
    get_log_buffer,
    LogBuffer,
)
from boun_scrape.api.auth import (
    create_jwt_token,
    verify_password,
    get_current_user,
)
from boun_scrape.api.rate_limit import login_rate_limit_dep

router = APIRouter(tags=["legacy-compat"])

class Token(BaseModel):
    access_token: str
    token_type: str

class UserInfo(BaseModel):
    username: str

class ScraperConfigUpdate(BaseModel):
    cookies: Optional[str] = None
    response_html: Optional[str] = None

@router.post("/auth/login", response_model=Token, dependencies=[Depends(login_rate_limit_dep)])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    settings: Settings = Depends(get_settings_dep),
):
    input_user = (form_data.username or "").strip()
    input_pwd = (form_data.password or "").strip()
    
    if input_user.lower() != settings.admin_user.lower() or not verify_password(input_pwd, settings.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_jwt_token({"sub": settings.admin_user}, settings.jwt_secret_key)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UserInfo)
async def get_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}

@router.get("/stats")
async def get_stats(
    repo: CourseRepository = Depends(get_repository),
    current_user: str = Depends(get_current_user),
):
    terms = repo.get_terms()
    depts = repo.get_departments()
    latest_run = repo.get_latest_run()
    
    # Get total courses across DB
    with repo.db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM courses")
        total_courses = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM course_slots")
        total_slots = cursor.fetchone()[0]
    
    return {
        "total_courses": total_courses,
        "total_slots": total_slots,
        "departments": len(depts),
        "terms": len(terms),
        "last_scraped": latest_run.completed_at.isoformat() if latest_run and latest_run.completed_at else None,
    }

@router.get("/terms", response_model=List[str])
async def get_terms(
    repo: CourseRepository = Depends(get_repository),
    current_user: str = Depends(get_current_user),
):
    return repo.get_terms()

@router.get("/departments", response_model=List[str])
async def get_departments(
    repo: CourseRepository = Depends(get_repository),
    current_user: str = Depends(get_current_user),
):
    depts = repo.get_departments()
    return sorted(list({d.code for d in depts}))

@router.get("/departments/all")
async def get_all_departments(
    repo: CourseRepository = Depends(get_repository),
    current_user: str = Depends(get_current_user),
):
    depts = repo.get_departments()
    if depts:
        return [{"kisaadi": d.code, "bolum": d.name} for d in depts]
    return []

@router.get("/courses")
async def get_courses(
    term: Optional[str] = None,
    department: Optional[str] = None,
    course_code: Optional[str] = None,
    instructor: Optional[str] = None,
    day: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    repo: CourseRepository = Depends(get_repository),
    current_user: str = Depends(get_current_user),
):
    filter_params = CourseFilterParams(
        term=term,
        department=department,
        course_code=course_code,
        instructor=instructor,
        day=day,
        keyword=search,
        page=page,
        size=limit,
    )
    courses, total = repo.get_courses(filter_params)
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "courses": [
            {
                "id": c.id,
                "term": c.term,
                "department": c.department,
                "course_code": c.course_code,
                "section": c.section,
                "course_name": c.course_name,
                "instructor": c.instructor,
                "credits": str(c.credits) if c.credits is not None else "",
                "ects": str(c.ects) if c.ects is not None else "",
                "delivery_method": c.delivery_method,
                "exam_location": c.exam_location,
                "exam_date": c.exam_date,
                "sl": c.sl,
                "required_for": c.required_for,
                "departments": c.departments,
                "slots": [
                    {
                        "id": s.id,
                        "day": s.day,
                        "hour": s.hour,
                        "room": s.room,
                        "slot_title": s.slot_title,
                        "instructor": s.instructor,
                    }
                    for s in c.slots
                ],
            }
            for c in courses
        ],
    }

@router.get("/config")
async def get_config(
    settings: Settings = Depends(get_settings_dep),
    current_user: str = Depends(get_current_user),
):
    has_cookies = os.path.exists(settings.cookies_path) and os.path.getsize(settings.cookies_path) > 0
    return {
        "has_cookies": has_cookies,
        "cookies_path": settings.cookies_path,
        "has_response_html": True,
        "db_path": settings.db_path,
    }

@router.post("/config")
async def update_config(
    data: ScraperConfigUpdate,
    settings: Settings = Depends(get_settings_dep),
    current_user: str = Depends(get_current_user),
):
    if data.cookies is not None:
        with open(settings.cookies_path, "w", encoding="utf-8") as f:
            f.write(data.cookies)
    return {"status": "ok", "message": "Configuration updated successfully"}

@router.post("/scrape/start")
async def start_scrape(
    scheduler: ScrapeScheduler = Depends(get_scheduler),
    current_user: str = Depends(get_current_user),
):
    scheduler.run_in_background(scheduler.execute_scrape_cycle())
    return {"status": "ok", "message": "Scraping cycle initiated in background"}

@router.post("/scrape/stop")
async def stop_scrape(
    scheduler: ScrapeScheduler = Depends(get_scheduler),
    current_user: str = Depends(get_current_user),
):
    await scheduler.stop()
    return {"status": "ok", "message": "Scraper stopped"}

@router.get("/scrape/status")
async def get_scrape_status(
    scheduler: ScrapeScheduler = Depends(get_scheduler),
    current_user: str = Depends(get_current_user),
):
    status_info = scheduler.get_status()
    is_scraping = status_info.get("is_scraping", False)
    progress = status_info.get("current_progress")

    if progress and progress.get("total"):
        current, total = progress["completed"], progress["total"]
        percent = round((current / total) * 100, 1)
    else:
        current, total = (0, 100) if is_scraping else (100, 100)
        percent = 0.0 if is_scraping else 100.0

    return {
        "phase": "scraping" if is_scraping else None,
        "status": "running" if is_scraping else "idle",
        "progress": {
            "total": total,
            "current": current,
            "percent": percent,
        },
    }

@router.get("/scrape/terms")
async def get_scrape_terms(
    repo: CourseRepository = Depends(get_repository),
    current_user: str = Depends(get_current_user),
):
    return repo.get_terms()

@router.get("/scrape/logs")
async def get_scrape_logs(
    clear: bool = False,
    log_buffer: LogBuffer = Depends(get_log_buffer),
    current_user: str = Depends(get_current_user),
):
    logs = log_buffer.get_logs()
    if clear:
        log_buffer.clear()
    return [f"[{r.timestamp.strftime('%H:%M:%S')}] [{r.level}] {r.message}\n" for r in logs]

@router.get("/quota/check")
async def check_quota(
    abbr: str,
    code: str,
    section: str,
    donem: str,
    quota_service: QuotaService = Depends(get_quota_service),
    current_user: str = Depends(get_current_user),
):
    records = await quota_service.fetch_quota(donem, abbr, code, section)
    return [
        {
            "department": r.department,
            "status": r.status.value,
            "quota": str(r.total_quota) if r.total_quota is not None else ("Unlimited" if r.is_unlimited else "Consent"),
            "current": str(r.enrolled),
            "available": str(r.available) if r.available is not None else "0",
        }
        for r in records
    ]
