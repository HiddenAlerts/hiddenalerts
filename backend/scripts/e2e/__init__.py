"""Production end-to-end test harness.

Read-only by default. Every module here is written on the assumption that it may
one day be pointed at production by a tired person at the end of a deployment,
so the safe thing is always the default and mutation always costs several
deliberate keystrokes.

Credentials come from the environment only. Tokens live in process memory only.
Nothing here writes a credential, a token or an ``Authorization`` header to disk.
"""
