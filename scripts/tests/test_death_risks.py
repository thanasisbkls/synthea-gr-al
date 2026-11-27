import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

import death_risks as dr  # noqa: E402

D = datetime.date
BANDS = [(0, 0, 300.0), (1, 9, 20.0), (10, 119, 1000.0)]
REF = D(2020, 1, 1)


class DeathRiskTest(unittest.TestCase):
    def test_person_years_and_deaths_by_band(self):
        # born 2000-01-01: 20 years to the reference, alive: 1 year, 9 years, 10 years in the bands
        rates, deaths, exposure = dr.module_rates([(D(2000, 1, 1), None)], BANDS, REF)
        self.assertEqual(deaths, [0, 0, 0])
        for got, want in zip(exposure, [1.0, 9.0, 10.0]):
            self.assertAlmostEqual(got, want, delta=0.01)

    def test_death_falls_in_one_band_and_ends_exposure(self):
        # dies at about 5 years old: exposure 1 + 4, one death in band 1
        born = D(2000, 1, 1)
        rates, deaths, exposure = dr.module_rates([(born, D(2005, 1, 1))], BANDS, REF)
        self.assertEqual(deaths, [0, 1, 0])
        self.assertAlmostEqual(exposure[1], 4.0, delta=0.02)
        self.assertEqual(exposure[2], 0.0)
        self.assertAlmostEqual(rates[1], 1 / exposure[1] * 1e5, places=3)

    def test_rate_is_not_biased_by_how_long_people_are_followed(self):
        # 1000 people, 10 of whom die at age 2
        people = []
        for i in range(1000):
            born = D(2000, 1, 1)
            people.append((born, D(2002, 1, 1) if i % 100 == 0 else None))
        rates, deaths, exposure = dr.module_rates(people, BANDS, D(2011, 1, 1))
        self.assertEqual(deaths[1], 10)
        self.assertAlmostEqual(rates[1], 10 / exposure[1] * 1e5, places=3)

    def test_top_up_never_below_zero(self):
        self.assertEqual(dr.top_up([300.0, 20.0, 1000.0], [0.0, 50.0, 400.0]), [300.0, 0.0, 600.0])

    def test_who_tables_are_contiguous_bands(self):
        for country, table in dr.WHO.items():
            self.assertEqual(table[0][0], 0, country)
            for before, after in zip(table, table[1:]):
                self.assertEqual(after[0], before[1] + 1, country)
            self.assertTrue(all(0 < row[2] < 100000 for row in table), country)


if __name__ == "__main__":
    unittest.main()
