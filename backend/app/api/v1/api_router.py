from fastapi import APIRouter
from .endpoints import room, command, user, character, inventory, map, character_class # This imports the router from endpoints/room.py

# This router will be included with a prefix like /api by main.py
# So paths here are relative to that.
api_router = APIRouter() 

# All routes defined in 'room.router' will be prefixed with '/room'
# So, a GET "/{x}/{y}/{z}" in room.router becomes GET "/room/{x}/{y}/{z}" here.
api_router.include_router(room.router, prefix="/room", tags=["Rooms"])
api_router.include_router(command.router, prefix="/command", tags=["Commands"])
api_router.include_router(user.router, prefix="/users", tags=["Users"])
api_router.include_router(character.router, prefix="/character", tags=["Characters"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(map.router, prefix="/map", tags=["Map"])
api_router.include_router(character_class.router, prefix="/character-class", tags=["Character Classes"])