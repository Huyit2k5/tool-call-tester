"""CLI:
  toolcheck run spec.json --trace trace.jsonl [--format openai|anthropic|mcp|otel] [--json F] [--junit F] [--state F]
  toolcheck convert --from openai|anthropic|mcp|otel input.json -o trace.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys

import importlib

from . import plugins, plugins_semantic, spec as spec_mod
from .adapters import ADAPTERS, convert, load_json_or_jsonl
from .report import to_json, to_terminal
from .report.html import to_html
from .report.junit import to_junit
from .runner import run
from .trace import Trace


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="toolcheck", description="Kiểm tra tool-call của agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="chạy spec trên trace")
    r.add_argument("spec")
    r.add_argument("--trace", required=True)
    r.add_argument("--json", metavar="FILE", help="ghi báo cáo JSON ra file")
    r.add_argument("--state", metavar="FILE", help="JSON trạng thái cuối để kiểm final_state")
    r.add_argument("--junit", metavar="FILE", help="ghi báo cáo JUnit XML")
    r.add_argument("--format", choices=sorted(ADAPTERS), help="định dạng của --trace nếu không phải JSONL chuẩn")
    r.add_argument("--html", metavar="FILE", help="ghi báo cáo HTML tĩnh một file")
    r.add_argument("--plugin", action="append", default=[], metavar="MODULE", help="module chứa checker @register (lặp được)")
    r.add_argument("--judge", metavar="MODULE:FUNC", help="hàm judge LLM cho plugin semantic_args")
    c = sub.add_parser("convert", help="chuyển log nền tảng về trace JSONL chuẩn")
    c.add_argument("input")
    c.add_argument("--from", dest="kind", required=True, choices=sorted(ADAPTERS))
    c.add_argument("-o", "--output", required=True)
    args = p.parse_args(argv)

    if args.cmd == "convert":
        try:
            trace = convert(args.kind, load_json_or_jsonl(args.input))
            trace.save(args.output)
        except (ValueError, OSError) as exc:
            print(f"lỗi: {exc}", file=sys.stderr)
            return 2
        print(f"converted {len(trace)} tool calls -> {args.output}")
        return 0

    try:
        for mod in args.plugin:
            plugins.load_module(mod)
        if args.judge:
            mod, _, func = args.judge.partition(":")
            try:
                plugins_semantic.set_judge(getattr(importlib.import_module(mod), func))
            except (ImportError, AttributeError) as exc:
                raise ValueError(f"--judge {args.judge}: {exc}") from exc
        spec = spec_mod.load(args.spec)
        if args.format:
            trace = convert(args.format, load_json_or_jsonl(args.trace))
        else:
            trace = Trace.load(args.trace)
        state = None
        if args.state:
            with open(args.state, encoding="utf-8") as f:
                state = json.load(f)
    except (spec_mod.SpecError, ValueError, OSError) as exc:  # JSONDecodeError là ValueError
        print(f"lỗi: {exc}", file=sys.stderr)
        return 2

    try:
        report = run(spec, trace, state)
    except ValueError as exc:  # gồm SpecError (plugin chưa đăng ký) và thiếu judge
        print(f"lỗi: {exc}", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    print(to_terminal(report))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(to_json(report))
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(to_html(report, trace))
    if args.junit:
        with open(args.junit, "w", encoding="utf-8") as f:
            f.write(to_junit(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
