"""Tests of scripts/postprocess.py. Run: python3 -m unittest discover scripts/tests"""
import csv
import datetime
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import postprocess as pp  # noqa: E402

# tiny stand-ins for the files of a run: (header, rows)
FILES = {
    "patients.csv": (
        ["Id", "BIRTHDATE", "SSN", "PREFIX", "FIRST", "LAST", "RACE", "ETHNICITY", "GENDER",
         "HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE", "INCOME"],
        [["p1", "1950-03-09", "999-11-1111", "Mr.", "Γιώργος", "Παπαδόπουλος", "white",
          "nonhispanic", "M", "1000.50", "0.00", "9000"],
         ["p2", "1980-01-01", "999-22-2222", "Ms.", "Μαρία", "Νικολάου, Jr", "white",
          "nonhispanic", "F", "20.00", "0.00", "7000"]]),
    "encounters.csv": (
        ["Id", "PATIENT", "ENCOUNTERCLASS", "DESCRIPTION", "BASE_ENCOUNTER_COST",
         "TOTAL_CLAIM_COST", "PAYER_COVERAGE"],
        [["e1", "p1", "virtual", "virtual visit of a patient", "75.00", "75.00", "0.00"],
         ["e2", "p1", "ambulatory", "check up", "75.00", "75.00", "0.00"],
         ["e3", "p2", "wellness", 'say "hi"', "10", "10", "0"]]),
    "medications.csv": (
        ["START", "PATIENT", "CODE", "BASE_COST", "PAYER_COVERAGE", "DISPENSES", "TOTALCOST"],
        [["2020-01-01", "p1", "123", "5.0", "0.0", "3", "15.0"]]),
    "procedures.csv": (["START", "PATIENT", "CODE", "BASE_COST"],
                       [["2020-01-01", "p1", "9", "100.0"]]),
    "immunizations.csv": (["DATE", "PATIENT", "CODE", "BASE_COST"],
                          [["2020-01-01", "p1", "20", "136.00"]]),
    "organizations.csv": (["Id", "NAME", "REVENUE", "UTILIZATION"],
                          [["o1", "Κέντρο Υγείας", "5000.0", "12"]]),
    "payers.csv": (["Id", "NAME", "AMOUNT_COVERED", "AMOUNT_UNCOVERED", "REVENUE",
                    "UNIQUE_CUSTOMERS"], [["x", "NO_INSURANCE", "0", "9", "9", "2"]]),
    "conditions.csv": (["START", "PATIENT", "CODE", "DESCRIPTION"],
                       [["2020-01-01", "p1", "44054006", "Diabetes"]]),
    "observations.csv": (
        ["DATE", "PATIENT", "CODE", "DESCRIPTION", "VALUE", "UNITS"],
        [["2020-01-01", "p1", "93025-5", "Protocol for Responding", "", ""],
         ["2020-01-01", "p1", "56051-6", "Hispanic or Latino", "No", ""],
         ["2020-01-01", "p1", "71802-3", "Housing status", "Own", ""],
         ["2020-01-01", "p1", "8302-2", "Body Height", "170", "cm"],
         ["2020-01-01", "p2", "29463-7", "Body Weight", "60", "kg"]]),
}

COST_TABLE = {
    "patients.csv": ["HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE"],
    "encounters.csv": ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"],
    "medications.csv": ["BASE_COST", "PAYER_COVERAGE", "TOTALCOST"],
    "procedures.csv": ["BASE_COST"],
    "immunizations.csv": ["BASE_COST"],
    "organizations.csv": ["REVENUE"],
    "payers.csv": ["AMOUNT_COVERED", "AMOUNT_UNCOVERED", "REVENUE"],
}

MODULE = {"states": {
    "Initial": {"type": "Initial"},
    "PRAPARE": {"type": "MultiObservation",
                "codes": [{"system": "LOINC", "code": "93025-5",
                           "display": "Protocol for Responding to and Assessing Patients' Assets"}],
                "observations": [{"codes": [{"code": "56051-6", "display": "Hispanic or Latino"}]},
                                 {"codes": [{"code": "71802-3", "display": "Housing status"}]}]},
}}

TEXT = """Γιώργος Παπαδόπουλος
Γιώργος=Παπαδόπουλος
Race:                White
Ethnicity:           Non-Hispanic
Gender:              M
Age:                 70
--------------------------------------------------------------------------------
OBSERVATIONS:
  2020-01-01 : Body Height                          170 cm
  2020-01-02 : Protocol for Responding to and Assessing Patients' Assets [PRAPARE]
           - Do you feel safe Yes
           - Are you a refugee No
  2020-01-03 : Total score [HARK]                       0.0 {score}
           - Within the last year, were you afraid No
  2020-01-04 : Race and racing heart check          fine
--------------------------------------------------------------------------------
"""


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


class Fixture(unittest.TestCase):
    """A small run in a temporary folder; the tests are in the subclasses."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.input = os.path.join(root, "run")
        self.output = os.path.join(root, "run", "postprocessed")
        os.makedirs(os.path.join(self.input, "csv"))
        os.makedirs(os.path.join(self.input, "text"))
        for name, (header, rows) in FILES.items():
            write_csv(os.path.join(self.input, "csv", name), header, rows)
        with open(os.path.join(self.input, "text", "p1.txt"), "w", encoding="utf-8") as f:
            f.write(TEXT)
        self.modules = os.path.join(root, "modules")
        os.makedirs(os.path.join(self.modules, "encounter"))
        with open(os.path.join(self.modules, "encounter", "sdoh_hrsn.json"), "w") as f:
            json.dump(MODULE, f)

    def run_steps(self, steps):
        return pp.run(self.input, self.output, steps, self.modules)

    def out(self, name):
        return read_csv(os.path.join(self.output, "csv", name))

    def text(self):
        with open(os.path.join(self.output, "text", "p1.txt"), encoding="utf-8") as f:
            return f.read()


class PostprocessTest(Fixture):
    # ---- costs
    def test_cost_columns_are_dropped_and_the_rest_is_kept(self):
        self.run_steps(["costs"])
        for name, columns in COST_TABLE.items():
            header, rows = self.out(name)
            in_header, in_rows = FILES[name]
            for column in columns:
                self.assertNotIn(column, header, name)
            kept = [i for i, c in enumerate(in_header) if c not in columns]
            self.assertEqual([in_header[i] for i in kept], header, name)
            self.assertEqual([[r[i] for i in kept] for r in in_rows], rows, name)

    def test_income_is_not_a_cost_column(self):
        self.run_steps(["costs"])
        header, rows = self.out("patients.csv")
        self.assertIn("INCOME", header)
        self.assertEqual(["9000", "7000"], [r[header.index("INCOME")] for r in rows])

    # ---- race
    def test_race_and_ethnicity_columns_and_text_lines(self):
        self.run_steps(["race"])
        header, rows = self.out("patients.csv")
        self.assertNotIn("RACE", header)
        self.assertNotIn("ETHNICITY", header)
        self.assertEqual(len(FILES["patients.csv"][1]), len(rows))
        text = self.text()
        self.assertNotIn("Race:", text)
        self.assertNotIn("Ethnicity:", text)
        self.assertIn("Gender:              M", text)
        # a line that only contains the word later in the file is not touched
        self.assertIn("Race and racing heart check", text)

    # ---- prefix
    def test_prefix_is_blanked_not_dropped(self):
        self.run_steps(["prefix"])
        header, rows = self.out("patients.csv")
        i = header.index("PREFIX")
        self.assertEqual(["", ""], [r[i] for r in rows])
        self.assertEqual(["Γιώργος", "Μαρία"], [r[header.index("FIRST")] for r in rows])
        self.assertEqual(FILES["patients.csv"][0], header)

    # ---- virtual
    def test_virtual_encounters_become_ambulatory(self):
        self.run_steps(["virtual"])
        header, rows = self.out("encounters.csv")
        i = header.index("ENCOUNTERCLASS")
        self.assertEqual(["ambulatory", "ambulatory", "wellness"], [r[i] for r in rows])
        # the word in another column is not changed
        self.assertEqual("virtual visit of a patient", rows[0][header.index("DESCRIPTION")])

    # ---- sdoh
    def test_prapare_observation_rows_are_dropped(self):
        summary = self.run_steps(["sdoh"])
        header, rows = self.out("observations.csv")
        codes = [r[header.index("CODE")] for r in rows]
        self.assertEqual(["8302-2", "29463-7"], codes)
        self.assertEqual(3, summary["csv"]["observations.csv"]["dropped_rows"])

    def test_prapare_blocks_in_text_are_dropped_with_their_bullets_only(self):
        self.run_steps(["sdoh"])
        text = self.text()
        self.assertNotIn("PRAPARE", text)
        self.assertNotIn("Do you feel safe", text)
        self.assertNotIn("Are you a refugee", text)
        # the next report and its bullet stay
        self.assertIn("Total score [HARK]", text)
        self.assertIn("Within the last year, were you afraid No", text)
        self.assertIn("Body Height", text)

    # ---- all steps, files and behaviour
    def test_all_steps_together(self):
        self.run_steps(pp.STEPS)
        header, rows = self.out("patients.csv")
        self.assertEqual(["Id", "BIRTHDATE", "NATIONAL_ID", "PREFIX", "FIRST", "LAST", "GENDER",
                          "INCOME", "PHONE", "BLOOD_TYPE"], header)
        self.assertEqual("", rows[0][3])
        self.assertEqual("ambulatory", self.out("encounters.csv")[1][0][2])

    def test_sdoh_is_not_a_default_step_but_can_be_selected(self):
        self.assertNotIn("sdoh", pp.STEPS)
        self.assertIn("sdoh", pp.OPTIONAL_STEPS)
        self.run_steps(pp.STEPS)
        codes = [r[self.out("observations.csv")[0].index("CODE")]
                 for r in self.out("observations.csv")[1]]
        self.assertIn("93025-5", codes)

    def test_warning_when_the_questionnaire_is_still_in_the_run(self):
        summary = self.run_steps(pp.STEPS)  # the fixture holds PRAPARE rows
        self.assertEqual(1, len(summary["warnings"]))
        self.assertIn("-d config/common/modules", summary["warnings"][0])
        self.assertIn("3 PRAPARE", summary["warnings"][0])

    def test_no_warning_when_the_sdoh_step_runs_or_the_run_is_clean(self):
        self.assertEqual([], self.run_steps(pp.STEPS + ["sdoh"])["warnings"])
        header, rows = FILES["observations.csv"]
        write_csv(os.path.join(self.input, "csv", "observations.csv"), header,
                  [r for r in rows if r[2] not in ("93025-5", "56051-6", "71802-3")])
        self.assertEqual([], self.run_steps(pp.STEPS)["warnings"])

    def test_unselected_steps_do_nothing(self):
        self.run_steps(["costs"])
        header, _ = self.out("patients.csv")
        self.assertIn("RACE", header)
        self.assertIn("PREFIX", header)
        self.assertIn("Race:", self.text())

    def test_files_without_changes_are_identical_copies_and_the_input_is_untouched(self):
        before = {n: read_bytes(os.path.join(self.input, "csv", n)) for n in FILES}
        self.run_steps(pp.STEPS)
        for name in ("conditions.csv",):
            self.assertEqual(before[name], read_bytes(os.path.join(self.output, "csv", name)))
        for name, data in before.items():
            self.assertEqual(data, read_bytes(os.path.join(self.input, "csv", name)))
        with open(os.path.join(self.input, "text", "p1.txt"), encoding="utf-8") as f:
            self.assertEqual(TEXT, f.read())

    def test_greek_text_and_quoting_survive(self):
        self.run_steps(["costs"])
        header, rows = self.out("patients.csv")
        self.assertEqual("Νικολάου, Jr", rows[1][header.index("LAST")])
        header, rows = self.out("encounters.csv")
        self.assertEqual('say "hi"', rows[2][header.index("DESCRIPTION")])

    def test_a_missing_column_is_an_error(self):
        write_csv(os.path.join(self.input, "csv", "encounters.csv"),
                  ["Id", "PATIENT", "DESCRIPTION"], [["e1", "p1", "x"]])
        with self.assertRaises(ValueError):
            self.run_steps(["costs"])

    def test_unknown_step_and_same_folder_are_errors(self):
        with self.assertRaises(ValueError):
            self.run_steps(["nonsense"])
        with self.assertRaises(ValueError):
            pp.run(self.input, self.input, ["costs"], self.modules)

    def test_module_without_questionnaire_is_an_error(self):
        with open(os.path.join(self.modules, "encounter", "sdoh_hrsn.json"), "w") as f:
            json.dump({"states": {"Initial": {"type": "Initial"}}}, f)
        with self.assertRaises(ValueError):
            self.run_steps(["sdoh"])

    def test_the_real_module_has_the_questionnaire(self):
        real = os.path.join(os.path.dirname(__file__), "..", "..", "src", "main", "resources",
                            "modules")
        if not os.path.isdir(real):
            self.skipTest("module folder not found")
        codes, titles = pp.prapare(real)
        self.assertIn("93025-5", codes)
        self.assertIn("56051-6", codes)
        self.assertEqual(22, len(codes))
        self.assertTrue(any("PRAPARE" in t or "Protocol for Responding" in t for t in titles))


class IdentifierTest(unittest.TestCase):
    """AMKA, Albanian NID, blood types and phone numbers."""

    # examples of python-stdnum (stdnum/gr/amka.py)
    def test_luhn_check_digit_matches_the_stdnum_examples(self):
        self.assertEqual("7", pp.luhn_check_digit("0101309999"))
        self.assertNotEqual("9", pp.luhn_check_digit("0101309999"))

    def test_amka_structure(self):
        for gender, parity in (("M", "13579"), ("F", "02468")):
            for i in range(200):
                number = pp.amka(pp.seeded("gr", "id%d" % i, "national_id"),
                                 datetime.date(1957, 11, 3), gender)
                self.assertEqual(11, len(number))
                self.assertTrue(number.isdigit())
                self.assertEqual("031157", number[:6])
                self.assertIn(number[9], parity)
                self.assertEqual(number[10], pp.luhn_check_digit(number[:10]))

    def test_amka_of_a_baby_born_in_2005_uses_two_digits_of_the_year(self):
        number = pp.amka(pp.seeded("gr", "x", "national_id"), datetime.date(2005, 2, 28), "F")
        self.assertEqual("280205", number[:6])

    # decode I05101999Q of the OECD page: I = 1980s, 0 -> 1980, 51 = January + 50 (a woman), 01
    def test_albanian_nid_encoding_table(self):
        table = [
            (datetime.date(1980, 1, 1), "F", "I051" + "01"),
            (datetime.date(1980, 1, 1), "M", "I001" + "01"),
            (datetime.date(2005, 3, 9), "M", "K503" + "09"),
            (datetime.date(1999, 12, 31), "F", "J962" + "31"),
            (datetime.date(1917, 7, 4), "M", "B707" + "04"),
            (datetime.date(2024, 6, 15), "F", "M456" + "15"),
        ]
        for birth, gender, prefix in table:
            number = pp.albanian_nid(pp.seeded("al", "p", "national_id"), birth, gender)
            self.assertTrue(re.match(r"^[A-M][0-9]{8}[A-Z]$", number), number)
            self.assertEqual(prefix, number[:6], (birth, gender, number))

    def test_albanian_nid_outside_1900_to_2029_is_an_error(self):
        with self.assertRaises(ValueError):
            pp.albanian_nid(pp.seeded("al", "p", "national_id"), datetime.date(1890, 1, 1), "M")

    def test_values_depend_only_on_country_and_patient_id(self):
        for country in ("gr", "al"):
            self.assertEqual(pp.mobile_phone(country, "abc"), pp.mobile_phone(country, "abc"))
            self.assertEqual(pp.blood_type(country, "abc"), pp.blood_type(country, "abc"))
        self.assertNotEqual(pp.mobile_phone("gr", "abc"), pp.mobile_phone("al", "abc"))
        a = pp.amka(pp.seeded("gr", "abc", "national_id"), datetime.date(1960, 1, 2), "M")
        b = pp.amka(pp.seeded("gr", "abc", "national_id"), datetime.date(1960, 1, 2), "M")
        self.assertEqual(a, b)

    def test_phone_formats(self):
        for i in range(500):
            greek = pp.mobile_phone("gr", "p%d" % i)
            self.assertTrue(re.match(r"^\+30 69[0345789] \d{3} \d{4}$", greek), greek)
            albanian = pp.mobile_phone("al", "p%d" % i)
            self.assertTrue(re.match(r"^\+355 6[789] \d{3} \d{4}$", albanian), albanian)

    def test_blood_type_frequencies_follow_the_table(self):
        for country in ("gr", "al"):
            n = 20000
            counts = {name: 0 for name in pp.BLOOD_TYPES}
            for i in range(n):
                counts[pp.blood_type(country, "p%d" % i)] += 1
            for name, weight in zip(pp.BLOOD_TYPES, pp.BLOOD_FREQUENCIES[country]):
                self.assertAlmostEqual(weight, 100.0 * counts[name] / n, delta=1.0,
                                       msg="%s %s" % (country, name))

    def test_blood_type_tables_sum_to_100(self):
        for country, weights in pp.BLOOD_FREQUENCIES.items():
            self.assertAlmostEqual(100.0, sum(weights), places=6, msg=country)
            self.assertEqual(len(pp.BLOOD_TYPES), len(weights))


class IdentifierStepsTest(Fixture):
    """The three steps on a patients.csv."""

    def patients(self, steps, country="gr"):
        pp.run(self.input, self.output, steps, self.modules, country)
        return self.out("patients.csv")

    def test_national_id_replaces_ssn_in_place(self):
        header, rows = self.patients(["national_id"])
        self.assertNotIn("SSN", header)
        self.assertEqual(FILES["patients.csv"][0].index("SSN"), header.index("NATIONAL_ID"))
        i = header.index("NATIONAL_ID")
        self.assertEqual(len(FILES["patients.csv"][0]), len(header))
        self.assertTrue(rows[0][i].startswith("090350"))  # 9 March 1950, a man
        self.assertEqual("M", "M" if int(rows[0][i][9]) % 2 else "F")
        self.assertEqual("F", "M" if int(rows[1][i][9]) % 2 else "F")
        self.assertEqual("010180", rows[1][i][:6])

    def test_albanian_ids_for_albania(self):
        header, rows = self.patients(["national_id"], "al")
        i = header.index("NATIONAL_ID")
        self.assertTrue(rows[0][i].startswith("F00309"), rows[0][i])  # 1950-03-09, a man
        self.assertTrue(rows[1][i].startswith("I05101"), rows[1][i])  # 1980-01-01, a woman

    def test_phone_and_blood_type_are_appended_last(self):
        header, rows = self.patients(["phone", "blood_type"])
        self.assertEqual(FILES["patients.csv"][0] + ["PHONE", "BLOOD_TYPE"], header)
        self.assertTrue(rows[0][-2].startswith("+30 69"))
        self.assertIn(rows[0][-1], pp.BLOOD_TYPES)
        # the other columns are untouched
        self.assertEqual(FILES["patients.csv"][1][0], rows[0][:-2])

    def test_a_rerun_gives_the_same_values(self):
        first = self.patients(["national_id", "phone", "blood_type"])
        second = self.patients(["national_id", "phone", "blood_type"])
        self.assertEqual(first, second)

    def test_patients_missing_a_needed_column_is_an_error(self):
        write_csv(os.path.join(self.input, "csv", "patients.csv"), ["Id", "SSN", "GENDER"],
                  [["p1", "999-11-1111", "M"]])
        with self.assertRaises(KeyError):
            self.patients(["national_id"])

    def test_ids_are_unique(self):
        rows = [["p%d" % i, "1970-05-05", "999-00-0000", "Mr.", "A", "B", "white",
                 "nonhispanic", "M", "1", "1", "1"] for i in range(300)]
        write_csv(os.path.join(self.input, "csv", "patients.csv"), FILES["patients.csv"][0], rows)
        header, out = self.patients(["national_id"])
        values = [r[header.index("NATIONAL_ID")] for r in out]
        self.assertEqual(len(values), len(set(values)))


if __name__ == "__main__":
    unittest.main()
