# Multi-Scheduler Providers - Implementation Spec

This spec defines how Hermes should support multiple scheduler providers behind one stable scheduled-jobs model. The immediate goal is to preserve current Hermes scheduler behavior for all existing users while adding a second provider, `fly_io`, without forcing API, CLI, or tool callers to change how they create or manage jobs. This spec is for the `codex/multi-scheduler-types` branch and is currently `draft`.

**Initiative:** Hermes multi-scheduler providers
**Status:** draft

## Requirements

| # | User input | Current behaviour | Expected behaviour | Verified |
|---|---|---|---|---|
| R1 | A user upgrades Hermes and already has a recurring job created with `schedule="every 1h"` | Hermes assumes one built-in scheduler and stores job state locally | After upgrade, the job still lists, runs, pauses, resumes, and updates with no config changes required | Verified by inspection of current local cron storage and scheduler flow |
| R2 | An operator starts Hermes with no scheduler provider configured | Hermes implicitly uses the built-in scheduler | Hermes continues to use the built-in scheduler by default | Verified by inspection of current single-provider behavior |
| R3 | An operator starts Hermes with provider `builtin` and creates `name="daily report", schedule="0 9 * * *"` | No provider abstraction exists today | Hermes accepts the request and behaves exactly like current Hermes | Verified by inspection of current jobs API, CLI, and scheduler flow |
| R4 | An operator starts Hermes with provider `fly_io` and creates `name="daily report", schedule="0 9 * * *"` through `/api/jobs` | Hermes has no Fly.io scheduler provider | Hermes accepts the same request body and manages the job using the `fly_io` provider without requiring provider fields in the request | Verified by inspection of current `/api/jobs` request shape |
| R5 | A client sends `POST /api/jobs` with `{"name":"digest","schedule":"every 30m","prompt":"summarize status"}` | Hermes accepts the payload because there is only one scheduler implementation | Hermes continues accepting the same payload shape under `builtin` and `fly_io` | Verified by inspection of existing API server tests |
| R6 | An operator configures an unsupported provider like `banana` | Hermes has no provider validation because provider selection does not exist | Hermes fails clearly and predictably instead of silently falling back | Verified by gap analysis against current code |
| R7 | A remote coordinator triggers the same due Fly-managed occurrence twice | Current Hermes owns due-job discovery locally and avoids duplicate local execution through local state transitions | Hermes records at most one execution for a single due occurrence merely because the remote coordinator retried the wake/trigger path | Verified by requirement analysis for remote scheduling safety |
| R8 | A user pauses, resumes, triggers, lists, gets, updates, or deletes a job under either provider | These actions exist today only for the built-in scheduler | These actions remain available with the same user-visible semantics regardless of selected provider | Verified by inspection of current jobs API, CLI, and tool surfaces |

## Phases

### Phase 1 - Provider Selection And Backward Compatibility

**Status:** not started
**Ticket:** `codex/multi-scheduler-types`
**Fixes:** R1, R2, R3, R6

#### Behaviour

- Given Hermes starts with no scheduler provider configured, when a user lists or runs existing scheduled jobs, then Hermes behaves exactly as it does today.
- Given Hermes starts with provider `builtin`, when a user creates, updates, pauses, resumes, triggers, or deletes a job, then the observable result matches current Hermes behavior.
- Given Hermes starts with an unsupported provider like `banana`, when the scheduler subsystem initializes, then Hermes reports a clear unsupported-provider error and does not silently run jobs with a different provider.
- Given a user upgrades from current Hermes with existing local jobs, when Hermes starts with the default provider, then all existing jobs remain valid without a manual migration step.

#### Verification

| Input | Expected output | Verified result |
|---|---|---|
| Existing recurring job with `schedule="every 1h"`, Hermes started with no provider config | Job appears and behaves exactly as before | |
| Hermes started with `provider=builtin`, user creates `name="daily report", schedule="0 9 * * *"` | Job is created and behaves like current Hermes | |
| Hermes started with `provider=banana` | Hermes fails with a clear unsupported-provider error | |
| Existing paused job created before the feature, Hermes restarted with default config | Job remains paused and does not run unexpectedly | |

#### Not in scope

- Any Fly.io-specific scheduling behavior
- New API request fields
- Third-party scheduler providers

### Phase 2 - Shared Job Semantics Across Providers

**Status:** not started
**Ticket:** `codex/multi-scheduler-types`
**Fixes:** R4, R5, R8

#### Behaviour

- Given the provider is `builtin` or `fly_io`, when a user creates a job through the API, CLI, or scheduler tool, then the same user-visible job fields and schedule semantics apply.
- Given a user creates `name="daily report", schedule="0 9 * * *", prompt="summarize status", deliver="local"`, when the job is listed or retrieved, then the same core job state is visible regardless of provider.
- Given a user pauses or resumes a job under either provider, when the action succeeds, then the job state changes in the same observable way.
- Given a user triggers a job immediately under either provider, when the request is accepted, then the job becomes eligible for immediate execution according to the selected provider.
- Given a client sends the current `/api/jobs` payload shape, when Hermes is running under either provider, then Hermes accepts the request without requiring a provider-specific field.

#### Verification

| Input | Expected output | Verified result |
|---|---|---|
| `POST /api/jobs` with `{"name":"daily report","schedule":"0 9 * * *","prompt":"summarize status"}` under `builtin` | Job created successfully | |
| Same request under `fly_io` | Job created successfully with the same visible core fields | |
| `POST /api/jobs/{id}/pause` under `builtin` and `fly_io` | Job enters paused state in both modes | |
| `POST /api/jobs/{id}/run` under `builtin` and `fly_io` | Job becomes eligible for immediate execution in both modes | |
| `PATCH /api/jobs/{id}` updating `name` and `prompt` under both providers | Updated job shows new values with unchanged provider-independent semantics | |

#### Not in scope

- Provider-specific diagnostics in the request body
- Per-job provider selection
- Remote-only metadata exposed to end users

### Phase 3 - Fly.io Provider Coordination Semantics

**Status:** not started
**Ticket:** `codex/multi-scheduler-types`
**Fixes:** R4, R7, R8

#### Behaviour

- Given Hermes runs with provider `fly_io`, when a user creates or updates a recurring job, then Hermes preserves the job as scheduled and makes it available for Fly.io coordination.
- Given Hermes runs with provider `fly_io`, when a job is paused, resumed, deleted, or triggered manually, then Hermes keeps its visible job state consistent with the remote coordination state.
- Given Hermes is activated for a due Fly-managed job occurrence, when Hermes processes that occurrence, then the job executes using the normal Hermes scheduled-job execution path and records status and output in Hermes.
- Given the same Fly-managed due occurrence is triggered twice, when Hermes receives both triggers, then Hermes records at most one execution for that occurrence.
- Given a Fly-managed job execution completes, when the user lists or retrieves that job, then the job shows updated last-run state and next-run state in Hermes.

#### Verification

| Input | Expected output | Verified result |
|---|---|---|
| Provider `fly_io`, create recurring job `{"name":"hourly digest","schedule":"every 1h","prompt":"summarize status"}` | Job remains scheduled and ready for Fly.io coordination | |
| Provider `fly_io`, pause then resume a job | Job state changes correctly and remains schedulable | |
| Provider `fly_io`, trigger the same due occurrence twice | Exactly one run is recorded for that occurrence | |
| Provider `fly_io`, `POST /api/jobs/{id}/run` | Job is accepted for immediate execution without requiring new request fields | |

#### Not in scope

- Exactly-once guarantees across all distributed failure modes
- Support for non-Fly remote providers
- Remote provider discovery or installation

### Phase 4 - Reviewer-Safe Test Coverage And Release Readiness

**Status:** not started
**Ticket:** `codex/multi-scheduler-types`
**Fixes:** R1, R2, R3, R4, R5, R6, R7, R8

#### Behaviour

- Given Hermes is tested in its normal automated suite, when the scheduler-provider feature is added, then the default provider path proves that current behavior is unchanged.
- Given Hermes is tested in provider-selection scenarios, when the suite runs, then supported providers succeed and unsupported providers fail clearly.
- Given Hermes is tested through its existing job management surfaces, when the suite runs under `builtin` and `fly_io`, then the same user-visible job lifecycle behavior is verified for both.
- Given Hermes is tested for `fly_io`, when the normal suite runs, then all provider tests complete without real Fly.io credentials, real network calls, or long-lived external services.
- Given a reviewer evaluates the PR, when they inspect the test additions, then the tests extend Hermes's existing scheduler and jobs API suites rather than creating an isolated parallel test harness.

#### Verification

| Input | Expected output | Verified result |
|---|---|---|
| Full normal Hermes suite with default provider behavior covered | Existing built-in behavior remains green | |
| Test run with explicit `provider=builtin` and `provider=fly_io` cases | Shared lifecycle tests pass in both modes | |
| Test run with unsupported provider `banana` | Clear failure path verified | |
| `fly_io` provider tests in the normal suite | No real Fly.io API calls or credentials required | |
| Existing `/api/jobs` tests extended for provider behavior | Current API payloads remain backward-compatible | |

#### Not in scope

- Live Fly.io integration tests in the default suite
- Approval based on manual testing alone
- A new testing framework separate from Hermes's current pytest-based suite

## Constraints

- Use the existing branch `codex/multi-scheduler-types`
- Keep the first implementation limited to two concrete providers: `builtin` and `fly_io`
- Preserve current user-visible scheduled-job behavior unless this spec explicitly changes it
- Keep `/api/jobs` backward-compatible; provider selection must not require new request fields
- Keep the main test strategy aligned with current Hermes expectations: pytest-based, hermetic, and safe to run without real credentials or real Fly.io access
- The PR must extend Hermes's existing scheduler and jobs API tests so reviewers can see backward compatibility directly
- Each implementation slice should stay reviewable and small enough for one focused review

## Not In Scope

- **Per-job provider selection:** Deferred to keep the first provider abstraction small and backward-compatible
- **Third-party provider plugin system:** Deferred until the provider abstraction is proven with `builtin` and `fly_io`
- **New schedule syntax:** Deferred because existing schedule formats already cover required job definitions
- **Replacing Hermes as the source of truth for jobs:** Deferred because it would materially change the system model
- **Distributed exactly-once guarantees beyond duplicate-trigger protection:** Deferred because this requires a broader coordination design
- **Support for non-Fly remote providers:** Deferred until `fly_io` proves the provider interface is useful

## Appendix: Investigation Notes

### A1. Current Hermes scheduler model

Hermes currently has one scheduled-jobs model:

- jobs are created, updated, and stored in local scheduler state
- due jobs are discovered locally
- the scheduler executes jobs using one built-in execution path
- the API server exposes one set of job-management endpoints
- current clients do not send scheduler-provider information in requests

### A2. Current user-visible surfaces that must stay stable

The following user-visible behaviors already exist and should remain stable in the first provider PR:

- create a job
- list and retrieve jobs
- update a job
- pause and resume a job
- trigger immediate execution
- track last-run state and delivery outcome
- use one-shot, interval, and cron-expression schedules

### A3. Why this spec uses provider-only selection

This spec intentionally uses provider selection only:

- `builtin` means current Hermes scheduler behavior
- `fly_io` means Fly-aware scheduler coordination

This keeps the first PR concrete and avoids adding a second user-facing abstraction layer before there is evidence it is needed.

### A4. MR/PR test expectations

To avoid blocking review, the PR should prove:

- default behavior is unchanged for existing users
- `builtin` and `fly_io` share the same user-visible job lifecycle semantics
- current `/api/jobs` payloads remain valid
- `fly_io` behavior is covered in the normal hermetic test suite without real Fly.io integration

The expected test emphasis is on existing Hermes scheduler and jobs API suites, not on a new parallel testing harness.
