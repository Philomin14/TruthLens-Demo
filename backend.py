from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3

from factcheck_db_sim import (
    create_db,
    add_claim,
    add_result,
    add_source,
    get_claim_summary
)

app = FastAPI(title="UK Fact-Checking Backend")

DB_PATH = "factcheck.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class Claim(BaseModel):
    text: str
    category: Optional[str] = "general"

class Entities(BaseModel):
    entities: List[str]

class Validity(BaseModel):
    validity: str

class SourceIn(BaseModel):
    result_id: int
    url: str
    title: str

class ResultIn(BaseModel):
    claim_id: int
    validity_score: float
    summary: str


@app.on_event("startup")
def startup():
    create_db(DB_PATH)


# Create a claim
@app.post("/claims")
def submit_claim(claim: Claim, conn=Depends(get_db)):
    user_id = 1  # eplace with auth later

    claim_id = add_claim(conn, user_id, claim.text)

    return {
        "claim_id": claim_id,
        "text": claim.text,
        "category": claim.category
    }


# Get full claim 
@app.get("/claims/{claim_id}")
def get_claim_full(claim_id: int, conn=Depends(get_db)):
    summary = get_claim_summary(conn, claim_id)

    if not summary or not summary["claim"]:
        raise HTTPException(status_code=404, detail="Claim not found")

    return summary


# extract entities 
@app.get("/claims/{claim_id}/entities", response_model=Entities)
def extract_entities(claim_id: int, conn=Depends(get_db)):
    summary = get_claim_summary(conn, claim_id)

    if not summary or not summary["claim"]:
        return {"entities": []}

    entities = [e["name"] for e in summary["entities"]]
    return {"entities": entities}


# Get validity score
@app.get("/claims/{claim_id}/validity", response_model=Validity)
def check_validity(claim_id: int, conn=Depends(get_db)):
    summary = get_claim_summary(conn, claim_id)

    if not summary or not summary["result"]:
        return {"validity": "No result yet"}

    score = summary["result"]["validity_score"]

    if score >= 0.7:
        verdict = "Likely True"
    elif score <= 0.3:
        verdict = "Likely False"
    else:
        verdict = "Unverified"

    return {"validity": verdict}


# Add a fact-check result
@app.post("/results")
def create_result(result: ResultIn, conn=Depends(get_db)):
    try:
        result_id = add_result(
            conn,
            result.claim_id,
            result.validity_score,
            result.summary
        )
        return {"result_id": result_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Add a source to a result
@app.post("/sources")
def create_source(source: SourceIn, conn=Depends(get_db)):
    try:
        source_id = add_source(
            conn,
            source.result_id,
            source.url,
            source.title
        )
        return {"source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
