from fastapi import APIRouter, Depends, Query

from app import aronium_db
from app.auth import require_internal_api_key
from app.schemas import DocumentOut

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_internal_api_key)],
)


@router.get("/recent", response_model=list[DocumentOut])
def list_recent_documents(since_id: int = Query(default=0), limit: int = Query(default=100, le=500)):
    """
    Used by fidelityAPI to poll for new sales that haven't been converted
    into points yet. fidelityAPI keeps track of `since_id` on its own side
    (in loyalty.db) - generalAPI stays completely stateless about points.
    """
    return aronium_db.list_recent_documents(since_id=since_id, limit=limit)
