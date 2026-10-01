from xml.etree import ElementTree as ET

from ..runner import Report


def to_junit(report: Report) -> str:
    fails = sum(1 for v in report.layers.values() if v)
    suite = ET.Element("testsuite", name=report.name, tests=str(len(report.layers)), failures=str(fails))
    for layer, findings in report.layers.items():
        case = ET.SubElement(suite, "testcase", classname=report.name, name=layer)
        if findings:
            f = ET.SubElement(case, "failure", message=f"{len(findings)} lỗi ở lớp {layer}")
            f.text = "\n".join(
                x.message + (f" (bước {x.step})" if x.step is not None else "") for x in findings)
    return ET.tostring(suite, encoding="unicode", xml_declaration=False)
