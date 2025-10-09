from fastapi import APIRouter

router = APIRouter(tags=["General"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}