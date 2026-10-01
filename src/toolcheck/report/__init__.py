import json

from ..runner import Report


def to_json(report: Report) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def to_terminal(report: Report) -> str:
    lines = [f"toolcheck: {report.name} ({report.steps} bước, {report.tokens} token)"]
    for layer, findings in report.layers.items():
        if findings:
            lines.append(f"  [FAIL] {layer}")
            for f in findings:
                at = f" (bước {f.step})" if f.step is not None else ""
                lines.append(f"         - {f.message}{at}")
        else:
            lines.append(f"  [PASS] {layer}")
    if report.tokens_saved:
        lines.append(f"  Nếu dừng ngay khi phát hiện vòng lặp: tiết kiệm {report.tokens_saved} token")
    lines.append("KẾT QUẢ: " + ("PASS" if report.passed else "FAIL"))
    return "\n".join(lines)
