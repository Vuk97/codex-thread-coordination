# Native sender recovery

Read this when native messaging tools disappear after a reconnect. The helper
uses experimental local app-server methods. Inspect the live tool registry on
your version before sending.

## Check the capability before changing processes

1. Inspect the current catalog for `codex_tui.send_message_to_thread`.
2. Try normal reattachment to the existing task if appropriate.
3. Check whether an existing local TUI context exposes the sender.

The receiving thread and the TUI context used to call tools have separate IDs.
Discover both from the current app server. Keep the context alive while using
its native tools, and retain their normal approval requirements.

## Observed launch-mode difference

In the recorded **Codex 0.159.3** installation, explicit
`--remote unix://...` access exposed six read/status dynamic tools but omitted
the approval-gated native tool registration containing the sender, task
creation, and forking. Enabling `agent_message_board` did not restore it.
A normal local TUI launch, without `--remote` or `--no-daemon`, exposed all nine
native tools through the same app-server control socket.

This observation describes one version and installation. It is not a permanent
transport contract. A working `list_threads` result or healthy daemon does not
establish that the sender is registered in the selected context.

When authorized coordination requires a replacement context, launch a normal
local TUI from a fresh Terminal or PTY in a suitable working directory:

```bash
codex --no-alt-screen -C "$PWD"
```

Use that context for the authorized handoff. It is not a second implementation
assignment. If startup is blocked by a repository problem, use an appropriate
neutral working directory and identify artifact paths explicitly. Do not
restart active work or the daemon merely to add sender registration.

## Optional local helper

The helper calls the installed `codex_tui` MCP tools through a live context.
It does not implement its own message queue. It requires Python 3.10 or newer,
`websockets`, and access to the local Unix control socket.

From the repository or installed skill directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/codex_tui.py --context-thread CONTEXT_ID status
.venv/bin/python scripts/codex_tui.py --context-thread CONTEXT_ID list
.venv/bin/python scripts/codex_tui.py --context-thread CONTEXT_ID read --thread RECIPIENT_ID
```

Replace `CONTEXT_ID` and `RECIPIENT_ID` with IDs from your live registry. `status`
must show `send_message_to_thread`. Use the native thread list and read the
recipient before every send. The helper's CLI does not enforce that discovery
sequence on your behalf.

Write your authorized handoff to a local UTF-8 text file, then send it once:

```bash
.venv/bin/python scripts/codex_tui.py --context-thread CONTEXT_ID send \
  --thread RECIPIENT_ID --message-file handoff.txt
```

A successful response has this shape:

```json
{
  "senderAccepted": true,
  "recipientThreadId": "RECIPIENT_ID",
  "recipientActionVerified": false
}
```

The helper checks the live prompt limit and exact acknowledged recipient. It
waits up to 45 seconds for a send result and never automatically retries. A
timeout, interrupted send, or lost acknowledgment leaves delivery `UNKNOWN`.
Read the recipient's recent activity before deciding whether to retry. Absence
from an immediate read does not prove an in-flight handoff failed.

For pagination, copy the native cursor exactly:

```bash
.venv/bin/python scripts/codex_tui.py --context-thread CONTEXT_ID archived --cursor CURSOR
.venv/bin/python scripts/codex_tui.py --context-thread CONTEXT_ID read \
  --thread RECIPIENT_ID --cursor CURSOR
```

The default socket is under `${CODEX_HOME:-$HOME/.codex}/app-server-control/`.
Use `--socket /path/to/control.sock` if your local installation differs. If
access is restricted, use the runtime's normal narrow permission mechanism.
If no suitable context or socket is available, report the capability as blocked.

## Host failures are a separate diagnosis

If GUI applications also fail to open, check the host rather than assuming a
thread-routing problem. On macOS, a stale process can survive a WindowServer
restart with a dead `TASK_BOOTSTRAP_PORT`; its children inherit the broken GUI
service context.

Inspect saved thread activity before assuming a frozen terminal means work
stopped. If replacing a client is already authorized, verify that exact client
exited and resume the saved thread from the current desktop session. Account
for active work before a daemon restart, which can interrupt connected clients.
Discover and read each recipient again afterward. This guide grants no new
permission to stop processes or restart services.

Memory pressure calls for less local concurrency. Available agent slots do not
describe the host's memory capacity.
