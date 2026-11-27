#!/usr/bin/env python3
"""Validate the per-country geography and provider files in config/<cc>/.

Usage: python3 scripts/validate_geography.py [config_dir ...]   (default: config/gr config/al)
Exits 1 if any check fails.
"""
import csv
import os
import sys

TOL = 1e-6
GROUPS = {
    'gender': ['TOT_MALE', 'TOT_FEMALE'],
    'race': ['WHITE', 'BLACK', 'ASIAN', 'NATIVE', 'OTHER'],
    'age': [str(i) for i in range(1, 19)],
    'income': ['00..10', '10..15', '15..25', '25..35', '35..50', '50..75', '75..100',
               '100..150', '150..200', '200..999'],
    'education': ['LESS_THAN_HS', 'HS_DEGREE', 'SOME_COLLEGE', 'BS_DEGREE'],
}


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


PROVIDER_COLUMNS = ['id', 'name', 'state', 'LAT', 'LON', 'emergency']
PROVIDER_MARGIN = 1.0  # degrees around the settlements


def properties(*paths):
    props = {}
    for path in paths:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    props[k.strip()] = v.strip()
    return props


def validate_providers(cfg, demo, zips):
    errors = []
    common = os.path.join(os.path.dirname(cfg.rstrip('/')), 'common', 'synthea.properties')
    props = properties(common, cfg.rstrip('/') + '/synthea.properties')
    states = {r['STNAME'] for r in demo}
    lats = [float(z['LAT']) for z in zips]
    lons = [float(z['LON']) for z in zips]
    seen = {}
    for key, path in sorted(props.items()):
        if not (key.startswith('generate.providers.') and key.endswith('.default_file')):
            continue
        if not path.startswith('config/'):
            continue  # a US default file, not ours
        if not os.path.exists(path):
            errors.append('%s: file %s does not exist' % (key, path))
            continue
        rows = read(path)
        with open(path, encoding='utf-8') as f:
            header = next(csv.reader(f))
        missing = [c for c in PROVIDER_COLUMNS if c not in header]
        if missing:
            errors.append('%s: missing columns %s' % (path, missing))
            continue
        for r in rows:
            who = '%s: %s' % (path, r['name'])
            if r['state'] not in states:
                errors.append(who + ': state %r is not a demographics STNAME' % r['state'])
            if r['id'] in seen:
                errors.append(who + ': id %s also used in %s' % (r['id'], seen[r['id']]))
            seen[r['id']] = path
            try:
                la, lo = float(r['LAT']), float(r['LON'])
            except ValueError:
                errors.append(who + ': LAT/LON are not numbers')
                continue
            near = (min(lats) - PROVIDER_MARGIN <= la <= max(lats) + PROVIDER_MARGIN
                    and min(lons) - PROVIDER_MARGIN <= lo <= max(lons) + PROVIDER_MARGIN)
            if not near and 'dialysis' not in path:
                errors.append(who + ': more than %g degree from the settlements' % PROVIDER_MARGIN)
    return errors


SDOH_COLUMNS = ['FOOD_INSECURITY', 'SEVERE_HOUSING_COST_BURDEN', 'UNEMPLOYED',
                'NO_VEHICLE_ACCESS', 'UNINSURED']


def validate_sdoh(cfg, demo):
    """SDoH is switched off: the file must cover every STNAME and every probability must be 0."""
    errors = []
    path = cfg.rstrip('/') + '/geography/sdoh.csv'
    try:
        rows = read(path)
    except OSError:
        return [path + ': does not exist']
    states = {r['STNAME'] for r in demo}
    covered = {r['STATE'] for r in rows}
    for st in sorted(states - covered):
        errors.append('%s: no row for state %r' % (path, st))
    for r in rows:
        for c in SDOH_COLUMNS:
            try:
                if float(r[c]) != 0.0:
                    errors.append('%s: %s/%s is %s, not 0' % (path, r['STATE'], c, r[c]))
            except (KeyError, ValueError):
                errors.append('%s: missing or non-numeric %s' % (path, c))
    return errors


def validate(cfg):
    errors = []
    geo = cfg.rstrip('/') + '/geography/'
    demo = read(geo + 'demographics.csv')
    zips = read(geo + 'zipcodes.csv')
    tzs = read(geo + 'timezones.csv')
    if not demo:
        errors.append('demographics.csv has no rows')
    ids = [r['ID'] for r in demo]
    if len(ids) != len(set(ids)):
        errors.append('demographics.csv: duplicate ID')
    zip_places = {(z['USPS'], z['NAME']) for z in zips}
    tz_states = {t['STATE'] for t in tzs}
    for r in demo:
        who = '%s/%s' % (r['STNAME'], r['NAME'])
        try:
            if int(r['POPESTIMATE2015']) <= 0:
                errors.append(who + ': POPESTIMATE2015 must be positive')
        except ValueError:
            errors.append(who + ': POPESTIMATE2015 is not an integer')
        for group, cols in GROUPS.items():
            try:
                total = sum(float(r[c]) for c in cols)
            except (KeyError, ValueError):
                errors.append('%s: missing or non-numeric %s column' % (who, group))
                continue
            if abs(total - 1.0) > TOL:
                errors.append('%s: %s sums to %.6f, not 1' % (who, group, total))
        if (r['STNAME'], r['NAME']) not in zip_places:
            errors.append(who + ': no row in zipcodes.csv')
        if r['STNAME'] not in tz_states:
            errors.append(who + ': state has no row in timezones.csv')
    demo_places = {(r['STNAME'], r['NAME']) for r in demo}
    for z in zips:
        if (z['USPS'], z['NAME']) not in demo_places:
            errors.append('zipcodes.csv: %s/%s is not in demographics.csv' % (z['USPS'], z['NAME']))
    errors += validate_providers(cfg, demo, zips)
    errors += validate_sdoh(cfg, demo)
    return errors, len(demo)


def main(argv):
    dirs = argv or ['config/gr', 'config/al']
    failed = False
    for cfg in dirs:
        errors, n = validate(cfg)
        print('%s: %d settlements, providers checked, %s' % (cfg, n, 'OK' if not errors else '%d problem(s)' % len(errors)))
        for e in errors:
            print('  -', e)
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
