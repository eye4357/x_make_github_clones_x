# x_make_github_clones_x — Lab Notes from Walter White

> "When supply lines fail, the cook fails. This code keeps my GitHub supply chain bulletproof."

## Manifesto
x_make_github_clones_x is the automation rig that provisions and refreshes every repository we rely on. It performs label-aware partial syncs, tracks clone health, and reports back to the orchestrator when a repo drifts. It's the muscle keeping our lab inventory accurate on the Road to 0.20.0.

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
- [Road to 0.20.0 Control Room](../x_0_make_all_x/Change%20Control/0.20.0/index.md)
- [Road to 0.20.0 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.0/Road%20to%200.20.0%20Engineering%20Proposal%20-%20Walter%20White.md)

## Cross-Linked Intelligence
- [x_make_common_x](../x_make_common_x/README.md) — shared logging and subprocess utilities harden every clone cycle
- [x_make_github_visitor_x](../x_make_github_visitor_x/README.md) — the compliance inspector that consumes freshly cloned repos
- [x_0_make_all_x](../x_0_make_all_x/README.md) — orchestrates clone waves during release runs

## Lab Etiquette
Every new clone strategy needs an entry in the Change Control index: label schemes, retry logic, failure remediation. Keep access tokens secured, avoid half measures, and report anomalies before they become outages.
