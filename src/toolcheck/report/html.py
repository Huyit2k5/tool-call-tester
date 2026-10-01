"""Báo cáo HTML tĩnh một file (CSS nội tuyến, không JS, không cần server)."""

from __future__ import annotations

import json
from html import escape
from typing import Optional

from ..runner import Report
from ..trace import Trace

CSS = """
body{font:14px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:960px;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.4rem;margin-bottom:.2rem}.meta{color:#666;margin-bottom:1rem}
.badge{display:inline-block;padding:.1rem .6rem;border-radius:1rem;font-weight:600;color:#fff}
.pass{background:#1a7f37}.fail{background:#c62828}
.layer{border:1px solid #ddd;border-radius:6px;margin:.5rem 0;padding:.5rem .8rem}
.layer.bad{border-color:#c62828;background:#fff5f5}.layer ul{margin:.3rem 0 0 1.2rem;padding:0}
table{border-collapse:collapse;width:100%;margin-top:.5rem}
td,th{border-bottom:1px solid #eee;padding:.3rem .5rem;text-align:left;vertical-align:top}
tr.flag td{background:#fff5f5}code{font-family:ui-monospace,monospace;font-size:12px;word-break:break-all}
@media(prefers-color-scheme:dark){body{background:#111;color:#eee}.layer{border-color:#444}
.layer.bad,tr.flag td{background:#2a1515}td,th{border-color:#333}.meta{color:#aaa}}
"""


def _j(v) -> str:
    return escape(json.dumps(v, ensure_ascii=False)) if v is not None else ""


def to_html(report: Report, trace: Optional[Trace] = None) -> str:
    flagged = {f.step for fs in report.layers.values() for f in fs if f.step is not None}
    status = "pass" if report.passed else "fail"
    out = [f"<!doctype html><html lang=vi><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>toolcheck: {escape(report.name)}</title><style>{CSS}</style>",
           f"<h1>{escape(report.name)} <span class='badge {status}'>{status.upper()}</span></h1>",
           f"<div class=meta>{report.steps} bước · {report.tokens} token"
           + (f" · tiết kiệm được {report.tokens_saved} token nếu dừng khi phát hiện lặp" if report.tokens_saved else "")
           + "</div>"]
    for layer, findings in report.layers.items():
        if findings:
            items = "".join(f"<li>{escape(f.message)}" + (f" <em>(bước {f.step})</em>" if f.step is not None else "") + "</li>"
                            for f in findings)
            out.append(f"<div class='layer bad'><b>FAIL</b> · {escape(layer)}<ul>{items}</ul></div>")
        else:
            out.append(f"<div class=layer><b>PASS</b> · {escape(layer)}</div>")
    if trace is not None and len(trace):
        out.append("<h2>Trace</h2><table><tr><th>#<th>tool<th>args<th>kết quả / lỗi<th>token")
        for e in trace.events:
            res = f"<b>lỗi:</b> {escape(str(e.error))}" if e.error else _j(e.result)
            cls = " class=flag" if e.step in flagged else ""
            out.append(f"<tr{cls}><td>{e.step}<td>{escape(e.tool)}<td><code>{_j(e.args)}</code>"
                       f"<td><code>{res}</code><td>{e.tokens or ''}")
        out.append("</table>")
    return "".join(out) + "</html>"
