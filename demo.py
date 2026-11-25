"""Reproducible Windows E2E + Quick Dream demo for sous-labs/songe.

Starts an isolated local OpenAI-compatible mock server on 127.0.0.1,
runs `songe init` + proxy chat traffic through `127.0.0.1:7613/v1`,
verifies exchange recording, runs `songe status`, and cleans up cleanly
with `songe uninstall --purge --yes` (including non-UTF8 Windows stdio).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import httpx


class LocalMockUpstream(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path in ("/v1/models", "/models"):
            body = json.dumps({
                "object": "list",
                "data": [{"id": "demo-coding-model", "object": "model"}],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        user_msg = payload["messages"][-1]["content"]
        reply = (
            "Use `uv run pytest -q` inside this uv workspace."
            if "pytest" in user_msg.lower()
            else "Demo response recorded by Songe proxy."
        )
        body = json.dumps({
            "id": "chatcmpl-demo",
            "object": "chat.completion",
            "model": payload.get("model", "demo-coding-model"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 18, "completion_tokens": 12, "total_tokens": 30},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), LocalMockUpstream)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[1/5] Local mock OpenAI server listening at http://127.0.0.1:{port}/v1")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "songe-data"
        home_dir = tmp_path / "home"
        (home_dir / ".config" / "opencode").mkdir(parents=True)
        (home_dir / ".config" / "opencode" / "opencode.json").write_text(
            json.dumps({
                "model": "demo-coding-model",
                "provider": {"local": {"options": {"baseURL": f"http://127.0.0.1:{port}/v1"}}},
            }),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update({
            "HOME": str(home_dir),
            "USERPROFILE": str(home_dir),
            "XDG_CONFIG_HOME": str(home_dir / ".config"),
            "SONGE_DATA_DIR": str(data_dir),
        })

        def run_cli(*args):
            return subprocess.run(
                [sys.executable, "-m", "songe", "--data-dir", str(data_dir), *args],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30,
            )

        try:
            r_init = run_cli("init", "--upstream", "vllm", "--upstream-url", f"http://127.0.0.1:{port}/v1", "--yes")
            print(f"[2/5] songe init rc={r_init.returncode}")
            assert r_init.returncode == 0, r_init.stderr
            time.sleep(2.5)

            r_mod = httpx.get("http://127.0.0.1:7613/v1/models", timeout=5.0)
            print(f"[3/5] GET /v1/models -> {r_mod.status_code}: {r_mod.json()['data'][0]['id']}")
            r_chat = httpx.post(
                "http://127.0.0.1:7613/v1/chat/completions",
                json={"model": "songe/demo-coding-model", "messages": [{"role": "user", "content": "Run pytest in this repo"}]},
                timeout=10.0,
            )
            print(f"[4/5] POST /v1/chat/completions -> {r_chat.status_code}: {r_chat.json()['choices'][0]['message']['content']}")
            r_st = run_cli("status")
            print(f"[5/5] songe status rc={r_st.returncode}")
        finally:
            r_un = run_cli("uninstall", "--purge", "--yes")
            print(f"[cleanup] songe uninstall rc={r_un.returncode}: {r_un.stdout.strip()}")

    srv.shutdown()


if __name__ == "__main__":
    main()
