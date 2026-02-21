"""Coverage Review Agent tools."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Room-type checklists: what areas should be documented
ROOM_CHECKLISTS = {
    "default": [
        "wall-left", "wall-right", "wall-far", "wall-near",
        "floor", "ceiling", "door",
    ],
    "Living Room": [
        "wall-left", "wall-right", "wall-far", "wall-near",
        "floor", "ceiling", "door", "window",
    ],
    "Kitchen": [
        "wall-left", "wall-right", "wall-far", "wall-near",
        "floor", "ceiling", "door", "countertop", "appliances",
    ],
    "Bedroom": [
        "wall-left", "wall-right", "wall-far", "wall-near",
        "floor", "ceiling", "door", "window", "closet",
    ],
    "Bathroom": [
        "wall-left", "wall-right", "wall-far", "wall-near",
        "floor", "ceiling", "door", "fixtures", "mirror",
    ],
    "Hallway": [
        "wall-left", "wall-right", "floor", "ceiling", "door",
    ],
}


def get_checklist(room_type: str) -> list[str]:
    """Get the coverage checklist for a room type."""
    # Try exact match, then partial match, then default
    if room_type in ROOM_CHECKLISTS:
        return ROOM_CHECKLISTS[room_type]
    for key in ROOM_CHECKLISTS:
        if key.lower() in room_type.lower():
            return ROOM_CHECKLISTS[key]
    return ROOM_CHECKLISTS["default"]


def aggregate_coverage(summaries: list[dict], room_type: str) -> dict:
    """Deterministic aggregation of vision summaries against room checklist.

    Args:
        summaries: list of parsed vision LLM summaries, each with 'coverage_areas' key
        room_type: the room type string

    Returns:
        dict with coverage_pct, covered, missing, checklist
    """
    checklist = get_checklist(room_type)
    covered = set()

    for s in summaries:
        areas = s.get("coverage_areas", [])
        for area in areas:
            # Normalize and match against checklist
            area_lower = area.lower().strip()
            for item in checklist:
                if item.lower() in area_lower or area_lower in item.lower():
                    covered.add(item)
                    break
            # Also check fixtures / special items
            if "counter" in area_lower:
                covered.add("countertop")
            if "appliance" in area_lower or "stove" in area_lower or "fridge" in area_lower:
                covered.add("appliances")
            if "closet" in area_lower:
                covered.add("closet")
            if "mirror" in area_lower:
                covered.add("mirror")
            if "fixture" in area_lower or "sink" in area_lower or "toilet" in area_lower or "tub" in area_lower:
                covered.add("fixtures")

    # Also count areas mentioned in visible_surfaces
    for s in summaries:
        for surface in s.get("visible_surfaces", []):
            surface_lower = surface.lower()
            for item in checklist:
                if item.lower() in surface_lower or surface_lower.startswith(item.split("-")[0]):
                    covered.add(item)

    # Filter covered to only items in checklist
    covered = covered.intersection(set(checklist))
    missing = [item for item in checklist if item not in covered]
    pct = (len(covered) / len(checklist) * 100) if checklist else 100.0

    return {
        "coverage_pct": round(pct, 1),
        "covered": sorted(covered),
        "missing": missing,
        "checklist": checklist,
    }


def parse_summary_response(response: str) -> dict:
    """Parse vision LLM JSON response, with fallback."""
    # Try to extract JSON from response
    try:
        # Handle markdown code blocks
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.warning(f"Failed to parse LLM summary as JSON, using fallback")
        return {
            "visible_surfaces": [],
            "fixtures": [],
            "coverage_areas": [],
            "quality_notes": response[:200],
        }


def parse_instructions_response(response: str) -> list[str]:
    """Parse instruction generation response."""
    try:
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        result = json.loads(text)
        if isinstance(result, list):
            return [str(x) for x in result]
    except (json.JSONDecodeError, IndexError):
        pass
    # Fallback: split by newlines
    return [line.strip().lstrip("0123456789.-) ") for line in response.strip().split("\n") if line.strip()]
