#!/usr/bin/env python3
"""Socioeconomic score thresholds (middle, high) for a country, from the US category shares.

Synthea gives each person a score (0.2 * income level + 0.7 * education level + 0.1 * a random
occupation level) and calls the person Low, Middle or High from two thresholds. The disease
modules (opioid addiction, COPD, dementia) have a risk per category that was set for the US
population, where the category shares come out of the upstream thresholds (0.25 and 0.66) and
the Massachusetts demographics. This script finds the two thresholds that give a country's
demographics the same Low and High shares as that reference, so the category means the same
relative position and the average risk of a module stays that of its source.

The score is drawn as in Generator and Demographics: education group from the demographics row
(averaged over the rows, weighted by population), a uniform education level inside the group's
range, an income uniform inside a picked income band, and the income level from the poverty and
high income properties.

Usage: python3 scripts/ses_thresholds.py gr|al
"""
import csv
import os
import random
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
EDUCATION_RANGE = {"LESS_THAN_HS": (0.0, 0.5), "HS_DEGREE": (0.1, 0.75),
                   "SOME_COLLEGE": (0.3, 0.85), "BS_DEGREE": (0.5, 1.0)}
INCOME_BANDS = ["00..10", "10..15", "15..25", "25..35", "35..50", "50..75", "75..100",
                "100..150", "150..200", "200..999"]
WEIGHTS = (0.2, 0.7, 0.1)
US_THRESHOLDS = (0.25, 0.66)
US_INCOME = (17550, 75000)
SAMPLES = 400000


def read_properties(path):
    props = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*([\w.]+)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                props[m.group(1)] = m.group(2)
    return props


def weighted(path, state=None):
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if not state or r["STNAME"] == state]
    total = sum(float(r["TOT_POP"]) for r in rows)

    def mean(column):
        return sum(float(r[column]) * float(r["TOT_POP"]) for r in rows) / total
    return ({c: mean(c) for c in EDUCATION_RANGE}, {c: mean(c) for c in INCOME_BANDS})


def scores(education, income, poverty, high, seed=7):
    rng = random.Random(seed)
    groups = rng.choices(list(education), list(education.values()), k=SAMPLES)
    bands = rng.choices(list(income), list(income.values()), k=SAMPLES)
    out = []
    for group, band in zip(groups, bands):
        low, top = EDUCATION_RANGE[group]
        a, b = band.split("..")
        amount = rng.uniform(int(a) * 1000, int(b) * 1000)
        level = 1.0 if amount >= high else 0.0 if amount <= poverty else \
            (amount - poverty) / (high - poverty)
        out.append(WEIGHTS[0] * level + WEIGHTS[1] * rng.uniform(low, top)
                   + WEIGHTS[2] * rng.random())
    return sorted(out)


def main(country):
    reference = scores(*weighted(os.path.join(ROOT, "src", "main", "resources", "geography",
                                              "demographics.csv"), "Massachusetts"), *US_INCOME)
    low_share = sum(s < US_THRESHOLDS[0] for s in reference) / len(reference)
    high_share = sum(s >= US_THRESHOLDS[1] for s in reference) / len(reference)
    props = read_properties(os.path.join(ROOT, "config", country, "synthea.properties"))
    poverty = float(props["generate.demographics.socioeconomic.income.poverty"])
    high = float(props["generate.demographics.socioeconomic.income.high"])
    own = scores(*weighted(os.path.join(ROOT, props["generate.demographics.default_file"])),
                 poverty, high)
    middle = own[int(low_share * len(own))]
    top = own[int((1 - high_share) * len(own))]
    print("reference (Massachusetts, upstream thresholds): Low %.1f%%, Middle %.1f%%, High %.1f%%"
          % (low_share * 100, (1 - low_share - high_share) * 100, high_share * 100))
    print("generate.demographics.socioeconomic.score.middle = %.3f" % middle)
    print("generate.demographics.socioeconomic.score.high = %.3f" % top)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("gr", "al"):
        sys.exit(__doc__)
    main(sys.argv[1])
