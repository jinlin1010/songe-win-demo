# songe-win-demo

Minimal reproducible Windows E2E demo for [`sous-labs/songe`](https://github.com/sous-labs/songe):

1. Starts a local OpenAI-compatible mock upstream on `127.0.0.1` (zero API cost).
2. Runs `songe init` against an isolated `--data-dir` and `opencode.json`.
3. Sends `/v1/models` and `/v1/chat/completions` traffic through Songe's Windows service proxy (`127.0.0.1:7613/v1`).
4. Verifies `songe status` and cleans up cleanly with `songe uninstall --purge --yes` (safe even under non-UTF8 Windows stdio encodings such as `gbk`/`cp1252` via [PR #183](https://github.com/sous-labs/songe/pull/183)).

## Run

```powershell
uv run python demo.py
```
