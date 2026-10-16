# Eventer plugin maintenance

Keep this a portable skill package. Do not add a server, database, daemon,
mandatory provider, or model API dependency. Use the harness's existing tools.
Preserve evidence, uncertainty, recipient privacy, and the user's authority.
Use only synthetic fixtures in tests and public examples. No real sends or bookings.
Run `python scripts/validate.py`, `python -m pytest`, and `python evals/run.py offline`.
Behavioral verification requires actual harness execution; never relabel fake
responses or deterministic fixtures as model evaluation. Record blocked checks.
Keep graders outside evaluation workspaces. Package only reviewed public files.
Update skills and regression cases together when changing behavior.
Do not change the original Eventer service from this repository.
