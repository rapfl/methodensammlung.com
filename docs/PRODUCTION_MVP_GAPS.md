# Production MVP Gaps

## Current weaknesses

- Persistence is local-only. Drafts, session notes, and runtime state live in `localStorage`, with no shared backend or account model.
- Routing is hash-based. It works for the prototype, but it is not yet a production-grade navigation setup.
- Duration coverage in the SSOT is sparse. Several workflows depend on partial or unknown timing data by design.
- Active Session is intentionally lightweight and local. There is no sync, recovery, or cross-device handoff.
- Finder quality is strong visually, but still constrained by sparse and uneven SSOT coverage for duration and materials.
- Verification is currently limited to build, lint, and type checks plus manual route review. There is no automated browser or regression coverage.

## Open tasks

- Add a real deployment-ready routing and hosting strategy.
- Define a backend or sync layer for drafts, active sessions, and notes.
- Improve SSOT coverage for duration, materials, and other operational fields that the UI depends on.
- Add structured QA for the main routes:
  - Finder
  - Library
  - Method Detail
  - Composer
  - Active Session
- Harden the release process with a documented build-and-publish path.

## MVP-hardening to-dos

- Product
  - Finalize the Finder interaction model and validate it with real stressful-use scenarios.
  - Review all copy and visual calmness route by route for production polish.
  - Define the exact MVP scope for facilitator workflows versus browse/discovery workflows.

- Data
  - Establish a clear SSOT update process and versioning approach.
  - Fill missing grounded durations where possible.
  - Normalize material metadata further so filtering and operational prep become more reliable.

- Engineering
  - Add automated smoke tests for primary route rendering and core interactions.
  - Add release checks for workbook export integrity and generated bundle consistency.
  - Decide whether generated data files stay committed or are always produced in CI.

- Operational readiness
  - Document deployment, rollback, and content-update steps.
  - Define ownership for SSOT maintenance, app QA, and release approval.
  - Decide how production incidents or wrong workbook content should be corrected quickly.
