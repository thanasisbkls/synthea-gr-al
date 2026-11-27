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
DIABETES = "metabolic_syndrome_disease.json"
OSTEOARTHRITIS = "osteoarthritis.json"
EPILEPSY = "epilepsy.json"
INJURIES = "injuries.json"
EXPECTED = EMPTY + [OPIOID_ADDICTION, OPIOID_CHRONIC, DIABETES, OSTEOARTHRITIS, EPILEPSY,
                    INJURIES]
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


def without(module, *keys):
    """The module with the given state names and the remarks left out, to compare the rest."""
    copy = json.loads(json.dumps(module))
    copy.pop("remarks", None)
    for key in keys:
        copy["states"].pop(key)
    return copy


def distributions(state):
    """Every {distribution, transition} entry of a state, whatever kind of transition it has."""
    found = []
    if isinstance(state, dict):
        if "transition" in state and "distribution" in state:
            found.append(state)
        for value in state.values():
            found += distributions(value)
    elif isinstance(state, list):
        for value in state:
            found += distributions(value)
    return found


def successors(node):
    """Target state names of a state that can be taken (a distribution of 0 never is)."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("transition", "direct_transition") and isinstance(value, str):
                if node.get("distribution", 1) != 0:
                    found.append(value)
            else:
                found += successors(value)
    elif isinstance(node, list):
        for value in node:
            found += successors(value)
    return found


def reachable(module):
    seen, todo = set(), ["Initial"]
    while todo:
        name = todo.pop()
        if name in seen or name not in module["states"]:
            continue
        seen.add(name)
        todo += successors(module["states"][name])
    return seen


def white_branch(module):
    state = module["states"]["Non_Veteran_Diabetes_Prevalence"]
    return [c for c in state["complex_transition"]
            if c.get("condition", {}).get("race") == "White"][0]["distributions"]


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

    def test_the_diabetes_copy_only_changes_the_white_branch_shares(self):
        original = load(os.path.join(BUILT_IN, DIABETES))
        copy = load(os.path.join(REPLACEMENTS, DIABETES))
        # the rest of the module is the upstream one; the White branch is compared below
        for module in (original, copy):
            white_branch(module).clear()
        self.assertEqual(without(original), without(copy))
        self.assertTrue(copy.get("remarks"))
        # upstream still has the shares we replaced, so a change there is noticed
        upstream = {d["transition"]: d["distribution"]
                    for d in white_branch(load(os.path.join(BUILT_IN, DIABETES)))}
        self.assertEqual({"Eventual_Diabetes": 0.25, "Eventual_Prediabetes": 0.45,
                          "No_Diabetes": 0.3}, upstream)

    def test_the_diabetes_shares_keep_prediabetes_and_sum_to_one(self):
        shares = {d["transition"]: d["distribution"]
                  for d in white_branch(load(os.path.join(REPLACEMENTS, DIABETES)))}
        self.assertEqual(0.45, shares["Eventual_Prediabetes"])
        self.assertLess(shares["Eventual_Diabetes"], 0.25)
        self.assertAlmostEqual(1.0, sum(shares.values()), places=6)

    def test_the_osteoarthritis_copy_only_changes_the_non_veteran_shares(self):
        original = load(os.path.join(BUILT_IN, OSTEOARTHRITIS))
        copy = load(os.path.join(REPLACEMENTS, OSTEOARTHRITIS))
        self.assertEqual(without(original, "Non_Veteran"), without(copy, "Non_Veteran"))
        self.assertTrue(copy.get("remarks"))
        for module, expected in ((original, {"M": 0.21, "F": 0.2267}), (copy, None)):
            for branch in module["states"]["Non_Veteran"]["complex_transition"]:
                gender = branch["condition"]["gender"]
                shares = {d["transition"]: d["distribution"] for d in branch["distributions"]}
                self.assertEqual({"Delay_Until_Symptoms", "Terminal"}, set(shares))
                self.assertAlmostEqual(1.0, sum(shares.values()), places=6)
                if expected:  # upstream still has the shares we replaced
                    self.assertEqual(expected[gender], shares["Delay_Until_Symptoms"])
                else:
                    self.assertLess(shares["Delay_Until_Symptoms"], 0.21)

    def test_the_epilepsy_copy_only_replaces_the_exit_of_the_treatment_loop(self):
        original = load(os.path.join(BUILT_IN, EPILEPSY))
        copy = load(os.path.join(REPLACEMENTS, EPILEPSY))
        loop = "Undergoing_Seizure_Treatment"
        outcomes = ("Treatment_Outcome_Child", "Treatment_Outcome_Adult")
        self.assertEqual(set(original["states"]) | set(outcomes), set(copy["states"]))
        self.assertEqual(without(original, loop), without(copy, loop, *outcomes))
        self.assertTrue(copy.get("remarks"))
        # upstream still has the 10% death chance we replaced, so a change there is noticed
        upstream = {d["transition"]: d["distribution"]
                    for d in original["states"][loop]["distributed_transition"]}
        self.assertEqual({"Seizure_Encounter": 0.2, "Sudden_Cardiac_Death": 0.1,
                          "Medication_Guard": 0.7}, upstream)
        # the loop state now only waits (same delay) and branches on age
        self.assertEqual(original["states"][loop]["range"], copy["states"][loop]["range"])
        self.assertEqual(set(outcomes), {t.get("transition") for t in
                                         copy["states"][loop]["conditional_transition"]})

    def test_the_epilepsy_death_chances_follow_the_published_rates(self):
        copy = load(os.path.join(REPLACEMENTS, EPILEPSY))
        years = 0.396  # average length of one pass of the treatment loop
        for name, per_thousand_years in (("Treatment_Outcome_Child", 0.22),
                                         ("Treatment_Outcome_Adult", 1.2)):
            shares = {d["transition"]: d["distribution"]
                      for d in copy["states"][name]["distributed_transition"]}
            self.assertAlmostEqual(per_thousand_years / 1000 * years,
                                   shares["Sudden_Cardiac_Death"], places=5, msg=name)
            self.assertEqual(0.2, shares["Seizure_Encounter"])
            self.assertAlmostEqual(1.0, sum(shares.values()), places=6)

    def test_the_injuries_copy_never_reaches_the_gunshot_pathway(self):
        original = load(os.path.join(BUILT_IN, INJURIES))
        copy = load(os.path.join(REPLACEMENTS, INJURIES))
        self.assertEqual(sorted(original["states"]), sorted(copy["states"]))
        self.assertTrue(copy.get("remarks"))
        lists = {}
        for name, module in (("original", original), ("copy", copy)):
            lists[name] = [d for state in module["states"].values()
                           for d in distributions(state)]
        gunshot = {n: [d["distribution"] for d in lists[n] if d["transition"] == "Gunshot_Injury"]
                   for n in lists}
        # upstream has it in the child, adult and elderly (two branches) incidence lists
        self.assertEqual([0.000318] * 4, gunshot["original"])
        self.assertEqual([0] * 4, gunshot["copy"])
        # no state of the pathway can be reached from the start with a non-zero chance
        reached = reachable(copy)
        self.assertNotIn("Gunshot_Injury", reached)
        self.assertNotIn("Death_Gunshot_Wound", reached)
        self.assertNotIn("Gunshot_Wound", reached)
        # the original does reach them, so the test would notice a change of the upstream module
        self.assertIn("Death_Gunshot_Wound", reachable(original))

    def test_the_injuries_copy_keeps_every_other_injury_probability(self):
        original = load(os.path.join(BUILT_IN, INJURIES))
        copy = load(os.path.join(REPLACEMENTS, INJURIES))
        for name, state in original["states"].items():
            before = {d["transition"]: d["distribution"] for d in distributions(state)}
            after = {d["transition"]: d["distribution"] for d in distributions(copy["states"][name])}
            if "Gunshot_Injury" not in before:
                self.assertEqual(state, copy["states"][name], name)
                continue
            self.assertAlmostEqual(sum(v for v in before.values() if isinstance(v, float)),
                                   sum(v for v in after.values() if isinstance(v, float)),
                                   places=8, msg=name)
            for target, value in before.items():
                if target not in ("Gunshot_Injury", "Wait_For_Injury"):
                    self.assertEqual(value, after[target], name + " " + target)

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
