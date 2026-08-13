# South Mississippi Project Radar — V0.1

Private-ish validation prototype for excavation/sitework contractors.

## Deploy to GitHub Pages
1. Create a new GitHub repository (for example `south-ms-project-radar`).
2. Upload `index.html` and `projects.json` to the repository root.
3. In GitHub: Settings → Pages → Build and deployment → Deploy from a branch.
4. Select `main` and `/ (root)`, then Save.
5. GitHub will provide the Pages URL. Do not advertise it yet.

`index.html` contains `noindex,nofollow,noarchive` to discourage search indexing.

## Important V0.1 limitations
- The dataset is deliberately small and verified rather than padded with invented leads.
- Some pins are approximate city/project-area coordinates when an exact coordinate was not confirmed.
- Most discovered 2026 public bids are already closed as of Aug. 13, 2026. The prototype therefore demonstrates why freshness/status verification is the core product.
- The email-interest box is UI-only in V0.1. Do not collect addresses until a backend/form endpoint is connected.
- Opportunity scores are editorial heuristics and must not be represented as bid eligibility or guaranteed available work.

## Files
- `index.html` — complete map app
- `projects.json` — editable opportunity dataset
- `research-notes.md` — source notes and next data targets
