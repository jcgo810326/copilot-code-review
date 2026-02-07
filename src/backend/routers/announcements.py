"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


@router.get("")
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all active announcements (within date range)"""
    current_date = datetime.now().date().isoformat()
    
    # Find announcements that are active (current date is within start and expiration dates)
    announcements = list(
        announcements_collection
        .find({
            "$or": [
                {"start_date": {"$exists": False}},
                {"start_date": None},
                {"start_date": {"$lte": current_date}}
            ],
            "expiration_date": {"$gte": current_date}
        })
        # Ensure deterministic ordering so announcements[0] is stable on the frontend
        .sort([("start_date", -1), ("created_at", -1)])
    )
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        if "_id" in announcement:
            announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.get("/all")
def get_all_announcements(username: str) -> List[Dict[str, Any]]:
    """Get all announcements (for management interface). Requires authentication."""
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get all announcements, sorted by creation date (newest first)
    announcements = list(announcements_collection.find({}).sort("created_at", -1))
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        if "_id" in announcement:
            announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.post("")
def create_announcement(
    message: str,
    expiration_date: str,
    username: str,
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new announcement. Requires authentication."""
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate expiration_date is provided
    if not expiration_date:
        raise HTTPException(status_code=400, detail="Expiration date is required")
    
    # Validate message is not empty
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Create announcement document
    announcement = {
        "message": message.strip(),
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_by": username,
        "created_at": datetime.now().isoformat()
    }
    
    # Insert into database
    result = announcements_collection.insert_one(announcement)
    
    # Return the created announcement with its ID
    announcement["_id"] = str(result.inserted_id)
    return announcement


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    username: str,
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing announcement. Requires authentication."""
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate expiration_date is provided
    if not expiration_date:
        raise HTTPException(status_code=400, detail="Expiration date is required")
    
    # Validate message is not empty
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Convert string ID to ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Update the announcement
    update_data = {
        "message": message.strip(),
        "expiration_date": expiration_date,
        "updated_by": username,
        "updated_at": datetime.now().isoformat()
    }
    unset_data: Dict[str, Any] = {}

    # Handle start_date updates:
    # - If explicitly provided as an empty string, clear the field.
    # - If provided as a non-empty value, update it.
    # - If None, do not modify the existing value.
    if start_date == "":
        unset_data["start_date"] = 1
    elif start_date is not None:
        update_data["start_date"] = start_date

    update_query: Dict[str, Any] = {"$set": update_data}
    if unset_data:
        update_query["$unset"] = unset_data
    
    result = announcements_collection.update_one(
        {"_id": obj_id},
        update_query
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Fetch and return the updated announcement
    announcement = announcements_collection.find_one({"_id": obj_id})
    announcement["_id"] = str(announcement["_id"])
    
    return announcement


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, username: str) -> Dict[str, str]:
    """Delete an announcement. Requires authentication."""
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Convert string ID to ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Delete the announcement
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
