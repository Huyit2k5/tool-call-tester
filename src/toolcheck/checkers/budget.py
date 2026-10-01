"""Checker ngân sách: số bước, tổng token, tổng thời gian."""

from __future__ import annotations

from ..trace import Trace


def check(trace: Trace, cfg: dict):
    from . import Finding

    findings = []
    if "max_steps" in cfg and len(trace) > cfg["max_steps"]:
        findings.append(Finding("budget", f"{len(trace)} bước vượt giới hạn {cfg['max_steps']}"))
    if "max_tokens" in cfg and trace.total_tokens > cfg["max_tokens"]:
        findings.append(Finding("budget", f"{trace.total_tokens} token vượt giới hạn {cfg['max_tokens']}"))
    if "max_seconds" in cfg and trace.duration > cfg["max_seconds"]:
        findings.append(Finding("budget", f"{trace.duration:.1f}s vượt giới hạn {cfg['max_seconds']}s"))
    return findings
