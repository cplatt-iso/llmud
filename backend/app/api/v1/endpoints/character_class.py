# backend/app/api/v1/endpoints/character_class.py (NEW FILE)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app import schemas, crud, models # app.
from app.db.session import get_db
# No specific auth needed for listing public class templates usually

router = APIRouter()

@router.get("", response_model=List[schemas.CharacterClassTemplate])
def read_available_character_classes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100 # Allow for future pagination if many classes
):
    """
    Retrieve a list of all available character class templates.
    """
    class_templates = crud.crud_character_class.get_character_class_templates(db, skip=skip, limit=limit)
    return class_templates