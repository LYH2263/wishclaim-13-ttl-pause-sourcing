from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.engines.sourcing_pause import (
    pause_allowed, pause_payload, resume_allowed, resume_payload,
    fulfill_allowed, release_allowed,
)
from app.projections.wish import project_wish, project_wishes

app = FastAPI(title="Wishclaim", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    # Only claimed rows are swept; sourcing_paused rows are TTL-exempt by design.
    # Pause/resume run this sweep first, so a claim cannot be paused after it expired.
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
                      (rel["status"], None, None, None, r["id"]))

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = project_wishes(c.execute("SELECT * FROM wishes ORDER BY id DESC"), now()); c.close(); return rows

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "not found")
    return project_wish(r, now())

class WishIn(BaseModel):
    title: str
    note: str = ""

@app.post("/api/wishes")
def create_wish(body: WishIn):
    c = connect()
    cur = c.execute("INSERT INTO wishes(title,note,status,data_quality) VALUES (?,?,?,?)",
                    (body.title, body.note, "open", "clean"))
    c.commit(); wid = cur.lastrowid; c.close(); return {"id": wid}

class ClaimIn(BaseModel):
    claimer: str

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    p = lock_payload(body.claimer, now(), ttl())
    c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=?, paused_at=NULL WHERE id=?",
              (p["status"], p["claimer"], p["claimed_at"], p["expires_at"], wid))
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/release")
def release(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if not release_allowed(r["status"]):
        c.close(); raise HTTPException(400, "not_claimed")
    c.execute("UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL, paused_at=NULL WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "released"}

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = fulfill_allowed(r["status"])
    if not allowed["ok"]:
        c.close()
        code = 409 if allowed["reason"] == "sourcing_paused" else 400
        raise HTTPException(code, allowed["reason"])
    c.execute("UPDATE wishes SET status='fulfilled' WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "fulfilled"}

@app.post("/api/wishes/{wid}/pause")
def pause(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    d = pause_allowed(r["status"], r["claimer"], body.claimer)
    if not d["ok"]:
        c.close(); raise HTTPException(403 if d["reason"] == "not_claimer" else 409, d["reason"])
    p = pause_payload(now())
    cur = c.execute(
        "UPDATE wishes SET status=?, paused_at=? WHERE id=? AND status='claimed' AND claimer=?",
        (p["status"], p["paused_at"], wid, body.claimer))
    if cur.rowcount != 1:
        c.rollback(); c.close(); raise HTTPException(409, "state_changed")
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/resume")
def resume(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    d = resume_allowed(r["status"], r["claimer"], body.claimer, r["paused_at"], r["expires_at"])
    if not d["ok"]:
        c.close(); raise HTTPException(403 if d["reason"] == "not_claimer" else 409, d["reason"])
    p = resume_payload(now(), r["paused_at"], r["expires_at"])
    cur = c.execute(
        "UPDATE wishes SET status=?, expires_at=?, paused_at=NULL "
        "WHERE id=? AND status='sourcing_paused' AND claimer=? AND paused_at IS NOT NULL",
        (p["status"], p["expires_at"], wid, body.claimer))
    if cur.rowcount != 1:
        c.rollback(); c.close(); raise HTTPException(409, "state_changed")
    c.commit(); c.close(); return p

@app.get("/api/mine")
def mine(claimer: str):
    c = connect(); sweep(c); c.commit()
    rows = project_wishes(c.execute("SELECT * FROM wishes WHERE claimer=?", (claimer,)), now()); c.close(); return rows

@app.get("/api/done")
def done():
    c = connect()
    rows = project_wishes(c.execute("SELECT * FROM wishes WHERE status='fulfilled'"), now()); c.close(); return rows

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "fulfill": "核销后状态变为 fulfilled",
        "sourcing_pause": "认领人可暂停寻货：暂停期间剩余锁定时间冻结，不会被超时释放；仅认领人本人可暂停与恢复，恢复后按冻结的剩余时间继续倒计时；暂停中不可核销、不可转单。",
    }
