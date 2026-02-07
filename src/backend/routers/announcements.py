"""
Announcements endpoints for the High School Management System API.

This router exposes REST endpoints for creating and managing announcements
that can be shown to students and staff.

Base path
=========
- All routes in this module are prefixed with ``/announcements``.

Endpoints
=========

1. GET /announcements
---------------------
- Description:
  Return all *active* announcements. An announcement is considered active
  when the current date is within its optional ``start_date`` (if present)
  and required ``expiration_date``.
- Authentication:
  None (public endpoint).
- Query parameters:
  None.
- Response:
  A JSON array of announcement objects. Each object has:
  - ``_id`` (string): Announcement identifier.
  - ``message`` (string): Announcement text.
  - ``start_date`` (string | null): Optional ISO date (YYYY-MM-DD) when
    the announcement becomes visible.
  - ``expiration_date`` (string): ISO date (YYYY-MM-DD) when the
    announcement expires.
  - ``created_by`` (string): ID of the teacher that created the announcement.
  - ``created_at`` (string): ISO 8601 timestamp of creation.

2. GET /announcements/all
-------------------------
- Description:
  Return **all** announcements for use in the management interface
  (including expired or not-yet-active announcements), sorted by
  ``created_at`` descending (newest first).
- Authentication:
  Required. Caller must supply a valid teacher username.
- Query parameters:
  - ``username`` (string, required): The teacher's identifier. The value
    must match a document ``{"_id": username}`` in ``teachers_collection``.
- Errors:
  - ``401 Authentication required`` if the username does not correspond
    to an existing teacher.
- Response:
  A JSON array of announcement objects (same shape as in ``GET /announcements``).

3. POST /announcements
----------------------
- Description:
  Create a new announcement.
- Authentication:
  Required. Caller must supply a valid teacher username.
- Body / form parameters:
  - ``message`` (string, required): The announcement text. Must not be
    empty or whitespace-only.
  - ``expiration_date`` (string, required): ISO date (YYYY-MM-DD) when
    the announcement expires. This field must be provided.
  - ``username`` (string, required): The teacher's identifier. Must
    correspond to a document in ``teachers_collection``.
  - ``start_date`` (string | null, optional): ISO date (YYYY-MM-DD)
    when the announcement should begin to be shown. If omitted or null,
    the announcement is considered active immediately (subject to
    ``expiration_date``).
- Errors:
  - ``401 Authentication required`` if the username is not a valid teacher.
  - ``400 Expiration date is required`` if ``expiration_date`` is missing.
  - ``400 Message is required`` if ``message`` is empty or whitespace.
- Response:
  The created announcement object, including its generated ``_id``.

4. PUT /announcements/{announcement_id}
--------------------------------------
- Description:
  Update an existing announcement identified by ``announcement_id``.
- Authentication:
  Required. Caller must supply a valid teacher username.
- Path parameters:
  - ``announcement_id`` (string, required): The identifier of the
    announcement to update.
- Body / form parameters:
  - ``message`` (string, required): New announcement text.
  - ``expiration_date`` (string, required): New expiration date
    (ISO date, YYYY-MM-DD).
  - ``username`` (string, required): The teacher's identifier. Must
    correspond to a document in ``teachers_collection``.
  - ``start_date`` (string | null, optional): New start date (ISO date,
    YYYY-MM-DD) or null to remove a previously set start date.
- Errors:
  - ``401 Authentication required`` if the username is not a valid teacher.
  - ``404 Announcement not found`` if the given ``announcement_id`` does
    not exist.
- Response:
  The updated announcement object.

5. DELETE /announcements/{announcement_id}
------------------------------------------
- Description:
  Delete an existing announcement identified by ``announcement_id``.
- Authentication:
  Required. Caller must supply a valid teacher username.
- Path parameters:
  - ``announcement_id`` (string, required): The identifier of the
    announcement to delete.
- Query / body parameters:
  - ``username`` (string, required): The teacher's identifier. Must
    correspond to a document in ``teachers_collection``.
- Errors:
  - ``401 Authentication required`` if the username is not a valid teacher.
  - ``404 Announcement not found`` if the given ``announcement_id`` does
    not exist.
- Response:
  JSON object with a confirmation message (e.g., ``{"detail": "Deleted"}``).

Security and data handling
--------------------------
- These endpoints rely on the ``teachers_collection`` to validate the
  ``username`` parameter for management actions (list all, create, update,
  delete).
- Only minimal error details are returned to clients; errors should be
  logged server-side as needed.
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
