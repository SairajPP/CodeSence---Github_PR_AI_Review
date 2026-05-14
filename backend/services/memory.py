import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from langchain_huggingface import HuggingFaceEmbeddings
import uuid
import logging

logger = logging.getLogger(__name__)

# Initialize Qdrant Client (Local storage)
import time
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qdrant_data")

# Retry logic to handle uvicorn --reload locking issues
client = None
for _ in range(5):
    try:
        client = QdrantClient(path=DB_PATH)
        break
    except Exception as e:
        logger.warning(f"Qdrant DB locked, retrying in 1s...")
        time.sleep(1)

if client is None:
    raise RuntimeError("Could not acquire Qdrant lock. Another process is using it.")

# Initialize Embeddings
# all-MiniLM-L6-v2 produces vectors of size 384
try:
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
except Exception as e:
    logger.error(f"Failed to load HuggingFace embeddings: {e}")
    embeddings = None

COLLECTION_NAME = "codesense_findings"

# Ensure collection exists
if embeddings:
    try:
        client.get_collection(collection_name=COLLECTION_NAME)
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

def save_findings(repo_full_name: str, findings: list):
    """
    Saves a list of AgentFinding objects to the vector database.
    """
    if not findings or not embeddings:
        return
        
    points = []
    for finding in findings:
        # Create a rich text representation to embed
        text_to_embed = f"{finding.title}: {finding.explanation}"
        
        try:
            vector = embeddings.embed_query(text_to_embed)
            
            # We store metadata to filter by repo later
            payload = {
                "repo": repo_full_name,
                "title": finding.title,
                "explanation": finding.explanation,
                "agent": finding.agent.value,
                "severity": finding.severity.value,
            }
            
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload
                )
            )
        except Exception as e:
            print(f"Error embedding finding: {e}")
            continue
            
    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True
        )
        logger.info(f"Saved {len(points)} findings to Qdrant memory for {repo_full_name}.")

def find_similar_issues(repo_full_name: str, finding) -> List[Dict[str, Any]]:
    """
    Searches for similar past findings in the same repository.
    finding is an AgentFinding object.
    Returns a list of dictionaries with matching past issues.
    """
    if not embeddings:
        return []
        
    text_to_search = f"{finding.title}: {finding.explanation}"
    
    try:
        query_vector = embeddings.embed_query(text_to_search)
        
        # We want to filter by the same repo to avoid cross-contamination between repos
        repo_filter = Filter(
            must=[
                FieldCondition(
                    key="repo",
                    match=MatchValue(value=repo_full_name)
                )
            ]
        )
        
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=repo_filter,
            limit=3,
        )
        
        results = []
        for hit in search_result.points:
            results.append({
                "score": hit.score,
                "title": hit.payload.get("title"),
                "explanation": hit.payload.get("explanation")
            })
            
        return results
    except Exception as e:
        print(f"Error searching Qdrant: {e}")
        return []
