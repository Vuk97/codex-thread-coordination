# Contributing

Keep the skill focused on communication between existing Codex threads.
Scheduling, new-task creation, and project-specific authority belong to the
calling workflow.

For changes to the helper or installer, run:

```bash
python3 -m unittest discover -s tests -v
git diff --check
```

Tests use fake transports and temporary directories. They do not send messages
to live Codex sessions or replace installed skills.

Compatibility reports should include the Codex version, operating system,
launch mode, available tool names, and a minimal redacted error. Do not attach
raw conversations, real thread IDs, local home paths, private project names,
authentication data, or unredacted handoff files.

Document an observed version-specific recovery as an observation. Check the
live schema before treating it as a general rule. Keep sender acceptance,
recipient action, and artifact correctness separate in tests and documentation.
