import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OVERRIDE = os.path.join(ROOT, "config", "common", "biometrics.yml")
WEIGHT_LOSS = os.path.join(ROOT, "src", "main", "java", "org", "mitre", "synthea", "modules",
                           "WeightLossModule.java")


class BiometricsOverrideTest(unittest.TestCase):
    def test_the_weight_management_start_chance_is_read_at_the_top_level(self):
        # the weight loss module looks up "start_prob" (not "weightloss.start_prob"), so the
        # override works only as a top-level key; if upstream changes the lookup this must fail
        code = open(WEIGHT_LOSS, encoding="utf-8").read()
        self.assertIn('BiometricsConfig.get("start_prob"', code)
        lines = open(OVERRIDE, encoding="utf-8").read().splitlines()
        top = [line for line in lines if re.match(r"^start_prob:\s*0(\.0)?\s*(#.*)?$", line)]
        self.assertEqual(1, len(top))

    def test_the_weight_loss_of_old_age_starts_at_70(self):
        text = open(OVERRIDE, encoding="utf-8").read()
        self.assertRegex(text, r"(?m)^  geriatric_weight_loss_age: 70$")
        code = open(os.path.join(ROOT, "src", "main", "java", "org", "mitre", "synthea",
                                 "modules", "LifecycleModule.java"), encoding="utf-8").read()
        self.assertIn('"lifecycle.geriatric_weight_loss_age"', code)


if __name__ == "__main__":
    unittest.main()
