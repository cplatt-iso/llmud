# backend/app/services/room_service.py
from sqlalchemy.orm import Session # Use the real Session type
from typing import Optional
from .. import crud, schemas, models # Import models too

def get_room_details(db: Session, *, x: int, y: int, z: int) -> Optional[schemas.RoomInDB]:
    """
    Service layer to get room details.
    Fetches ORM model from CRUD and converts to Pydantic schema.
    """
    room_orm_model = crud.crud_room.get_room_by_coords(db=db, x=x, y=y, z=z)
    if room_orm_model:
        # Convert the SQLAlchemy ORM model instance to a Pydantic schema instance
        # Pydantic v2 uses .from_orm() via the Config.from_attributes = True setting
        return schemas.RoomInDB.from_orm(room_orm_model)
    return None