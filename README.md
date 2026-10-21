# Mona Metrics

**Small data. Big purrs. Questionable intergalactic business decisions.**

Mona runs two cat cafes on the Octoverse trade route. This Python demo turns
their daily counter exports into reproducible reports, catches dodgy data, and
gives a repository-local AI data steward something real to investigate.

All cafes, dates, credits, visits, and adoptions are **clearly synthetic demo
data**. They are not GitHub customer data, live business metrics, agent-run
history, or CAO telemetry. No CAO or Repo Assist is installed here.

## Launch the analytics pod

Requires Python 3.11+; no third-party Python packages, accounts, or API keys.
Run commands from the repository root:

```sh
python3 -m mona_metrics report
python3 -m mona_metrics report --format json
python3 -m mona_metrics check
python3 -m unittest discover -s tests -v
```

The baseline has 14 daily cafe records, 658 visits, 574 orders, 6,888 credits,
and 19 adoptions over September 1-7, 2026. Orders count transactions, not
individual drinks; conversion means orders / visits, not unique buyers.
Revenue is in whole fictional credits; adoption counts are not a causal
measure of cafe performance.

Try the deliberately spicy export:

```sh
python3 -m mona_metrics report --data data/scenarios/meteor-shower.csv
python3 -m mona_metrics check --data data/scenarios/meteor-shower.csv
```

The second command deliberately exits **1**: this fixture has a missing cafe-day,
a traffic spike, low conversion, and excess food waste. It is a test scenario,
not broken CI. Tests assert these findings. Malformed input exits **2**, writes
an explicit diagnostic to stderr, and produces no misleading partial report.
`report` exits 0 for valid data even when warnings exist; `check` exits 0 only
when no warnings exist. Missing files and invalid configuration also exit 2.

## What is in the cargo hold?

| Path | Purpose |
| --- | --- |
| `data/cafes.json` | Cafe names and explicit quality thresholds |
| `data/daily.csv` | Clean, seven-day baseline for two cafes |
| `data/scenarios/meteor-shower.csv` | Intentional warnings for demo investigations |
| `mona_metrics/` | Standard-library parser, checks, aggregation, and CLI |
| `tests/` | Exact totals, thresholds, malformed input, and CLI contracts |
| `.github/workflows/ci.yml` | Ordinary Python CI on pushes and pull requests |
| `.github/workflows/data-steward.md` | Actual GitHub Agentic Workflow source |
| `.github/workflows/data-steward.lock.yml` | Compiler-generated Actions workflow |

Reports sort cafes, dates, and warnings, never use the current clock, and include
an input SHA-256 fingerprint. Currency sums use integers; rates round to four
decimal places. Waste is grams. The same input bytes yield identical output.
Only validated rows contribute to metrics. See [the data contract](data/README.md)
for assumptions and thresholds.

## Meet the data steward

The **Mona data steward** is a genuine Copilot-powered GitHub Agentic Workflow,
not a Python script pretending to be an agent. It runs **Tuesdays at 09:17 UTC**
and supports `workflow_dispatch`. Schedules become eligible through a normal
merge to the default branch; this bootstrap does not dispatch it, seed paid
runs, or fabricate prior activity.

Deterministic preparation produces compact JSON for both fixtures. The agent
then checks interpretations against the actual CSV and configuration, explains
the warning scenario, distinguishes observation from hypothesis, and recommends
one bounded improvement. It may create **at most one** `[Mona steward]` issue.
A stable input-derived title, safe-output deduplication, a bounded read of prior
issues, and replacement of older reports prevent a weekly issue pile-up.
Unchanged/already-reported evidence must produce `noop`.

The agent cannot push code or directly write GitHub resources. Its repository
permissions are read-only; only the compiler's separate safe-output job can
create an issue. External network access is denied in the agent sandbox.
The main execution is capped at 12 turns, 8 minutes, and 100 gh-aw AI Credits,
with a 200-credit per-user/workflow 24-hour activation guardrail. The compiler's
separate AI threat-detection job has its own default 400-credit budget and
10-minute execution timeout; setup and other jobs have separate timeouts.
These are runtime guardrails, **not a guaranteed monetary spending cap**.
Automatic failure/version issues are disabled; failures remain visible in
Actions logs and conclusions. Human review remains required for recommendations.

### Authentication, model, and billing prerequisites

This workflow is compiled with **`gh aw v0.92.6`** and explicitly uses Copilot
with **`gpt-5-mini`**. Before running, a repository administrator must verify:

- GitHub Actions and GitHub Agentic Workflows/Copilot workflow-token inference
  are available and allowed for this organization and repository.
- Organization policy permits `copilot-requests: write` and the selected model.
  This permission authorizes inference, **not repository writes**.
- The organization has the necessary Copilot entitlement, enabled billing and
  budget for workflow-token requests, and sufficient model capacity. AI usage
  and Actions usage follow GitHub's applicable billing; this is not promised free.
- The generated safe-output job may use `issues: write`, and Issues are enabled.
  The agent itself has only `contents: read` and `issues: read` for repository data.

The compiled workflow uses the ephemeral **`github.token`** inference path;
no PAT or `COPILOT_GITHUB_TOKEN` secret is required by this configuration.
Availability, model access, and charging depend on GitHub policy and account
configuration; local compilation does not prove entitlement or successful
inference. Do not create credentials or substitute tokens to bypass policy.
If the model is unavailable, explicitly choose an allowed model and recompile.
See [upstream authentication guidance](https://github.github.com/gh-aw/reference/auth/).

After approved merge, genuine scheduled or explicitly approved manual executions
can supply authentic gh-aw evidence for a later CAO quickstart. Sample cafe
records are not evidence of workflow runs, costs, or outcomes.

### Editing the workflow

Install the repository's pinned CLI version in an isolated environment if needed;
do not silently upgrade shared tools. Edit the Markdown source, never its lock.

```sh
gh aw version  # expected v0.92.6
gh aw compile data-steward --strict --validate --actionlint --shellcheck
gh aw list --json
git diff -- .github/workflows
```

Commit the source, generated lock, and generated manifest together. No manual
workflow activation, credentials setup, CAO installation, or Repo Assist is part
of this demo.
