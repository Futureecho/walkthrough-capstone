"""Coverage Review Agent prompts."""

SUMMARIZE_VIEW_PROMPT = """You are analyzing a property walkthrough photo of a {room_type}.
Orientation hint: {orientation_hint}

Describe what surfaces, fixtures, and areas are visible in this image.
Be specific about:
- Which walls are visible (left, right, far, near)
- Floor and ceiling visibility
- Windows, doors, outlets visible
- Fixtures and appliances visible
- Any corners visible

Respond as a JSON object:
{{
  "visible_surfaces": ["list of surfaces/areas visible"],
  "fixtures": ["list of fixtures/appliances visible"],
  "coverage_areas": ["list from: wall-left, wall-right, wall-far, wall-near, floor, ceiling, corner-left-near, corner-right-near, corner-left-far, corner-right-far, door, window"],
  "quality_notes": "any notes about visibility/obstructions"
}}"""

NEXT_SHOTS_PROMPT = """Based on the coverage analysis of a {room_type}:

Currently covered areas: {covered}
Missing areas: {missing}
Coverage: {coverage_pct}%

Provide 1-3 specific instructions for additional photos to improve coverage.
Each instruction should describe:
1. Where to stand
2. What direction to point the camera
3. What the photo should capture

Be concise and actionable. Respond as a JSON array of instruction strings."""
