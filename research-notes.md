# V0.4 build notes

V0.4 intentionally does not add more projects. It upgrades what the product does with the project data.

## Prototype matching model
Each project now contains neutral `capabilityTags`.
The browser compares those tags with the contractor's selected capabilities and calculates a personalized match score using:
- capability overlap,
- timing,
- source confidence,
- preferred working radius,
- prime/subcontract work preference.

This is still a validation heuristic, not a production scoring model.

## Production pipeline target
source collectors
→ raw document/page capture
→ structured extraction
→ deduplication
→ status reconciliation
→ neutral project record
→ AI/human review when ambiguous
→ customer-specific matching
→ alerts / map / digest

## Human review
Projects containing inferred language such as “likely” and projects with unresolved award/status questions are explicitly flagged for review.
