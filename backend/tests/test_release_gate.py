"""The release gate rejects missing/skipped mandatory execution evidence."""

import json
import xml.etree.ElementTree as ET

import pytest

from scripts.verify_release import GATES, ROOT, assess


@pytest.fixture
def reports(tmp_path):
    config = json.loads((ROOT / "backend/src/features/matching/semantic_config.json").read_text(encoding="utf-8"))
    for name, (pattern, count, required) in GATES.items():
        for index in range(count):
            suite = ET.Element("testsuite")
            properties = ET.SubElement(suite, "properties")
            if name == "mysql":
                for key, value in {"BE10.database": "mysql", "BE10.databaseVersion": "8.4.7"}.items():
                    ET.SubElement(properties, "property", name=key, value=value)
            if name == "actualModel":
                for key in ("model", "modelVersion", "revision"):
                    ET.SubElement(properties, "property", name="BE7." + key, value=json.dumps(config[key]))
            for target in required[index::count]:
                ET.SubElement(suite, "testcase", name=target)
            ET.ElementTree(suite).write(tmp_path / pattern.replace("*", str(index + 1)), encoding="utf-8")
    return tmp_path


def test_complete_gate_evidence_passes(reports):
    assert assess(reports)["status"] == "PASS"


@pytest.mark.parametrize("group", list(GATES))
@pytest.mark.parametrize("fault", ["missing", "skipped", "failure", "error"])
def test_mandatory_execution_cannot_be_missing_or_skipped(reports, group, fault):
    path = sorted(reports.glob(GATES[group][0]))[0]
    if fault == "missing":
        path.unlink()
    else:
        root = ET.parse(path).getroot()
        ET.SubElement(next(root.iter("testcase")), fault)
        ET.ElementTree(root).write(path)
    assert assess(reports)["status"] == "FAIL"


@pytest.mark.parametrize("group,property_name,value", [
    ("mysql", "BE10.database", "sqlite"),
    ("actualModel", "BE7.revision", '"historical-model"'),
])
def test_wrong_database_or_model_is_not_release_evidence(reports, group, property_name, value):
    for path in reports.glob(GATES[group][0]):
        root = ET.parse(path).getroot()
        for prop in root.iter("property"):
            if prop.get("name") == property_name:
                prop.set("value", value)
        ET.ElementTree(root).write(path)
    assert assess(reports)["status"] == "FAIL"
