"""HTTP API over the eligibility engine (FastAPI), consumed by the React frontend.

Endpoints:
  GET  /api/health            -> {"status": "ok"}
  GET  /api/meta              -> enums, lender list, sample profile ids (to build the form)
  GET  /api/profiles          -> the bundled P01-P16 sample inputs
  POST /api/evaluate          -> body = applicant fields; returns the full Decision + fixes

Run:  uvicorn eligibility.api:app --reload --port 8000
      (or: python -m eligibility.api)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .counterfactual import suggest
from .engine import Engine
from .schema import (ALLOWED_TENURES, Applicant, EmploymentType, Gender, LENDERS,
                     LENDER_TYPE, MaritalStatus, ResidenceType, Status)

app = FastAPI(title="Personal Loan Eligibility API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev; the Vite proxy also removes the need for this
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine: Optional[Engine] = None
PROFILES_DIR = Path(__file__).resolve().parents[2] / "tests" / "profiles"


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    """Everything the frontend needs to render the form and label results."""
    return {
        "lenders": [{"id": l, "type": LENDER_TYPE[l]} for l in LENDERS],
        "employment_types": [e.value for e in EmploymentType],
        "genders": [g.value for g in Gender],
        "residence_types": [r.value for r in ResidenceType],
        "marital_statuses": [m.value for m in MaritalStatus],
        "salary_account_options": ["none", *LENDERS],
        "tenures": list(ALLOWED_TENURES),
        "employer_categories": ["private", "govt", "psu", "mnc", "defence",
                                "private_ltd", "public_ltd", "corporate"],
    }


@app.get("/api/profiles")
def profiles() -> list[dict]:
    out = []
    for pf in sorted(PROFILES_DIR.glob("P*.json")):
        rec = json.loads(pf.read_text(encoding="utf-8"))
        out.append(rec)
    return out


@app.get("/api/summary")
def summary() -> dict:
    from .quality import model_summary
    return model_summary(engine().store)


@app.get("/api/completeness")
def completeness() -> list[dict]:
    """Per-product rule completeness (complete / partial / insufficient) with group status."""
    from .quality import product_completeness
    return product_completeness(engine().store)


def _decision_payload(app_model: Applicant) -> dict:
    eng = engine()
    d = eng.run(app_model)
    payload = d.model_dump(mode="json")
    # attach counterfactual fixes to each non-eligible offer
    for offer_obj, offer_json in zip(d.offers, payload["offers"]):
        if not offer_obj.status.is_offer:
            offer_json["fixes"] = [f.model_dump() for f in suggest(eng, app_model, offer_obj)]
        else:
            offer_json["fixes"] = []
    return payload


@app.post("/api/evaluate")
def evaluate(body: dict[str, Any]) -> dict:
    body = dict(body)
    body.pop("profile_id", None)
    body.pop("description", None)
    # drop empty-string / None optionals so Pydantic defaults apply
    cleaned = {k: v for k, v in body.items() if v not in ("", None)}
    try:
        applicant = Applicant(**cleaned)
    except ValidationError as exc:
        detail = [{"loc": list(e.get("loc", [])), "msg": str(e.get("msg", "")),
                   "type": e.get("type", "")} for e in exc.errors()]
        raise HTTPException(status_code=422, detail=detail)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _decision_payload(applicant)


def main() -> None:
    import uvicorn
    uvicorn.run("eligibility.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
