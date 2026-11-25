#!/usr/bin/env python3
"""Post-processing of the Synthea output for Greece and Albania.

Reads the CSV and text files of a run (output/<cc>/csv and output/<cc>/text) and writes cleaned
copies to output/<cc>/postprocessed/{csv,text}. The input is never changed.

Each piece is a named step; run all of them or pick some with --steps:

  costs    drop the cost columns (invented US prices, no insurance exists)
  race     drop the race and ethnicity columns and the Race and Ethnicity lines of the text files
           (placeholders: every patient is white and nonhispanic)
  prefix   blank the English name prefixes (Mr., Ms., Mrs.)
  national_id  replace the SSN column of patients.csv by NATIONAL_ID: an AMKA (Greece) or an
           Albanian NID, generated from the country, the patient Id, the birth date and the gender
  phone    add a PHONE column to patients.csv: a mobile number in the format of the country
  blood_type  add a BLOOD_TYPE column to patients.csv, drawn from the frequencies of the country
  virtual  relabel virtual encounters as ambulatory
  sdoh     (not a default step) drop the PRAPARE questionnaire (observation rows and the blocks in
           the text files). The simulation no longer writes it (run Synthea with
           -d config/common/modules); use this only on a run made without that option.

Usage:
  python3 scripts/postprocess.py --country gr
  python3 scripts/postprocess.py --country al --steps costs,race

The tables below say exactly what each step touches; change them there.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import random
import re
import shutil
import string
import sys

csv.field_size_limit(10 ** 9)

STEPS = ["costs", "race", "prefix", "virtual", "national_id", "phone", "blood_type"]
OPTIONAL_STEPS = ["sdoh"]

# ---- what each step touches ---------------------------------------------------------------

# costs: columns dropped, per CSV file. INCOME stays: it is the person's income from the Eurostat
# distribution, not a price.
COST_COLUMNS = {
    "patients.csv": ["HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE"],
    "encounters.csv": ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"],
    "medications.csv": ["BASE_COST", "PAYER_COVERAGE", "TOTALCOST"],
    "procedures.csv": ["BASE_COST"],
    "immunizations.csv": ["BASE_COST"],
    "organizations.csv": ["REVENUE"],
    "payers.csv": ["AMOUNT_COVERED", "AMOUNT_UNCOVERED", "REVENUE"],
}

# race: columns dropped, and the lines of the text files (the first block, before the first
# line of dashes)
RACE_COLUMNS = {"patients.csv": ["RACE", "ETHNICITY"]}
RACE_TEXT_LINE = re.compile(r"^(Race|Ethnicity):\s")

# prefix: columns blanked (the empty value stays, the column stays)
PREFIX_COLUMNS = {"patients.csv": ["PREFIX"]}

# virtual: value changes per file and column
VIRTUAL_MAP = {"encounters.csv": {"ENCOUNTERCLASS": {"virtual": "ambulatory"}}}

# sdoh: the PRAPARE questionnaire. Its codes and titles are read from the module itself.
SDOH_MODULE = os.path.join("encounter", "sdoh_hrsn.json")
SDOH_ROW_FILTER = {"observations.csv": "CODE"}
TEXT_BULLET = re.compile(r"^\s+- ")
TEXT_DATED = re.compile(r"^\s+\d{4}-\d{2}-\d{2} : (.*)$")


def prapare(modules_dir):
    """The PRAPARE codes and the titles of its panel, from the module sdoh_hrsn.json."""
    path = os.path.join(modules_dir, SDOH_MODULE)
    with open(path, encoding="utf-8") as f:
        module = json.load(f)
    codes, titles = set(), []
    for state in module["states"].values():
        if state.get("type") == "MultiObservation":
            for code in state.get("codes", []):
                codes.add(code["code"])
                titles.append(code["display"])
            for obs in state.get("observations", []):
                if obs.get("codes"):
                    codes.add(obs["codes"][0]["code"])
    if not codes:
        raise ValueError("no PRAPARE questionnaire found in " + path)
    return codes, titles


# ---- national IDs, blood types and phone numbers --------------------------------------------
# Everything is drawn from a random generator seeded on the country, the patient Id and the
# purpose, so a rerun gives the same values.

# Blood type frequencies in percent, Wikipedia "Blood type distribution by country" (the row of
# Greece has no citation there, and the table is marked as disputed).
BLOOD_TYPES = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
BLOOD_FREQUENCIES = {
    "gr": [37.8, 32.2, 11.0, 4.0, 6.6, 5.7, 2.0, 0.7],
    "al": [34.1, 31.2, 14.5, 5.2, 6.0, 5.5, 2.6, 0.9],
}

# Mobile numbers. Greece: ten digits starting 69, the third digit one of 0 3 4 5 7 8 9
# (Wikipedia "Telephone numbers in Greece"). Albania: 067, 068 and 069 (Wikipedia "Telephone
# numbers in Albania"), nine digits after the 0. Landline numbers are not generated.
GREEK_MOBILE_THIRD_DIGIT = "0345789"
ALBANIAN_MOBILE_PREFIXES = ["67", "68", "69"]


def seeded(country, patient_id, purpose):
    """A random generator that depends only on the country, the patient Id and the purpose."""
    text = "%s:%s:%s" % (country, patient_id, purpose)
    return random.Random(int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big"))


def luhn_check_digit(payload):
    """The Luhn check digit of a string of digits (the digit that is appended to it)."""
    total = 0
    for i, ch in enumerate(reversed(payload)):
        digit = int(ch)
        if i % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def amka(rng, birth_date, gender):
    """An AMKA: DDMMYY, a 3 digit serial, a digit that is odd for men and even for women, and
    the Luhn check digit (python-stdnum, stdnum/gr/amka.py)."""
    serial = "%03d" % rng.randrange(1000)
    parity = rng.choice("13579" if gender == "M" else "02468")
    body = "%02d%02d%02d%s%s" % (birth_date.day, birth_date.month, birth_date.year % 100,
                                 serial, parity)
    return body + luhn_check_digit(body)


def albanian_nid(rng, birth_date, gender):
    """An Albanian NID: a letter for the decade of birth (A is the 1900s, M the 2020s) and a
    digit for the year, the month (plus 50 for women), the day, a 3 digit serial and a check
    letter. The check letter is synthetic: its algorithm is not public, so this is not a valid
    NID. Sources: python-stdnum stdnum/al/nipt.py, the OECD TIN page of Albania (example
    I05101999Q is a woman born 1 January 1980)."""
    decade = birth_date.year // 10 - 190
    if not 0 <= decade <= 12:
        raise ValueError("an Albanian NID needs a birth year from 1900 to 2029: %s" % birth_date)
    month = birth_date.month + (50 if gender == "F" else 0)
    body = "%s%d%02d%02d%03d" % (chr(ord("A") + decade), birth_date.year % 10, month,
                                 birth_date.day, rng.randrange(1000))
    return body + rng.choice(string.ascii_uppercase)


def blood_type(country, patient_id):
    """A blood type drawn from the frequencies of the country."""
    draw = seeded(country, patient_id, "blood_type").random() * sum(BLOOD_FREQUENCIES[country])
    for name, weight in zip(BLOOD_TYPES, BLOOD_FREQUENCIES[country]):
        draw -= weight
        if draw < 0:
            return name
    return BLOOD_TYPES[-1]


def mobile_phone(country, patient_id):
    """A mobile number: +30 69X XXX XXXX or +355 6X XXX XXXX."""
    rng = seeded(country, patient_id, "phone")
    if country == "gr":
        return "+30 69%s %03d %04d" % (rng.choice(GREEK_MOBILE_THIRD_DIGIT),
                                       rng.randrange(1000), rng.randrange(10000))
    return "+355 %s %03d %04d" % (rng.choice(ALBANIAN_MOBILE_PREFIXES), rng.randrange(1000),
                                  rng.randrange(10000))


def national_id_function(country):
    """A function row -> national id; ids are unique within a run."""
    make = amka if country == "gr" else albanian_nid
    used = set()

    def national_id(row):
        birth = datetime.date.fromisoformat(row["BIRTHDATE"])
        for attempt in range(1000):
            purpose = "national_id" if attempt == 0 else "national_id:%d" % attempt
            value = make(seeded(country, row["Id"], purpose), birth, row["GENDER"])
            if value not in used:
                used.add(value)
                return value
        raise ValueError("no unique national id for patient " + row["Id"])
    return national_id


# ---- CSV ----------------------------------------------------------------------------------

def process_csv(src, dst, drop=(), blank=(), value_map=None, row_filters=(), computed=()):
    """Copy one CSV file, dropping and blanking columns, mapping values and dropping rows.

    row_filters is a list of (column, codes): rows whose value in the column is in codes are
    dropped. Every named column must exist: a missing one means Synthea's format has changed.
    computed is a list of (old column or None, new column, function): the function gets the
    original row as a dict; the value replaces the old column (which is renamed) or, with None,
    is appended as a new last column. Returns (rows read, rows written).
    """
    value_map = value_map or {}
    drop, blank = set(drop), set(blank)
    with open(src, newline="", encoding="utf-8") as fin, \
            open(dst, "w", newline="", encoding="utf-8") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout, lineterminator="\n")
        header = next(reader)
        named = (drop | blank | set(value_map) | {col for col, _ in row_filters}
                 | {old for old, _, _ in computed if old})
        missing = sorted(named - set(header))
        if missing:
            raise ValueError("%s has no column %s" % (os.path.basename(src), ", ".join(missing)))
        index = {name: i for i, name in enumerate(header)}
        keep = [i for i, name in enumerate(header) if name not in drop]
        blank_at = {index[c] for c in blank}
        maps_at = {index[c]: m for c, m in value_map.items()}
        filters_at = [(index[c], codes) for c, codes in row_filters]
        replaced = {index[old]: (new, fn) for old, new, fn in computed if old}
        appended = [(new, fn) for old, new, fn in computed if not old]
        writer.writerow([replaced[i][0] if i in replaced else header[i] for i in keep]
                        + [new for new, _ in appended])
        read = written = 0
        for row in reader:
            read += 1
            if any(row[i] in codes for i, codes in filters_at):
                continue
            for i in blank_at:
                row[i] = ""
            for i, m in maps_at.items():
                row[i] = m.get(row[i], row[i])
            if computed:
                original = dict(zip(header, row))
                for i, (_, fn) in replaced.items():
                    row[i] = fn(original)
                extra = [fn(original) for _, fn in appended]
            else:
                extra = []
            writer.writerow([row[i] for i in keep] + extra)
            written += 1
    return read, written


# ---- text ---------------------------------------------------------------------------------

def process_text(src, dst, steps, panel_titles):
    """Copy one patient text file, removing the Race and Ethnicity lines and PRAPARE blocks.

    A PRAPARE block is the dated line that starts with the panel title and the bullet lines
    (indented "- question answer") below it. Returns the number of lines removed.
    """
    with open(src, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out, removed, i = [], 0, 0
    in_header = True  # before the first line of dashes
    while i < len(lines):
        line = lines[i]
        if in_header and line.startswith("-----"):
            in_header = False
        if "race" in steps and in_header and RACE_TEXT_LINE.match(line):
            removed += 1
            i += 1
            continue
        if "sdoh" in steps:
            dated = TEXT_DATED.match(line)
            if dated and any(dated.group(1).startswith(t) for t in panel_titles):
                j = i + 1
                while j < len(lines) and TEXT_BULLET.match(lines[j]):
                    j += 1
                removed += j - i
                i = j
                continue
        out.append(line)
        i += 1
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(out))
    return removed


def replacement_module_warning(input_dir, modules_dir):
    """A warning if the run still holds PRAPARE rows: it was made without -d config/common/modules.

    The empty replacement modules remove the questionnaire (and the homelessness and abuse
    screening output) at the source, so any PRAPARE row means they were not loaded.
    """
    path = os.path.join(input_dir, "csv", "observations.csv")
    if not os.path.exists(path):
        return None
    codes, _ = prapare(modules_dir)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        column = header.index("CODE")
        found = sum(1 for row in reader if row[column] in codes)
    if found:
        return ("%d PRAPARE observation rows found: the run seems to have been made without "
                "-d config/common/modules, so the SDoH, homelessness and abuse screening "
                "modules were not replaced (select the sdoh step to drop the questionnaire)"
                % found)
    return None


# ---- run ----------------------------------------------------------------------------------

def plan_for(filename, steps, sdoh_codes, country):
    drop, blank, value_map, filters, computed = [], [], {}, [], []
    if "costs" in steps:
        drop += COST_COLUMNS.get(filename, [])
    if "race" in steps:
        drop += RACE_COLUMNS.get(filename, [])
    if "prefix" in steps:
        blank += PREFIX_COLUMNS.get(filename, [])
    if "virtual" in steps:
        value_map.update(VIRTUAL_MAP.get(filename, {}))
    if "sdoh" in steps and filename in SDOH_ROW_FILTER:
        filters.append((SDOH_ROW_FILTER[filename], sdoh_codes))
    if filename == "patients.csv":
        if "national_id" in steps:
            computed.append(("SSN", "NATIONAL_ID", national_id_function(country)))
        if "phone" in steps:
            computed.append((None, "PHONE", lambda row: mobile_phone(country, row["Id"])))
        if "blood_type" in steps:
            computed.append((None, "BLOOD_TYPE", lambda row: blood_type(country, row["Id"])))
    return drop, blank, value_map, filters, computed


def run(input_dir, output_dir, steps, modules_dir, country="gr"):
    """Post-process input_dir/{csv,text} into output_dir/{csv,text}; returns a summary dict."""
    if country not in BLOOD_FREQUENCIES:
        raise ValueError("unknown country: " + country)
    unknown = [s for s in steps if s not in STEPS + OPTIONAL_STEPS]
    if unknown:
        raise ValueError("unknown step(s): " + ", ".join(unknown))
    if os.path.abspath(output_dir) == os.path.abspath(input_dir):
        raise ValueError("the output folder must differ from the input folder")
    sdoh_codes, panel_titles = prapare(modules_dir) if "sdoh" in steps else (set(), [])
    summary = {"csv": {}, "text_files": 0, "text_lines_removed": 0, "warnings": []}
    csv_in, csv_out = os.path.join(input_dir, "csv"), os.path.join(output_dir, "csv")
    os.makedirs(csv_out, exist_ok=True)
    for name in sorted(os.listdir(csv_in)):
        if not name.endswith(".csv"):
            continue
        drop, blank, value_map, filters, computed = plan_for(name, steps, sdoh_codes, country)
        src, dst = os.path.join(csv_in, name), os.path.join(csv_out, name)
        if not (drop or blank or value_map or filters or computed):
            shutil.copyfile(src, dst)
            continue
        read, written = process_csv(src, dst, drop, blank, value_map, filters, computed)
        summary["csv"][name] = {"rows": read, "dropped_rows": read - written,
                                "dropped_columns": list(drop), "blanked_columns": list(blank),
                                "computed_columns": [new for _, new, _ in computed]}
    text_in = os.path.join(input_dir, "text")
    if os.path.isdir(text_in):
        text_out = os.path.join(output_dir, "text")
        os.makedirs(text_out, exist_ok=True)
        for name in sorted(os.listdir(text_in)):
            if name.endswith(".txt"):
                summary["text_lines_removed"] += process_text(
                    os.path.join(text_in, name), os.path.join(text_out, name), steps,
                    panel_titles)
                summary["text_files"] += 1
    if "sdoh" not in steps:
        warning = replacement_module_warning(input_dir, modules_dir)
        if warning:
            summary["warnings"].append(warning)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--country", required=True, choices=["gr", "al"])
    parser.add_argument("--input", help="Synthea output folder (default output/<country>)")
    parser.add_argument("--output", help="default <input>/postprocessed")
    parser.add_argument("--steps", default=",".join(STEPS),
                        help="comma separated, default: " + ",".join(STEPS)
                        + "; also available: " + ",".join(OPTIONAL_STEPS))
    parser.add_argument("--modules-dir", default=os.path.join("src", "main", "resources", "modules"))
    args = parser.parse_args(argv)
    input_dir = args.input or os.path.join("output", args.country)
    output_dir = args.output or os.path.join(input_dir, "postprocessed")
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    summary = run(input_dir, output_dir, steps, args.modules_dir, args.country)
    for name, s in summary["csv"].items():
        print("%-18s rows %9d  dropped rows %8d  dropped columns %s  blanked %s  new %s" % (
            name, s["rows"], s["dropped_rows"], s["dropped_columns"] or "-",
            s["blanked_columns"] or "-", s["computed_columns"] or "-"))
    print("text files %d, lines removed %d -> %s" % (
        summary["text_files"], summary["text_lines_removed"], output_dir))
    for warning in summary["warnings"]:
        print("WARNING: " + warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
