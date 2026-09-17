from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


SPEC_DIR = Path(__file__).parents[1]
DOCUMENTS_DIR = Path(__file__).with_name("documents")
CONFORMANCE_FIXTURES_DIR = SPEC_DIR.parent / "conformance" / "fixtures"
SCHEMA = json.loads(
    (SPEC_DIR / "agent-topology.schema.json").read_text(encoding="utf-8")
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "agent_topology_schema_validator", SPEC_DIR / "validate.py"
)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
VALIDATOR_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(VALIDATOR_MODULE)


class SchemaTests(unittest.TestCase):
    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(SCHEMA)

    def test_valid_documents(self) -> None:
        for path in sorted((DOCUMENTS_DIR / "valid").glob("*.json")):
            with self.subTest(document=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(VALIDATOR_MODULE.validate_document(document, SCHEMA), [])

    def test_conformance_expected_documents(self) -> None:
        expected_paths = sorted(CONFORMANCE_FIXTURES_DIR.glob("*/expected.json"))
        self.assertEqual(len(expected_paths), 11)
        for path in expected_paths:
            with self.subTest(fixture=path.parent.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(VALIDATOR_MODULE.validate_document(document, SCHEMA), [])

    def test_format_package_and_hash_versions_are_independent(self) -> None:
        document = json.loads(
            (DOCUMENTS_DIR / "valid" / "minimal.json").read_text(encoding="utf-8")
        )
        changed_package_version = deepcopy(document)
        changed_package_version["provenance"]["producer"]["version"] = "2026.9.10"
        self.assertEqual(
            VALIDATOR_MODULE.validate_document(changed_package_version, SCHEMA), []
        )

        changed_format_version = deepcopy(document)
        changed_format_version["topologyVersion"] = "1"
        errors = VALIDATOR_MODULE.validate_document(changed_format_version, SCHEMA)
        self.assertTrue(any("$.topologyVersion" in error for error in errors))

    def test_invalid_documents_have_actionable_errors(self) -> None:
        cases = {
            "inconsistent-completeness.json": "$.completeness.status: must be 'incomplete'",
            "invalid-reference.json": "$.graphs[0].structure.edges[0].target: unknown node id 'missing'",
            "misplaced-extension.json": "$.graphs[0].structure.nodes[0]: 'vendorData' does not match",
            "missing-required.json": "$: 'topologyVersion' is a required property",
        }
        for filename, expected in cases.items():
            with self.subTest(document=filename):
                document = json.loads(
                    (DOCUMENTS_DIR / "invalid" / filename).read_text(encoding="utf-8")
                )
                errors = VALIDATOR_MODULE.validate_document(document, SCHEMA)
                self.assertTrue(errors)
                self.assertTrue(
                    any(expected in error for error in errors),
                    f"expected {expected!r} in {errors!r}",
                )


if __name__ == "__main__":
    unittest.main()
