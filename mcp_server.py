#!/usr/bin/env python3
"""Sudhaar as an MCP server (stdio, JSON-RPC 2.0, one message per line). Stdlib only.

Tools: sudhaar_check (static scan of a path or pasted code), sudhaar_verify (live 400/200 proof),
sudhaar_fix (returns the diff; writes the files only when apply=true).
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sudhaar as sd

TARGET = {"type": "object", "properties": {
    "path": {"type": "string", "description": "File or folder to check"},
    "code": {"type": "string", "description": "Or: code pasted directly"},
}}
TOOLS = [
    {"name": "sudhaar_check", "description": "Find Sarvam API calls (models, voices, pace, language codes) that Sarvam's live API rejects today.",
     "inputSchema": TARGET},
    {"name": "sudhaar_verify", "description": "Prove each finding against Sarvam's live API: the current value (expect 400) and the fix (expect 200). Needs SARVAM_API_KEY.",
     "inputSchema": TARGET},
    {"name": "sudhaar_fix", "description": "Return a unified diff that fixes every finding. Writes the files only when apply is true.",
     "inputSchema": {**TARGET, "properties": {**TARGET["properties"], "apply": {"type": "boolean", "default": False}}}},
]


def target(args):
    if args.get("code"):
        root = Path(tempfile.mkdtemp(prefix="sudhaar-mcp-"))
        (root / ("snippet.js" if "function" in args["code"] or "const " in args["code"] else "snippet.py")).write_text(args["code"])
        return root
    p = Path(args.get("path", ".")).expanduser()
    if not p.exists():
        raise ValueError(f"No such file or folder: {p}")
    return p


def report(issues, root):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):  # stdout is the MCP channel, so capture the CLI's printing
        sd.report(issues, str(root))
    return buf.getvalue()


def call(name, args):
    root = target(args)
    if name == "sudhaar_check":
        return report(sd.scan(root), root)
    if name == "sudhaar_verify":
        if not os.environ.get("SARVAM_API_KEY"):
            raise ValueError("Set SARVAM_API_KEY in the MCP server's env to verify live")
        issues = sd.scan(root)
        sd.verify(issues)
        return report(issues, root)
    if name == "sudhaar_fix":
        work = root
        if not args.get("apply"):  # preview on a copy, never touch the user's files
            work = Path(tempfile.mkdtemp(prefix="sudhaar-mcp-fix-")) / root.name
            (shutil.copytree if root.is_dir() else shutil.copy)(root, work)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sd.apply_fixes(sd.scan(work))
        return buf.getvalue() or "Nothing to fix."
    raise ValueError(f"Unknown tool {name}")


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "sudhaar", "version": "1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = msg.get("params", {})
        try:
            result = {"content": [{"type": "text", "text": call(p.get("name"), p.get("arguments") or {})}]}
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    elif mid is None:
        return None  # notifications (e.g. notifications/initialized) get no reply
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


if __name__ == "__main__":
    for line in sys.stdin:
        if line.strip():
            reply = handle(json.loads(line))
            if reply is not None:
                print(json.dumps(reply), flush=True)
