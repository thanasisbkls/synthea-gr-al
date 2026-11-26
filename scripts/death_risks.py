#!/usr/bin/env python3
"""Yearly death risks by age for lifecycle.death_risk_file, as a top-up of the modules' deaths.

Synthea's disease modules kill people, but nobody dies of causes the modules do not model, and
there are no deaths at old age or in infancy. Real mortality is the sum of both. This script
measures the death rate per person-year that the modules cause in a run made WITHOUT natural
deaths (lifecycle.death_by_natural_causes = false, generate.only_alive_patients = false), and
writes, for every age band of the country's real death rates, the difference to the real rate
(never below zero: where the modules already kill more than the real rate, nothing is added).

  python3 scripts/death_risks.py --country gr --input output/death_gr

The run must hold the dead as well as the living (every person generated, with the death date
in patients.csv): person-years are counted from birth to death or to the reference date, which
does not depend on dying, so the rate is not biased by the way the population is drawn.
Rerun it whenever a module that kills people changes.

Real rates: WHO Global Health Observatory, indicator LIFE_0000000029 (age-specific death rate,
both sexes), 2023, https://ghoapi.azureedge.net/api/LIFE_0000000029 (accessed 2026-11-26).
"""
import argparse
import csv
import datetime
import os
import sys

# (min age, max age included, deaths per 100,000 person-years, both sexes, 2023)
WHO = {
    "gr": [(0, 0, 333.5), (1, 4, 15.4), (5, 9, 6.2), (10, 14, 7.2), (15, 19, 21.8),
           (20, 24, 31.6), (25, 29, 36.9), (30, 34, 47.5), (35, 39, 67.3), (40, 44, 98.4),
           (45, 49, 161.4), (50, 54, 263.8), (55, 59, 478.9), (60, 64, 723.5),
           (65, 69, 1148.9), (70, 74, 1570.1), (75, 79, 2791.4), (80, 84, 5052.4),
           (85, 120, 16154.1)],
    "al": [(0, 0, 847.2), (1, 4, 26.9), (5, 9, 18.0), (10, 14, 21.5), (15, 19, 42.0),
           (20, 24, 47.8), (25, 29, 65.5), (30, 34, 76.4), (35, 39, 101.9), (40, 44, 137.6),
           (45, 49, 222.8), (50, 54, 340.0), (55, 59, 457.5), (60, 64, 733.5),
           (65, 69, 1261.0), (70, 74, 2528.2), (75, 79, 3998.9), (80, 84, 7935.8),
           (85, 120, 15654.9)],
}
DAYS_PER_YEAR = 365.25


def module_rates(people, bands, reference):
    """Deaths per 100,000 person-years in each band.

    people: list of (birth date, death date or None); bands: (min age, max age included, ...).
    """
    exposure = [0.0] * len(bands)
    deaths = [0] * len(bands)
    for born, died in people:
        end = died or reference
        for i, band in enumerate(bands):
            start = born + datetime.timedelta(days=band[0] * DAYS_PER_YEAR)
            stop = born + datetime.timedelta(days=(band[1] + 1) * DAYS_PER_YEAR)
            years = (min(stop, end) - start).days / DAYS_PER_YEAR
            if years > 0:
                exposure[i] += years
            if died and start <= died < stop:
                deaths[i] += 1
    return [d / e * 1e5 if e else 0.0 for d, e in zip(deaths, exposure)], deaths, exposure


def top_up(real, simulated):
    """Real rate minus the rate the modules cause, never below zero."""
    return [max(0.0, r - s) for r, s in zip(real, simulated)]


def read_people(path):
    people = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            born = datetime.date.fromisoformat(row["BIRTHDATE"][:10])
            died = datetime.date.fromisoformat(row["DEATHDATE"][:10]) if row["DEATHDATE"] else None
            people.append((born, died))
    return people


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--country", required=True, choices=sorted(WHO))
    parser.add_argument("--input", required=True, help="output folder of a run without natural deaths")
    parser.add_argument("--reference", default="2026-11-20", help="reference date of the run (-r)")
    parser.add_argument("--output", help="CSV to write (default: print only)")
    args = parser.parse_args(argv)
    bands = WHO[args.country]
    people = read_people(os.path.join(args.input, "csv", "patients.csv"))
    rates, deaths, _ = module_rates(people, bands, datetime.date.fromisoformat(args.reference))
    extra = top_up([b[2] for b in bands], rates)
    print("%-7s %7s %12s %10s %10s" % ("age", "deaths", "modules/100k", "real/100k", "top-up"))
    for band, d, s, e in zip(bands, deaths, rates, extra):
        print("%-7s %7d %12.1f %10.1f %10.1f" % ("%d-%d" % band[:2], d, s, band[2], e))
    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["min_age", "max_age", "deaths_per_100000"])
            for band, e in zip(bands, extra):
                w.writerow([band[0], band[1], round(e, 1)])
        print("written", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
