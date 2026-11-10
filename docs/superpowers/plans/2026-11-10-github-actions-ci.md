# GitHub Actions CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore executable CI on `master` and delete every GitHub Actions cache after each run.

**Architecture:** Keep one quality job for the existing locked Python checks. A second cleanup job depends on it with `if: always()` so cache deletion happens after the quality job and its post-job hooks, independently of quality result.

**Tech Stack:** GitHub Actions, Ubuntu runner, Python 3.12, uv, pytest, Ruff, GitHub CLI.

**Spec:** `docs/superpowers/specs/2026-11-10-github-actions-ci-design.md`

## Global Constraints

- Trigger only for pushes and pull requests targeting `master`.
- Do not declare a service container; the checks need no external service.
- Use the existing `uv.lock` with `uv sync --frozen`.
- The cleanup job must run after either quality success or failure and use `gh cache delete --all --succeed-on-no-caches`.
- Give `actions: write` only to the cleanup job; quality gets only `contents: read`.
- Do not modify or stage `.gitignore`.
- Add no dependency, cache strategy, artifact, deploy, or application-test change.

## Review Focus

- A failed `pytest` still triggers `cleanup` because it has `needs: quality` and `if: always()` — Task 1.
- A repository with no Action caches returns success via `--succeed-on-no-caches` — Task 1.
- Cache cleanup runs after quality post-job hooks, not as a step inside `quality` — Task 1.
- The GitHub token can delete caches but quality cannot mutate Actions because write permission is job-scoped — Task 1.
- Pushes to `master` and pull requests targeting `master` schedule the workflow — Task 1.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `.github/workflows/ci.yml` | GitHub Actions triggers, quality checks, and post-quality cache cleanup. |
| `docs/superpowers/specs/2026-11-10-github-actions-ci-design.md` | Approved scope and cleanup rationale. |
| `docs/superpowers/plans/2026-11-10-github-actions-ci.md` | Implementation and verification plan. |

### Task 1: Restore CI and add post-run cache cleanup

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `docs/superpowers/specs/2026-11-10-github-actions-ci-design.md`
- Create: `docs/superpowers/plans/2026-11-10-github-actions-ci.md`

**Interfaces:**
- Consumes: `uv.lock`, repository default branch `master`, `github.token`, and `$GITHUB_REPOSITORY`.
- Produces: a `quality` job and a `cleanup` job with repository-wide Actions-cache deletion.

- [ ] **Step 1: Establish the current invalid-workflow reproduction**

Record that GitHub Actions run `42841090431` has conclusion `failure` with no
jobs, and that `.github/workflows/ci.yml` contains `services: none`.

- [ ] **Step 2: Replace the invalid workflow declaration**

Target `master` for both existing triggers. Remove `services: none` and remove
`cache: "uv"`; retain checkout, Python 3.12, locked dependency sync, pytest,
Ruff check, and Ruff format check.

- [ ] **Step 3: Add the post-quality cleanup job**

Define `cleanup` with `needs: quality`, `if: ${{ always() }}`, and job-level
`permissions.actions: write`. Set `GH_TOKEN` to `${{ github.token }}` and run
`gh cache delete --all --succeed-on-no-caches --repo "$GITHUB_REPOSITORY"`.

- [ ] **Step 4: Validate configuration locally**

Run: `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml"); puts "valid YAML"'`

Expected: `valid YAML`. Review the diff to verify that the cleanup is a separate
job and permissions are scoped as designed.

- [ ] **Step 5: Run the relevant local quality commands**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`

Expected: Current application-test failures, if any, are reported separately;
they are not hidden or removed by this CI-only change. Ruff commands should run
after the test failure is addressed in a later task.

- [ ] **Step 6: Commit and push reviewed paths only**

Stage `.github/workflows/ci.yml` and the two CI design/plan files individually.
Create an imperative conventional commit, push `master`, and inspect the remote
workflow run to confirm jobs are scheduled and cleanup runs.

## Self-review

- **Spec coverage:** Task 1 covers valid workflow syntax, `master` triggers,
  locked quality checks, job-scoped Actions permission, and unconditional,
  repository-wide cache cleanup.
- **Step scan:** Each workflow behavior has a named field or command; no new
  software interface is introduced.
- **Type consistency:** GitHub job IDs are consistently `quality` and `cleanup`.
- **Review Focus:** The five failure modes are owned by Task 1 and verified by
  workflow structure plus the remote post-push run.
- **Proportion:** One focused task changes only the workflow and required design
  records.
