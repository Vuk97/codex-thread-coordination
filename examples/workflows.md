# Coordination examples

These examples use fictional thread names and repository-relative paths.
Discover the real thread IDs before sending. Start and assign the sessions
yourself, or through a separately authorized task-creation workflow.

## Implementation and review

An implementation thread owns `src/cache.py`. A review thread inspects the
completed change while implementation continues on independent work.

```text
Use $codex-thread-coordination to ask the Review thread to inspect the cache
invalidation change at the current commit in this worktree. Request concrete
defects with file locations and a reproducing test. Review only; I own edits.
```

The reviewer sends findings back through the native sender. The implementation
thread checks the cited code and reproduction before making changes.

## Shared contract between two worktrees

API and UI threads work in separate worktrees. The UI needs the API's response
contract before connecting its loading state.

```text
Use $codex-thread-coordination to ask API implementation for its response
schema, an example error payload, and the revision they belong to. UI changes
stay in my worktree. Ask it to reply here with paths I can read.
```

A schema path can unblock the UI without requiring the API thread to hand over
its working context or file ownership.

## A blocker belongs to another thread

```text
Use $codex-thread-coordination to tell Build investigation that the failing
test log is in artifacts/test-log.txt. Ask whether it matches the dependency
issue that thread is investigating. Request a diagnosis before any shared
configuration changes.
```

The receiving thread can use its existing investigation to answer. The sender
continues independent work while awaiting the response.

## A bounded handoff

Adapt this template to the task; every field is not required for every message.

```text
Request: Inspect the parser failure and return a minimal reproduction.
Artifact: artifacts/parser-failure.txt in the named implementation worktree.
Observed: The focused test rejects an empty input; normal input passes.
Boundary: Review only. Parser implementation retains ownership of edits.
Reply: Send the reproducing command and expected/actual result to this thread.
```

Keep the prompt within the live sender's byte limit. Identify the repository or
worktree when a relative path would be ambiguous. Include artifact identity
only when the recipient needs it to distinguish revisions.

## Optional repository rule

If cross-thread coordination is part of your normal project workflow, add a
rule like this to your own `AGENTS.md`:

```markdown
When the user requests coordination with another existing Codex session, use
the codex-thread-coordination skill. Discover and read the recipient before
each handoff, use the native sender, and check its acknowledgment. Verify
referenced artifacts before accepting the other thread's conclusions.
```

Installing the skill does not modify your repository rules automatically.
