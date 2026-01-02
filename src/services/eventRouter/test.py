#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(2)


DEFAULT_TOPICS = [
    "input.raw.extracted",
    "audio.raw.extracted",
    "text.synthesis.input",
    "audio.synthesis.input",
    "text.synthesis.output",
    "text.group.synthesis.input",
    "text.group.synthesis.output",
    "audio.generated",
    "dead-letter",
    "pipeline-output",
    "task-status",
]

# Topic -> expected worker app label
TOPIC_TO_APP = {
    "input.raw.extracted": "input-extraction",
    "audio.raw.extracted": "audio-to-text",
    "text.synthesis.input": "text-synthesizer",
    "text.group.synthesis.input": "text-synthesizer",
    "task-status": "sync-manager",
    "pipeline-output": "sync-manager",
}

# app -> (k8s service name, service port)
APP_TO_SERVICE = {
    "input-extraction": ("input-extraction-service", 8081),
    "audio-to-text": ("audio-to-text-service", 8080),
    "text-synthesizer": ("text-synthesizer-service", 8083),
    "sync-manager": ("sync-manager-service", 8082),
    # "tts": ("tts-service", 8084),  # if enabled
}

# Expected substring in GET / response body
# Adjust these to match your handlers exactly.
APP_EXPECT_SUBSTR = {
    "input-extraction": 'input extraction, "/"',
    "audio-to-text": 'audio to text, "/"',
    "text-synthesizer": 'text synthesizer, "/"',
    "sync-manager": 'sync manager, "/"',
}


def sh(cmd: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_payload(topic: str, run_id: int, via: str = "http") -> Dict:
    return {"run_id": run_id, "test": "ok", "topic": topic, "ts": now_iso(), "via": via}


def send_event(
    router_url: str,
    router_path: str,
    topic: str,
    payload: Dict,
    mode: str,
    timeout_s: int,
) -> requests.Response:
    """
    mode:
      - "object": {"name": "<topic>", "payload": {...}}
      - "string": {"name": "<topic>", "payload": "<json-string>"}
      - "raw": send payload as-is
    """
    url = router_url.rstrip("/") + "/" + router_path.lstrip("/")

    if mode == "object":
        body = {"name": topic, "payload": payload}
    elif mode == "string":
        body = {"name": topic, "payload": json.dumps(payload)}
    elif mode == "raw":
        body = payload
    else:
        raise ValueError(f"unknown mode: {mode}")

    return requests.post(url, json=body, timeout=timeout_s)


class PortForward:
    def __init__(self, namespace: str, svc_name: str, local_port: int, remote_port: int):
        self.namespace = namespace
        self.svc_name = svc_name
        self.local_port = local_port
        self.remote_port = remote_port
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        cmd = [
            "kubectl",
            "-n",
            self.namespace,
            "port-forward",
            f"svc/{self.svc_name}",
            f"{self.local_port}:{self.remote_port}",
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        deadline = time.time() + 12
        output = ""
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"port-forward exited early for {self.svc_name}: {output}")
            line = self.proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            output += line
            if "Forwarding from" in line:
                return

        raise RuntimeError(f"port-forward not ready for {self.svc_name}. Output:\n{output}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def verify_service_root_http(app: str, local_port: int) -> Tuple[bool, int, str]:
    """
    GET / and assert response contains expected substring.
    Returns: (ok, status_code, response_snippet)
    """
    expected = APP_EXPECT_SUBSTR.get(app)
    if not expected:
        return False, 0, f"no expected substring configured for app={app}"

    url = f"http://127.0.0.1:{local_port}/"
    try:
        r = requests.get(url, timeout=5)
        body = (r.text or "").replace("\n", " ").strip()
        ok = (r.status_code == 200) and (expected in body)
        return ok, r.status_code, body[:200]
    except Exception as e:
        return False, 0, str(e)


def print_summary(results: List[Dict]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.get("ok"))
    failed = total - passed
    pass_rate = (passed / total * 100) if total else 0.0

    print("\n" + "=" * 110)
    print("PIPELINE TEST SUMMARY")
    print("=" * 110)
    print(f"TOTAL EVENTS : {total}")
    print(f"PASSED       : {passed}")
    print(f"FAILED       : {failed}")
    print(f"PASS RATE    : {pass_rate:.2f}%")
    print("=" * 110)
    print(f"{'STATUS':6} {'TOPIC':26} {'SERVICE':18} {'ROUTER':6} {'HTTP':6} RESPONSE/ERROR")
    print("-" * 110)

    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        topic = r.get("topic", "-")
        service = r.get("service", "-")
        router_code = str(r.get("router_status") or "-")
        http_code = str(r.get("http_status") or "-")
        resp = (r.get("detail") or "").replace("\n", " ")
        print(f"{status:6} {topic:26} {service:18} {router_code:6} {http_code:6} {resp}")

    print("=" * 110)


def main():
    ap = argparse.ArgumentParser(
        description="Send pipeline events to eventRouter and verify microservices respond on GET / with expected text."
    )
    ap.add_argument(
        "--router-url",
        default=os.getenv("EVENT_ROUTER_URL", "http://localhost:8085"),
        help="Base URL of eventRouter (default: http://localhost:8085 or EVENT_ROUTER_URL)",
    )
    ap.add_argument(
        "--router-path",
        default=os.getenv("EVENT_ROUTER_PATH", "/event"),
        help="Path to POST events to (default: /event or EVENT_ROUTER_PATH)",
    )
    ap.add_argument(
        "--mode",
        choices=["object", "string", "raw"],
        default=os.getenv("EVENT_ROUTER_MODE", "object"),
        help="Body format to send (default: object)",
    )
    ap.add_argument("--topics", default=",".join(DEFAULT_TOPICS), help="Comma-separated topics to send")
    ap.add_argument("--count", type=int, default=1, help="How many rounds to send (default: 1)")
    ap.add_argument("--sleep-between", type=float, default=0.2, help="Seconds between sends (default: 0.2)")
    ap.add_argument(
        "--verify",
        choices=["http", "none"],
        default="http",
        help="Verification method (default: http)",
    )
    ap.add_argument(
        "--services-namespace",
        default=os.getenv("SERVICES_NAMESPACE", "default"),
        help="K8s namespace where microservices run (default: default or SERVICES_NAMESPACE)",
    )
    ap.add_argument("--router-timeout", type=int, default=10, help="HTTP timeout seconds (default: 10)")
    ap.add_argument("--wait-after", type=float, default=0.7, help="Seconds to wait after sending before verify")

    args = ap.parse_args()

    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    if not topics:
        print("No topics provided.", file=sys.stderr)
        sys.exit(2)

    # Ensure kubectl is available if verifying via HTTP (we port-forward)
    if args.verify == "http":
        rc, _, _ = sh(["kubectl", "version", "--client"], timeout=10)
        if rc != 0:
            print("kubectl not available; cannot port-forward services for HTTP verification.", file=sys.stderr)
            sys.exit(2)

    # Determine which apps are needed for selected topics
    apps_needed = sorted({TOPIC_TO_APP[t] for t in topics if t in TOPIC_TO_APP})
    forwards: List[PortForward] = []
    app_to_local_port: Dict[str, int] = {}
    local_port_base = 18080

    results: List[Dict] = []

    try:
        # Start port-forwards
        if args.verify == "http":
            for idx, app in enumerate(apps_needed):
                if app not in APP_TO_SERVICE:
                    continue
                svc, remote_port = APP_TO_SERVICE[app]
                local_port = local_port_base + idx
                pf = PortForward(args.services_namespace, svc, local_port, remote_port)
                print(f"[PF] starting port-forward app={app} svc={svc} {local_port}:{remote_port}")
                pf.start()
                forwards.append(pf)
                app_to_local_port[app] = local_port

        for round_idx in range(args.count):
            for i, topic in enumerate(topics):
                run_id = int(time.time() * 1_000_000_000) + (round_idx * 10_000) + i
                payload = build_payload(topic, run_id, via="http")

                app = TOPIC_TO_APP.get(topic)  # may be None
                record = {
                    "topic": topic,
                    "service": app or "-",
                    "run_id": run_id,
                    "router_status": None,
                    "http_status": None,
                    "ok": False,
                    "detail": "",
                }

                print(f"[SEND] topic={topic} run_id={run_id} -> {args.router_url}{args.router_path}")
                try:
                    resp = send_event(args.router_url, args.router_path, topic, payload, args.mode, args.router_timeout)
                    record["router_status"] = resp.status_code
                    record["detail"] = (resp.text or "")[:200]
                    print(f"[SEND] status={resp.status_code} resp={record['detail']}")
                except Exception as e:
                    record["detail"] = f"router send failed: {e}"
                    print(f"[SEND][ERROR] topic={topic} run_id={run_id} err={e}", file=sys.stderr)
                    results.append(record)
                    time.sleep(args.sleep_between)
                    continue

                time.sleep(args.wait_after)

                if args.verify == "none":
                    record["ok"] = True
                    results.append(record)
                    time.sleep(args.sleep_between)
                    continue

                if args.verify == "http":
                    if not app or app not in app_to_local_port:
                        record["detail"] = f"no app mapping/port-forward for topic={topic}"
                        results.append(record)
                        time.sleep(args.sleep_between)
                        continue

                    ok, http_status, body = verify_service_root_http(app, app_to_local_port[app])
                    record["http_status"] = http_status
                    record["ok"] = ok
                    if ok:
                        record["detail"] = body
                    else:
                        expected = APP_EXPECT_SUBSTR.get(app, "<missing expected>")
                        record["detail"] = f"{body} | expected_substring={expected}"

                    results.append(record)
                    time.sleep(args.sleep_between)

        print_summary(results)

        # Exit non-zero if any failures
        if args.verify != "none":
            total = len(results)
            passed = sum(1 for r in results if r.get("ok"))
            if passed != total:
                sys.exit(1)

    finally:
        for pf in forwards:
            pf.stop()


if __name__ == "__main__":
    main()
