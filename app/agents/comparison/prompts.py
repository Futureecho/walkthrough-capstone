"""Comparison Agent prompts."""

ANALYZE_CANDIDATE_PROMPT = """You are analyzing a candidate difference between move-in and move-out photos of a {room} in a rental property.

The highlighted region shows a possible area of change.

IMPORTANT LANGUAGE POLICY:
- NEVER say "damage confirmed", "damage detected", "tenant caused", "fault", or "liable"
- Use "candidate difference", "possible change", "appears to show", "may indicate"
- You are identifying areas that MAY warrant further review, not making determinations

Move-in image is on the left, move-out image is on the right.
The region of interest is at approximately ({x}, {y}) with size ({w}x{h}).

Analyze the highlighted region and provide:
1. What appears to be different between the two images in this region
2. Your confidence (0.0 to 1.0) that this represents a genuine change
3. Reason codes from: [scuff, stain, hole, crack, discoloration, missing_item, added_item, wear, other]
4. Whether a close-up photo would help clarify

Respond as JSON:
{{
  "analysis": "description of the candidate difference",
  "confidence": 0.7,
  "reason_codes": ["scuff", "wear"],
  "needs_closeup": true
}}"""

COMPOSE_FOLLOWUP_PROMPT = """Compose a brief, neutral follow-up message for the tenant about a candidate difference found in the {room}.

Analysis: {analysis}
Confidence: {confidence}
Reason codes: {reason_codes}

IMPORTANT: Use cautious, neutral language. Never imply fault or confirmed damage.
The message should:
1. Describe what was observed using "candidate difference" / "appears to" / "may indicate"
2. Ask if the tenant can confirm or provide context
3. If helpful, request a close-up photo of the area

Keep it under 3 sentences. Be professional and fair."""
