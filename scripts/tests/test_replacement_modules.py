"""Guards the replacement modules of config/common/modules (loaded with -d).

Each replaces the built-in module with the same path and name by an empty module. If upstream
renames or moves a module, or an empty module gets content, these tests fail.
Run: python3 -m unittest discover scripts/tests
"""
import json
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REPLACEMENTS = os.path.join(ROOT, "config", "common", "modules")
BUILT_IN = os.path.join(ROOT, "src", "main", "resources", "modules")
EMPTY = ["encounter/hark_screening.json", "encounter/sdoh_hrsn.json", "homelessness.json",
         "veteran.json"]
OPIOID_ADDICTION = "opioid_addiction.json"
OPIOID_CHRONIC = "prescribing_opioids_for_chronic_pain_and_treatment_of_oud.json"
EXPECTED = EMPTY + [OPIOID_ADDICTION, OPIOID_CHRONIC]
# states of the chronic pain module that start an opioid prescription or an aberrant urine test
OPIOID_ENTRIES = {"Enter_IR/SA_Opioid_Directed_Use_1", "Enter_IR/SA_Opioid_Directed_Use_2",
                  "Enter_ER/LA_Opioid_Directed_Use", "Urine_Drug_Testing_Aberrant_Positive_1",
                  "Urine_Drug_Testing_Aberrant_Positive_2"}


def transitions(node):
    """All target state names in a module state or any part of it."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("transition", "direct_transition") and isinstance(value, str):
                found.append(value)
            else:
                found += transitions(value)
    elif isinstance(node, list):
        for value in node:
            found += transitions(value)
    return found


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class ReplacementModulesTest(unittest.TestCase):
    def test_the_expected_modules_are_there_and_no_others(self):
        found = []
        for root, _, files in os.walk(REPLACEMENTS):
            for name in files:
                if name.endswith(".json"):
                    found.append(os.path.relpath(os.path.join(root, name), REPLACEMENTS))
        self.assertEqual(sorted(EXPECTED), sorted(found))

    def test_each_replaces_a_built_in_module_with_the_same_name(self):
        for relative in EXPECTED:
            replacement = load(os.path.join(REPLACEMENTS, relative))
            original_path = os.path.join(BUILT_IN, relative)
            self.assertTrue(os.path.exists(original_path), relative + " no longer exists upstream")
            self.assertEqual(load(original_path)["name"], replacement["name"], relative)

    def test_each_is_empty_and_says_why(self):
        for relative in EMPTY:
            module = load(os.path.join(REPLACEMENTS, relative))
            self.assertEqual({"Initial", "Terminal"}, set(module["states"]), relative)
            self.assertEqual("Initial", module["states"]["Initial"]["type"], relative)
            self.assertEqual("Terminal", module["states"]["Initial"]["direct_transition"],
                             relative)
            self.assertTrue(module.get("remarks"), relative + " must give its reason")

    def test_the_opioid_addiction_copy_only_ends_and_clears_the_prescription(self):
        module = load(os.path.join(REPLACEMENTS, OPIOID_ADDICTION))
        types = {state["type"] for state in module["states"].values()}
        self.assertEqual({"Initial", "Delay", "MedicationEnd", "SetAttribute"}, types)
        end = [s for s in module["states"].values() if s["type"] == "MedicationEnd"]
        self.assertEqual(["opioid_prescription"], [s["referenced_by_attribute"] for s in end])
        names = " ".join(module["states"]).lower()
        for word in ("misuse", "addiction", "overdose", "detox"):
            self.assertNotIn(word, names)
        self.assertTrue(module.get("remarks"))

    def test_the_chronic_pain_copy_keeps_every_state_and_never_starts_an_opioid(self):
        original = load(os.path.join(BUILT_IN, OPIOID_CHRONIC))
        copy = load(os.path.join(REPLACEMENTS, OPIOID_CHRONIC))
        self.assertEqual(sorted(original["states"]), sorted(copy["states"]))
        self.assertEqual(original["name"], copy["name"])
        targets = set()
        for state in copy["states"].values():
            targets |= set(transitions(state))
        self.assertEqual(set(), targets & OPIOID_ENTRIES)
        # the original does reach them, so the test would notice a change of the upstream module
        original_targets = set()
        for state in original["states"].values():
            original_targets |= set(transitions(state))
        self.assertEqual(OPIOID_ENTRIES, original_targets & OPIOID_ENTRIES)
        self.assertTrue(copy.get("remarks"))

    def test_every_module_that_reads_the_veteran_attribute_is_guarded_by_it(self):
        # the empty veteran module is enough only while each veteran module starts with a check
        # of the attribute (or reads it only to pick a branch); a new unguarded one must be seen
        guarded = 0
        for name in sorted(os.listdir(BUILT_IN)):
            if not name.startswith("veteran_"):
                continue
            text = open(os.path.join(BUILT_IN, name), encoding="utf-8").read()
            if name == "veteran_substance_abuse_treatment.json":
                continue  # reached only through the conditions module, which is guarded
            self.assertIn('"attribute": "veteran"', text, name)
            guarded += 1
        self.assertGreaterEqual(guarded, 7)


if __name__ == "__main__":
    unittest.main()
