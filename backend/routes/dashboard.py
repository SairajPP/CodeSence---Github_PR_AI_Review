from fastapi import APIRouter
from qdrant_client.models import Filter, FieldCondition, MatchValue
from services.memory import client, COLLECTION_NAME
import os

router = APIRouter()

@router.get("/findings")
def get_all_findings():
    """Get all findings across all repos for the dashboard."""
    try:
        # Check if collection exists
        if not client.collection_exists(COLLECTION_NAME):
             return {"findings": []}
             
        # Use scroll to get all points (up to 1000 for dashboard demo)
        records, next_page = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        findings = []
        for record in records:
            if record.payload:
                findings.append(record.payload)
                
        return {"findings": findings}
    except Exception as e:
        return {"error": str(e), "findings": []}

@router.get("/repos")
def get_repos():
    """Get unique repository names."""
    try:
        if not client.collection_exists(COLLECTION_NAME):
             return {"repos": []}
             
        records, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        repos = set()
        for record in records:
            if record.payload and "repo" in record.payload:
                repos.add(record.payload["repo"])
                
        return {"repos": list(repos)}
    except Exception as e:
        return {"error": str(e), "repos": []}
