# South Mississippi Project Radar — V0.4

Private beta focused on excavation/sitework contractors.

## V0.4 adds the action/intelligence layer
- Contractor capability profile in the browser.
- Personalized project score: `YOUR MATCH`, recalculated from the selected capabilities, timing, confidence, radius, and work style.
- Preferred working radius filter.
- Prime vs subcontract preference.
- Human-readable match explanation on every card.
- Recommended Next Move inside each project.
- Change/freshness fields and automation metadata in `projects.json`.
- Human-review flag for ambiguous or inferred scope.

## Important architecture decision
The project record remains neutral. Customer-specific opportunity interpretation happens in the matching layer.
That preserves the ability to support other customer types later without rewriting the project database.

## Deploy
Replace the existing repo files with these V0.4 versions, then:

git add .
git commit -m "Update Project Radar to V0.4"
git push origin main
