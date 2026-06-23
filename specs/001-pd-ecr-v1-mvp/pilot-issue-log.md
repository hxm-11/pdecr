# PD-ECR V1 MVP Pilot Issue Log

Generated content is `V1_MVP_DRAFT` only and must not be treated as production
approval.

| Date | Area | Issue | Evidence / Source | Impact | Owner | Status |
|---|---|---|---|---|---|---|
| 2026-06-18 | Retrieval | Some historical records are missing MCR No, product_no, or part_no. | Loader `missing_fields` output | UI must show missing-field indicators and generation must avoid unsupported claims. | PD-ECR pilot owner | Open |
| 2026-06-18 | Source references | Generated approval/sign-off module needs human confirmation. | V1 excludes formal approval workflow. | Export must keep demo/non-production status visible. | PD-ECR pilot owner | Open |
| 2026-06-18 | Export | Backend dependency runner `uv`/`pytest` was unavailable in this shell. | Validation note from implementation run | Full backend pytest should be rerun in the project dev environment. | Developer | Open |

## Categories to review during pilot

- Retrieval errors or low relevance
- Missing historical metadata
- Missing source cases or source files
- Generic generated module content
- Export formatting defects
- Follow-up priority for post-V1 work
