#!/usr/bin/env python3
"""Browser-level accessibility and responsive smoke checks for the SPA.

The script uses Chrome DevTools Protocol directly so it can run without a
Node/Playwright project. It verifies the hardening checks that matter most for
this app: labelled login controls, keyboard-safe modal state, locale switching,
unknown-view recovery, admin support queue visibility, and mobile overflow.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    import requests
    import websocket
except Exception as exc:  # pragma: no cover - operator setup failure
    raise SystemExit(
        "Missing Python packages for browser smoke. Install requests and websocket-client."
    ) from exc


def _chrome_path() -> str:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise SystemExit("Chrome/Chromium was not found. Set CHROME_BIN or install Chrome.")


class CDP:
    def __init__(self, ws_url: str) -> None:
        self._ws = websocket.create_connection(ws_url, timeout=5)
        self._seq = 0

    def cmd(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._seq += 1
        ident = self._seq
        self._ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == ident:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expression: str, await_promise: bool = False) -> Any:
        result = self.cmd(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
        ).get("result", {})
        return result.get("value")


def _wait_for(predicate, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            if predicate():
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for browser condition.")


def run(args: argparse.Namespace) -> None:
    user_data = tempfile.mkdtemp(prefix="compliant-parser-chrome-")
    chrome = args.chrome_bin or _chrome_path()
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            f"--remote-debugging-port={args.debug_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_data}",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        version_url = f"http://127.0.0.1:{args.debug_port}/json/version"
        _wait_for(lambda: requests.get(version_url, timeout=0.25).ok)
        target = requests.put(f"http://127.0.0.1:{args.debug_port}/json/new?{args.url}").json()
        cdp = CDP(target["webSocketDebuggerUrl"])
        cdp.cmd("Page.enable")
        cdp.cmd("Runtime.enable")

        for width, height in ((360, 800), (768, 1024), (1280, 800)):
            cdp.cmd(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 768},
            )
            cdp.cmd("Page.navigate", {"url": args.url})
            _wait_for(lambda: cdp.eval("document.readyState") == "complete")
            overflow = cdp.eval("document.documentElement.scrollWidth > window.innerWidth + 1")
            if overflow:
                raise RuntimeError(f"Horizontal overflow detected at {width}x{height}.")

        login_a11y = cdp.eval(
            """
            Boolean(
              document.querySelector("label[for='loginUser']") &&
              document.querySelector("label[for='loginPassword']") &&
              document.getElementById('loginNotice').getAttribute('aria-live') &&
              document.getElementById('loginForm').getAttribute('novalidate') !== null
            )
            """
        )
        if not login_a11y:
            raise RuntimeError("Login labels/live-region smoke failed.")

        cdp.eval(
            f"""
            document.getElementById('loginUser').value={json.dumps(args.username)};
            document.getElementById('loginPassword').value={json.dumps(args.password)};
            document.getElementById('loginForm').dispatchEvent(new Event('submit', {{bubbles:true, cancelable:true}}));
            """
        )
        _wait_for(lambda: cdp.eval("document.getElementById('loginScreen').classList.contains('mode-hidden')"))

        locale_ok = cdp.eval(
            """
            applyLocale('hi');
            const ok = document.documentElement.lang === 'hi' &&
              !document.querySelector('#caseNewBtn .btn-label').textContent.includes('New Case') &&
              !document.querySelector("button[data-tab='adminTabKB']").textContent.includes('Knowledge Base');
            applyLocale('en');
            ok && document.documentElement.lang === 'en';
            """
        )
        if not locale_ok:
            raise RuntimeError("Operational locale smoke failed.")

        not_found_ok = cdp.eval(
            """
            navigateTo('invalid-smoke-view');
            Boolean(document.getElementById('notFoundView').classList.contains('is-active') &&
              document.getElementById('notFoundBody').textContent.length > 20)
            """
        )
        if not not_found_ok:
            raise RuntimeError("Not-found fallback smoke failed.")

        modal_ok = cdp.eval(
            """
            new Promise(resolve => {
              openProfileModal();
              setTimeout(() => {
                const modal = document.getElementById('profileModal');
                const card = modal.querySelector('[role=dialog]');
                const openOk = modal.getAttribute('aria-hidden') === 'false' &&
                  card.getAttribute('aria-modal') === 'true' &&
                  modal.contains(document.activeElement);
                closeProfileModal();
                setTimeout(() => resolve(openOk && modal.getAttribute('aria-hidden') === 'true'), 20);
              }, 40);
            })
            """,
            await_promise=True,
        )
        if not modal_ok:
            raise RuntimeError("Modal accessibility smoke failed.")

        support_ok = cdp.eval(
            """
            new Promise(async resolve => {
              const create = await fetch('/api/auth/support-request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({request_type:'access_request', user_identifier:'smoke-officer'})
              });
              if (!create.ok) return resolve(false);
              navigateTo('admin');
              await new Promise(r => setTimeout(r, 300));
              const btn = document.querySelector("button[data-tab='adminTabSupport']");
              if (!btn) return resolve(false);
              btn.click();
              const deadline = Date.now() + 5000;
              const poll = () => {
                const text = document.getElementById('supportRequestList').textContent || '';
                if (text.includes('smoke-officer')) return resolve(true);
                if (Date.now() > deadline) return resolve(false);
                setTimeout(poll, 100);
              };
              poll();
            })
            """,
            await_promise=True,
        )
        if not support_ok:
            raise RuntimeError("Admin support queue smoke failed.")

        print("UI accessibility/responsive smoke passed.")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(user_data, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="password123")
    parser.add_argument("--debug-port", type=int, default=9223)
    parser.add_argument("--chrome-bin", default=None)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
