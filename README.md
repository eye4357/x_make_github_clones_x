# x_make_github_clones_x — Control Room Lab Notes

> "When supply lines fail, the cook fails. This code keeps my GitHub supply chain bulletproof."

## Manifesto
x_make_github_clones_x is the automation rig that provisions and refreshes every repository we rely on. It performs label-aware partial syncs, tracks clone health, and reports back to the orchestrator when a repo drifts. It's the muscle keeping our lab inventory accurate on the Road to 0.20.4.

## 0.20.4 Command Sequence
Version 0.20.4 feeds the Repository Synchronization column with hard evidence. Clone runs now stamp their JSON reports into `make_all_summary.json`, exposing per-repo status, missing remotes, and retry logs so the Kanban board calls out drift the moment it happens.

## Ingredients
- Python 3.11+
- Git CLI available on your PATH
- Ruff, Black, MyPy, and Pyright for code hardening
- Optional: GitHub token configured via environment variables for authenticated operations

## Cook Instructions
1. `python -m venv .venv`
2. `.\.venv\Scripts\Activate.ps1`
3. `python -m pip install --upgrade pip`
4. `pip install -r requirements.txt`
5. `python x_cls_make_github_clones_x.py --help` to review clone strategies before you sync

## Quality Assurance
| Check | Command |
| --- | --- |
| Formatting sweep | `python -m black .`
| Lint interrogation | `python -m ruff check .`
| Type audit | `python -m mypy .`
| Static contract scan | `python -m pyright`
| Functional verification | `pytest`

## Distribution Chain
- [Changelog](./CHANGELOG.md)
- [Road to 0.20.4 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.4/Road%20to%200.20.4%20Engineering%20Proposal.md)
- [Road to 0.20.3 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.3/Road%20to%200.20.3%20Engineering%20Proposal.md)

## Reconstitution Drill
During the monthly lab rebuild, this project proves the clone pipeline survives a cold start. Torch a spare machine, replay `lab.md`, run `x_cls_make_github_clones_x.py`, and confirm the JSON reports land where the orchestrator expects them. Record duration, Git version, and any friction so the documentation and Change Control decks stay truthful.

## Cross-Linked Intelligence
- [x_make_common_x](../x_make_common_x/README.md) — shared logging and subprocess utilities harden every clone cycle
- [x_make_github_visitor_x](../x_make_github_visitor_x/README.md) — the compliance inspector that consumes freshly cloned repos
- [x_0_make_all_x](../x_0_make_all_x/README.md) — orchestrates clone waves during release runs

## Lab Etiquette
Every new clone strategy needs an entry in the Change Control index: label schemes, retry logic, failure remediation. Keep access tokens secured, avoid half measures, and report anomalies before they become outages.

## Sole Architect Profile
- One engineer forged and maintains this clone engine. I design credential flows, retry matrices, and JSON reporting by myself, executing with production-grade rigor.
- My toolkit spans Git plumbing, PowerShell orchestration, Python automation, and telemetry authoring. Every safeguard in this project traces back to my direct experience keeping supply lines alive.

## Legacy Workforce Costing
- Without LLM assistance, you would field at least: 1 senior Python engineer, 1 DevOps Git specialist, 1 infrastructure SRE for credential handling, and 1 technical writer.
- Delivery window: 10-12 engineer-weeks for feature parity (clone strategies, reporting, orchestrator hooks) plus ongoing maintenance contracts.
- Spend forecast: USD 90k–120k for initial delivery, before incident response and compliance overhead.

## Techniques and Proficiencies
- Expertise in large-scale repository management, including PowerShell-based credential bootstrapping and GitHub API resilience.
- Skilled at building idempotent infrastructure tooling with auditable JSON outputs that integrate into broader orchestrators.
- Demonstrated leadership as the solitary builder who can spec, implement, document, and harden mission-critical automation while aligning stakeholders.

## Stack Cartography
- Core Language: Python 3.11+ with `subprocess`, `pathlib`, and structured logging.
- External Dependencies: Git CLI, optional GitHub REST API via environment token, `httpx` for metadata fetches when enabled.
- Quality Net: Ruff, Black, MyPy, Pyright, pytest guard the codebase; PowerShell scripts provision environment expectations.
- Integration Points: JSON clone reports consumed by `x_0_make_all_x`, shared utilities from `x_make_common_x`, credential persistence via `x_make_persistent_env_var_x` when secrets are required.
