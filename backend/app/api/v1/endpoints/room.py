# backend/app/api/v1/endpoints/room.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session # Import real Session
from .... import schemas, crud # Import the schemas package
from ....services import room_service
from ....db.session import get_db # Import the REAL get_db dependency

router = APIRouter()

@router.get("/{x}/{y}/{z}", response_model=schemas.RoomInDB) # Ensure this is schemas.RoomInDB
async def read_room_details_by_coords(
    x: int,
    y: int,
    z: int,
    db: Session = Depends(get_db) # Use the real Session and get_db
):
    print(f"API endpoint called for coords: x={x}, y={y}, z={z} with DB session: {db}")
    room_pydantic_schema = room_service.get_room_details(db=db, x=x, y=y, z=z)
    if room_pydantic_schema is None:
        print("Room not found in service layer (should have checked DB).")
        raise HTTPException(status_code=404, detail="Room not found. You've wandered off the edge of my persistent patience.")
    print(f"Room found: {room_pydantic_schema.name}")
    return room_pydantic_schema

@router.get("/by_uuid/{room_id_str}", response_model=schemas.RoomInDB)
async def read_room_details_by_uuid_str(
    room_id_str: str, 
    db: Session = Depends(get_db)
):
    try:
        room_uuid = uuid.UUID(room_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid room UUID format: {room_id_str}")
    
    room_orm = crud.crud_room.get_room_by_id(db, room_id=room_uuid)
    if not room_orm:
        raise HTTPException(status_code=404, detail=f"Room with UUID {room_uuid} not found.")
    return schemas.RoomInDB.from_orm(room_orm)