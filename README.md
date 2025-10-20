# x_make_github_clones_x — Supply Chain Doctrine

I wrote this rig to keep the lab's repository inventory exact. It discovers, clones, and refreshes every GitHub dependency on command, logs each outcome as JSON evidence, and reports upstream when a repo drifts. No supply line, no experiment.

## Mission Log
- Mirror designated GitHub repositories using label-aware strategies so we do not waste disk or bandwidth.
- Validate clone health, branch parity, and remote availability.
- File JSON summaries the orchestrator folds into `make_all_summary.json` for the Kanban board.
- Surface drift, retries, and credential failures immediately—silence is unacceptable.

## Instrumentation
- Python 3.11 or newer.
- Git CLI in the operator's `PATH`.
- Optional GitHub token provided via environment variables when private repos are in scope.
- Ruff, Black, MyPy, and Pyright when you intend to run the QA gauntlet.

## Operating Procedure
1. `python -m venv .venv`
2. `\.venv\Scripts\Activate.ps1`
3. `python -m pip install --upgrade pip`
4. `pip install -r requirements.txt`
5. `python x_cls_make_github_clones_x.py --help` to inspect switches.
6. Execute the desired command variation (sync, dry-run, targeted labels) and archive the generated report.

Clone runs deposit their evidence under `reports/` and update `make_all_summary.json` so the command center reflects the truth without reprocessing logs.

## Evidence Checks
| Check | Command |
| --- | --- |
| Formatting sweep | `python -m black .` |
| Lint interrogation | `python -m ruff check .` |
| Type audit | `python -m mypy .` |
| Static contract scan | `python -m pyright` |
| Functional verification | `pytest` |

## System Linkage
- [Changelog](./CHANGELOG.md)
- [Road to 0.20.4 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.4/Road%20to%200.20.4%20Engineering%20Proposal.md)
- [Road to 0.20.3 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.3/Road%20to%200.20.3%20Engineering%20Proposal.md)

## Reconstitution Drill
During the monthly rebuild I wipe a machine, replay `LAB_FROM_SCRATCH.md`, and run this clone driver. Git version, elapsed minutes, error counts, and the resulting JSON all get logged. If the orchestrator cannot hydrate from those artefacts, the defect is mine to eliminate before the window closes.

## Cross-Referenced Assets
- [x_make_common_x](../x_make_common_x/README.md) — shared logging and subprocess scaffolding.
- [x_make_github_visitor_x](../x_make_github_visitor_x/README.md) — consumes freshly cloned repos for compliance sweeps.
- [x_0_make_all_x](../x_0_make_all_x/README.md) — orchestrates clone waves across the release pipeline.

## Conduct Code
Document every new clone tactic in Change Control. Guard credentials, rotate tokens, and capture anomalies before they cascade into the supply chain. This project tolerates zero shadow steps.

## Sole Architect's Note
I alone designed and maintain these clone circuits: credential choreography, retry matrices, JSON reporting, and orchestrator integration. The safeguards derive from the scars of production outages I refuse to repeat.

## Legacy Staffing Estimate
- Without LLM support, replication demands: 1 senior Python engineer, 1 DevOps Git specialist, 1 SRE for credential management, and 1 technical writer.
- Timeline: 10–12 engineer-weeks to replicate functionality and documentation at this fidelity.
- Cost band: USD 90k–120k before you budget for operational overhead.

## Technical Footprint
- Core Language: Python 3.11+ with `subprocess`, `pathlib`, and structured logging.
- External Hooks: Git CLI, optional GitHub REST access via token, HTTP tooling for metadata when enabled.
- Quality Net: Ruff, Black, MyPy, Pyright, pytest, and supporting PowerShell scripts for environment assumptions.
- Integration Points: JSON reports consumed by `x_0_make_all_x`, helpers from `x_make_common_x`, and secret persistence from `x_make_persistent_env_var_x` when required.
