# Responsible AI

## Overview

This system uses AI to assist with property walkthrough documentation. Given its potential impact on financial disputes between landlords and tenants, responsible AI practices are critical.

## Privacy & Data Protection

### Image Data
- All images are stored locally on the server filesystem — no third-party storage
- Images sent to LLM APIs (OpenAI/Anthropic) are transmitted via encrypted connections
- No persistent storage of images by LLM providers (per their API data policies)
- Image paths use opaque ULIDs, not personally identifiable information

### Tenant Information
- Minimal PII collected: tenant name only (optional)
- No biometric data extracted from images
- Database stored locally in SQLite — no cloud database
- Reports contain only property documentation, not personal profiles

### Data Retention
- Images and data persist until explicitly deleted
- No automatic data sharing with third parties
- Tenant responses and comments stored alongside comparison data for audit trail

## Bias & Fairness

### Language Policy
The system enforces strict language controls to prevent bias:
- **Never** uses terms like "damage confirmed", "fault", "liable", or "tenant caused"
- All findings described as "candidate differences" requiring human review
- Confidence scores provided for transparency, not as determinations
- Language policy enforced both in prompts and post-processing code

### Assessment Fairness
- System identifies areas of **possible** change, never confirms damage
- Both move-in and move-out photos treated identically by the pipeline
- Classical CV metrics are objective and reproducible
- LLM analysis includes confidence scores for transparency
- "Fail-closed" design: uncertain cases flagged for manual review rather than automated determination

### Limitations Disclosed
- SSIM-based comparison is sensitive to lighting, angle, and camera differences
- Not all visual changes indicate damage (normal wear, seasonal changes, lighting)
- AI analysis is supplementary to human judgment, not a replacement
- System cannot determine causation, only identify visual differences

## Safety

### Consent
- System should be deployed with clear tenant notification that AI-assisted photo analysis is used
- Tenants have the ability to respond (confirm/disagree) to each candidate difference
- Close-up photo upload provides tenants an opportunity to provide additional evidence

### Human Oversight
- All agent outputs are advisory — final decisions require human review
- Reports include disclaimers about the nature of automated analysis
- Green checkmarks indicate quality/coverage checks passed, NOT "no issues found"
- System explicitly recommends in-person verification for all candidates

### Transparency
- Quality metrics (blur, darkness, sharpness scores) are visible and reproducible
- Coverage checklists show exactly what areas were/weren't documented
- Comparison confidence scores explain how certain the system is about each finding
- Reason codes provide machine-readable explanations for flagged regions

## Responsible Deployment

### Recommended Practices
1. Inform all parties that AI-assisted analysis is being used
2. Never use system outputs as sole evidence in disputes
3. Ensure both parties have access to view the full report
4. Maintain the human-in-the-loop for all final assessments
5. Regularly review language policy compliance via evaluation harness

### Monitoring
- Evaluation harness includes language policy compliance tests
- All forbidden terms are checked programmatically in every agent output
- Regular audits recommended to verify no biased patterns emerge
