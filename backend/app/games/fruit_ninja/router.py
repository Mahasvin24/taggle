from fastapi import APIRouter

router = APIRouter(prefix="/api/games/fruit-ninja", tags=["fruit-ninja"])


@router.get("")
def game_info() -> dict[str, str | list[str]]:
    """Starter endpoint; fruit samples and labeling endpoints will go here."""
    return {
        "slug": "fruit-ninja",
        "status": "coming-soon",
        "labels": ["fresh", "spoiled"],
    }
