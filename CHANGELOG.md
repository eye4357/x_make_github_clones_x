# x_make_telemetry_vector_x — Production Ledger

I record every change to this telemetry normaliser here. Entries adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning so audits can reconstruct the exact state of the pipeline at any point in time.

## [0.1.0] - 2025-11-12
### Added
- Introduced the `x_make_telemetry_vector_x` package with Pydantic schema and `normalize_payload` helper.
- Shipped packaging automation (`scripts/package_telemetry_vector.py`) and manifest support for repeatable builds.
- Authored adoption and metadata blueprints as part of the 0.20.13 cleanup offensive.

### Changed
- Repointed project metadata, README, and evidence logs from clone orchestration to telemetry normalisation.

## [0.20.4] - 2025-10-15
### Changed
- README tightened for the Road to 0.20.4 release, documenting how clone reports now hydrate the Repository Synchronization Kanban column via `make_all_summary.json`.
- Operational guidance refreshed to emphasise capturing missing remote evidence and retry logs in the new board layout.

## [0.20.3] - 2025-10-14
### Changed
- README and operations brief updated for the Road to 0.20.3 release, noting the JSON board pivot and clone metadata alignment.

## [0.20.2] - 2025-10-14
### Changed
- Reissued the documentation for the Road to 0.20.2 release, detailing clone cadence expectations and updated control-room links.

## [0.20.1] - 2025-10-13
### Changed
- Updated README callouts to reference the Road to 0.20.1 control room and proposal so clone automation points at the active release hub.

## [0.20.0-prep] - 2025-10-12
### Added
- Authored a control-room styled README and changelog to standardize clone operations for the Road to 0.20.0 campaign.
- Linked the automation rig to the change-control nexus and compliance visitor for faster situational awareness.

### Changed
- Documented expectations around retry strategies and label filters so contributors stop improvising in production.
