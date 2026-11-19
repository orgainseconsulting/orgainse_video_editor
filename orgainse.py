"""Submit and follow a production on the local studio from a terminal or Codex."""

import argparse
import http.client
import json
import sys
import time
from pathlib import Path


class Client:
    def __init__(self, port):
        self.port = port

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=600)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            reply = connection.getresponse()
            data = json.load(reply)
            if reply.status >= 400:
                raise ValueError(data.get("error", f"Studio returned {reply.status}"))
            return data
        finally:
            connection.close()

    def asset(self, filename):
        path = Path(filename)
        headers = {
            "X-Orgainse-Studio": "1",
            "X-File-Extension": path.suffix,
            "Content-Length": str(path.stat().st_size),
        }
        with path.open("rb") as stream:
            return self.request("POST", "/api/assets", stream, headers)["asset"]

    def wait(self, state):
        last = None
        while state["status"] in ("queued", "running"):
            if state["step"] != last:
                print(state["step"], file=sys.stderr, flush=True)
                last = state["step"]
            time.sleep(2)
            state = self.request("GET", "/api/jobs/" + state["id"])
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("list")
    status = sub.add_parser("status")
    status.add_argument("id")
    status.add_argument("--wait", action="store_true")
    for mode in ("create", "shorts"):
        cmd = sub.add_parser(mode)
        cmd.add_argument("--title", required=True)
        cmd.add_argument("--brief", default="")
        cmd.add_argument("--video", required=mode == "shorts")
        cmd.add_argument("--transcript")
        cmd.add_argument(
            "--ratio",
            choices=["16:9", "9:16", "4:5", "1:1"],
            default="9:16" if mode == "shorts" else "16:9",
        )
        cmd.add_argument("--seconds", type=int, default=30)
        cmd.add_argument("--draft", action="store_true")
        cmd.add_argument("--no-burn", action="store_true")
        cmd.add_argument("--wait", action="store_true")
        if mode == "create":
            cmd.add_argument("--url")
            cmd.add_argument("--image")
            cmd.add_argument("--script", type=Path, help="UTF-8 narration text file")
            cmd.add_argument("--planner", choices=["model", "template"], default="model")
        else:
            cmd.add_argument("--count", type=int, default=3)
            cmd.add_argument("--trim", nargs=2, type=float, metavar=("START", "END"))
    args = parser.parse_args()
    client = Client(args.port)
    if args.command in ("doctor", "list"):
        data = client.request("GET", "/api/" + ("status" if args.command == "doctor" else "jobs"))
    elif args.command == "status":
        data = client.request("GET", "/api/jobs/" + args.id)
    else:
        req = {
            "mode": args.command,
            "title": args.title,
            "brief": args.brief,
            "ratio": args.ratio,
            "seconds": args.seconds,
            "draft": args.draft,
            "captions": not args.no_burn,
        }
        for flag, key in [("video", "media"), ("image", "image"), ("transcript", "transcript")]:
            if path := getattr(args, flag, None):
                req[key] = client.asset(path)
        for flag in ("url", "count", "planner", "trim"):
            if getattr(args, flag, None) is not None:
                req[flag] = getattr(args, flag)
        if path := getattr(args, "script", None):
            req["script"] = path.read_text(encoding="utf-8-sig")
        data = client.request(
            "POST",
            "/api/jobs",
            json.dumps(req).encode(),
            {"Content-Type": "application/json", "X-Orgainse-Studio": "1"},
        )
    if getattr(args, "wait", False):
        data = client.wait(data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return int(isinstance(data, dict) and data.get("status") in ("failed", "interrupted"))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        sys.exit(str(exc))
