# BackQuant AI CLI Design

Date: 2026-04-20
Status: Draft for review

## Goal

Design a first-version CLI for AI-assisted RQAlpha strategy development and debugging.

The CLI is AI-first, JSON-first, and intended to let an AI agent iterate on local strategy files while using the existing remote BackQuant service for compilation, execution, logs, and results.

## Scope

This design only covers the first CLI version for:

- RQAlpha strategy development and debugging
- Local Python strategy files as the source of truth
- Remote execution through the existing BackQuant HTTP API
- Minimal local state for job-to-file mapping

This design does not cover:

- Factor research workflows
- Notebook-driven AI workflows
- VnPy CTA workflows
- Multi-user conflict management
- Remote API changes
- Rich local project metadata or experiment tracking

## Requirements

- AI is the primary caller.
- The CLI should work as a local proxy tool.
- Remote BackQuant logic should remain unchanged.
- Strategy execution should use the existing remote flow:
  1. save strategy
  2. run strategy by `strategy_id`
  3. inspect job state, result, and log
- The local file is the development source of truth.
- The remote strategy is only an execution mirror of the local file.
- Command output defaults to JSON.
- The CLI should keep local state as simple as possible.

## Approaches Considered

### Approach A: Thin Remote API Wrapper

Expose the existing BackQuant HTTP API almost directly as CLI commands.

Pros:

- Fastest to build
- Minimal CLI behavior

Cons:

- Weak local-file workflow
- Poor AI ergonomics for strategy-file iteration
- No local job-to-file linkage

### Approach B: Local-Only CLI

Run everything locally from strategy files without using the remote BackQuant job system.

Pros:

- Simple runtime model
- No remote coordination

Cons:

- Breaks alignment with the existing BackQuant runtime
- Loses remote job history, logs, and results
- Conflicts with the preferred deployment model where AI and BackQuant may be separated

### Approach C: Local Proxy CLI Using Existing Remote APIs

The CLI works on local files, but uses the existing remote save/run/job APIs without changing remote logic.

Pros:

- Best fit for AI-driven file iteration
- Reuses current remote behavior
- Keeps job/result/log flow unchanged
- Minimal remote-side risk

Cons:

- Requires a small amount of local state
- Remote strategy IDs are derived from local file naming

### Recommendation

Choose Approach C.

It gives the AI a local-file-centered workflow while preserving the current BackQuant remote behavior and avoiding backend changes.

## Core Model

### Source of truth

- Local `.py` file is the authoritative strategy source.
- Remote strategy code is overwritten from the local file before each run.

### Remote strategy identity

- `strategy_id` is derived from the local file stem.
- Example: `foo.py -> foo`

The first version accepts this simple convention and does not attempt to solve same-name collisions across different directories.

### Remote job identity

- Jobs remain fully owned by the remote BackQuant system.
- CLI receives `job_id` from the remote service and does not invent an alternative task model.

### Local cache

The CLI stores a minimal local cache to map `job_id` back to the local file used when the job was launched.

Suggested file:

- `./.bq/jobs.json`

Suggested structure:

```json
{
  "jobs": {
    "job_20260420_001": {
      "file": "/abs/path/strategies/foo.py",
      "strategy_id": "foo",
      "recorded_at": "2026-04-20T10:30:00Z"
    }
  }
}
```

This cache is not authoritative. It is only a local convenience layer.

## Command Model

The first version exposes these commands:

- `bq strategy compile --file PATH`
- `bq strategy run --file PATH --start YYYY-MM-DD --end YYYY-MM-DD [--cash ...] [--benchmark ...] [--frequency ...]`
- `bq strategy pull --file PATH`
- `bq job show --job-id ID`
- `bq job result --job-id ID`
- `bq job log --job-id ID`

## Command Behavior

### `bq strategy compile --file PATH`

Behavior:

1. Read the local file.
2. Derive `strategy_id` from `PATH.stem`.
3. Call the existing remote compile API using temporary code in the request body.
4. Return JSON.

Notes:

- This command does not overwrite the remote saved strategy.
- This command is intended for syntax and dependency checks before run.

### `bq strategy run --file PATH ...`

Behavior:

1. Read the local file.
2. Derive `strategy_id` from `PATH.stem`.
3. Call the existing remote save strategy API to overwrite the remote strategy with local code.
4. Call the existing remote run API using that `strategy_id`.
5. Receive `job_id`.
6. Write `job_id -> file` into `./.bq/jobs.json`.
7. Return JSON.

Notes:

- This command is effectively `save -> run`.
- No separate publish step exists in version 1.
- The remote strategy is treated as the current executable mirror of the local file.

### `bq strategy pull --file PATH`

Behavior:

1. Derive `strategy_id` from `PATH.stem`.
2. Fetch the current remote strategy code.
3. Overwrite the local file with the remote code.
4. Return JSON.

Notes:

- This command is intended for synchronization or recovery.
- In version 1, no merge behavior is provided.

### `bq job show --job-id ID`

Behavior:

1. Query the existing remote job status endpoint.
2. Look up local file mapping from `./.bq/jobs.json`.
3. Return JSON containing the local file mapping and raw remote response.

### `bq job result --job-id ID`

Behavior:

1. Query the existing remote result endpoint.
2. Look up local file mapping from `./.bq/jobs.json`.
3. Return JSON containing the local file mapping and raw remote response.

The first version intentionally uses remote passthrough instead of CLI-side summarization.

### `bq job log --job-id ID`

Behavior:

1. Query the existing remote log endpoint.
2. Look up local file mapping from `./.bq/jobs.json`.
3. Return JSON containing the local file mapping and raw remote response.

## JSON Contracts

### Run success

```json
{
  "ok": true,
  "data": {
    "job_id": "job_20260420_001",
    "file": "/abs/path/strategies/foo.py",
    "strategy_id": "foo",
    "status": "QUEUED"
  }
}
```

### Run failure

```json
{
  "ok": false,
  "error": {
    "code": "REMOTE_ERROR",
    "message": "strategy not found"
  }
}
```

### Compile success

```json
{
  "ok": true,
  "data": {
    "file": "/abs/path/strategies/foo.py",
    "strategy_id": "foo",
    "compile": {
      "ok": true,
      "stdout": "syntax check passed\ndependency check passed",
      "stderr": "",
      "diagnostics": []
    }
  }
}
```

### Compile failure

```json
{
  "ok": false,
  "error": {
    "code": "COMPILE_ERROR",
    "message": "syntax error",
    "details": {
      "file": "/abs/path/strategies/foo.py",
      "strategy_id": "foo",
      "stdout": "",
      "stderr": "SyntaxError: invalid syntax",
      "diagnostics": [
        {
          "line": 12,
          "column": 8,
          "level": "error",
          "message": "invalid syntax"
        }
      ]
    }
  }
}
```

### Job command success shape

```json
{
  "ok": true,
  "data": {
    "job_id": "job_20260420_001",
    "file": "/abs/path/strategies/foo.py",
    "strategy_id": "foo",
    "remote": {}
  }
}
```

If the local cache does not contain the mapping, `file` should be `null`.

## Error Handling

Suggested CLI exit codes:

- `0`: success
- `2`: CLI argument error
- `3`: local file or local cache error
- `4`: remote request failure or remote business error

The CLI should always prefer structured JSON output over human-oriented text.

## Data Flow

### Compile flow

1. local file read
2. derive `strategy_id`
3. send temporary code to remote compile API
4. return structured compile output

### Run flow

1. local file read
2. derive `strategy_id`
3. overwrite remote strategy code
4. request remote run
5. receive `job_id`
6. update local cache
7. return structured run output

### Job flow

1. query remote endpoint
2. read local cache
3. return local mapping plus remote payload

## Testing Strategy

Version 1 should be verified with:

- file stem to `strategy_id` derivation
- local file read errors
- local cache creation and update
- remote compile passthrough
- remote save then run flow
- job mapping lookup
- missing local cache entries
- JSON output stability

The first version should prefer a small set of deterministic CLI tests over broad integration scope.

## Risks and Tradeoffs

### Same-name file collisions

Two different files with the same stem map to the same remote `strategy_id`.

Version 1 accepts this tradeoff for simplicity.

### Remote strategy overwrite semantics

Running a local file overwrites the remote strategy every time.

This is intentional in version 1 because the remote strategy acts as an execution mirror, not a separately curated artifact.

### Local cache incompleteness

If `./.bq/jobs.json` is lost or incomplete, job queries still work remotely, but the CLI may not be able to report the originating local file.

This is acceptable because the cache is non-authoritative.

## Explicit Non-Goals

Version 1 does not include:

- factor evaluation commands
- notebook orchestration
- publish/promote workflow
- remote strategy naming prefixes
- directory-aware conflict handling
- CLI-side result summarization
- local experiment database
- bidirectional sync conflict resolution

## Next Step

After this design is reviewed and approved, the next artifact should be an implementation plan for the CLI package structure, API client layer, cache module, and command handlers.
