package org.mitre.synthea.modules.covid;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.util.HashSet;
import java.util.Set;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.mitre.synthea.TestHelper;
import org.mitre.synthea.helpers.Config;
import org.mitre.synthea.world.agents.Person;

public class C19VaccinationConfigTest {
  private static final String TEST_FILE = "covid/test_vaccination.json";

  private static long noon(int year, int month, int day) {
    return LocalDateTime.of(LocalDate.of(year, month, day), LocalTime.NOON)
        .toInstant(ZoneOffset.UTC).toEpochMilli();
  }

  private static Person personBornIn(int year) {
    Person person = new Person(7L);
    person.attributes.put(Person.BIRTHDATE, TestHelper.timestamp(year, 1, 1, 0, 0, 0));
    return person;
  }

  @Before
  public void useTestFile() {
    Config.set(C19VaccinationConfig.PROPERTY, TEST_FILE);
    reinitialize();
  }

  @After
  public void backToUnitedStates() {
    Config.remove(C19VaccinationConfig.PROPERTY);
    reinitialize();
  }

  private static void reinitialize() {
    C19Vaccine.initialize();
    C19VaccineAgeDistributions.initialize();
  }

  @Test
  public void readsTheFile() {
    C19VaccinationConfig config = C19VaccinationConfig.get();
    assertNotNull(config);
    // rules and periods are sorted by date even if the file lists them in another order
    assertEquals(noon(2021, 3, 1), config.firstPossibleShotTime());
    assertEquals(Long.MAX_VALUE, config.lateAdoptionStartTime());
  }

  @Test
  public void eligibilityFollowsTheRules() {
    C19VaccinationConfig config = C19VaccinationConfig.get();
    assertFalse(config.eligible(40, noon(2021, 2, 28)));
    assertTrue(config.eligible(40, noon(2021, 3, 1)));
    assertFalse(config.eligible(15, noon(2021, 5, 31)));
    assertTrue(config.eligible(15, noon(2021, 6, 1)));
    assertFalse(config.eligible(11, noon(2021, 12, 1)));
    // nobody starts a vaccination after the last date of the file
    assertTrue(config.eligible(40, noon(2021, 12, 31)));
    assertFalse(config.eligible(40, noon(2022, 1, 2)));
    assertFalse(config.eligible(15, noon(2030, 1, 1)));
  }

  @Test
  public void moduleUsesTheConfiguredEligibility() {
    Person adult = personBornIn(1980);
    Person teen = personBornIn(2006);
    assertFalse(C19ImmunizationModule.eligibleForShot(adult, noon(2021, 2, 1)));
    assertTrue(C19ImmunizationModule.eligibleForShot(adult, noon(2021, 3, 2)));
    assertFalse(C19ImmunizationModule.eligibleForShot(teen, noon(2021, 5, 1)));
    assertTrue(C19ImmunizationModule.eligibleForShot(teen, noon(2021, 6, 2)));
  }

  @Test
  public void vaccineMixFollowsTheLatestStartedPeriod() {
    C19VaccinationConfig config = C19VaccinationConfig.get();
    Set<String> april = new HashSet<>();
    Set<String> may = new HashSet<>();
    for (int i = 0; i < 200; i++) {
      Person person = new Person(i);
      assertEquals("PFIZER", config.selectVaccine(person, noon(2021, 3, 15)));
      april.add(config.selectVaccine(person, noon(2021, 4, 15)));
      assertEquals("JANSSEN", config.selectVaccine(person, noon(2021, 5, 15)));
      may.add(config.selectVaccine(person, noon(2021, 5, 15)));
    }
    assertEquals(Set.of("PFIZER", "ASTRAZENECA"), april);
    assertEquals(Set.of("JANSSEN"), may);
  }

  @Test
  public void vaccineSelectionIsDeterministic() {
    C19VaccinationConfig config = C19VaccinationConfig.get();
    for (int i = 0; i < 20; i++) {
      assertEquals(config.selectVaccine(new Person(i), noon(2021, 4, 15)),
          config.selectVaccine(new Person(i), noon(2021, 4, 15)));
    }
  }

  @Test
  public void moduleUsesTheConfiguredVaccines() {
    assertEquals(C19Vaccine.EUASet.PFIZER,
        C19ImmunizationModule.selectVaccine(new Person(1), noon(2021, 3, 15)));
    C19Vaccine astra = C19Vaccine.EUAs.get(C19Vaccine.EUASet.ASTRAZENECA);
    assertEquals("210", astra.getCvx());
    assertTrue(astra.isTwoDose());
    assertEquals(56L * 24 * 60 * 60 * 1000, astra.getTimeBetweenDoses());
    assertFalse(C19Vaccine.EUAs.get(C19Vaccine.EUASet.JANSSEN).isTwoDose());
    // only the vaccines of the file
    assertEquals(3, C19Vaccine.EUAs.size());
  }

  @Test
  public void ageRangesAcceptBothFormats() {
    C19VaccineAgeDistributions.AgeRange range = new C19VaccineAgeDistributions.AgeRange("18-24");
    assertTrue(range.in(18) && range.in(24));
    assertFalse(range.in(17) || range.in(25));
    range = new C19VaccineAgeDistributions.AgeRange("80+");
    assertTrue(range.in(80) && range.in(105));
    assertFalse(range.in(79));
    range = new C19VaccineAgeDistributions.AgeRange("Ages_40-49_yrs");
    assertTrue(range.in(40) && range.in(49));
    range = new C19VaccineAgeDistributions.AgeRange("Ages_75+_yrs");
    assertTrue(range.in(75) && range.in(100));
  }

  @Test(expected = IllegalArgumentException.class)
  public void badAgeRangeIsRejected() {
    new C19VaccineAgeDistributions.AgeRange("adults");
  }

  @Test
  public void uptakeAndShotTimesComeFromTheFile() {
    assertEquals(3, C19VaccineAgeDistributions.rawDistributions.size());
    C19VaccineAgeDistributions.AgeRange adults = new C19VaccineAgeDistributions.AgeRange("18-59");
    assertEquals(0.705, C19VaccineAgeDistributions.firstShotProbByAge.get(adults), 1e-9);
    Person person = personBornIn(1980);
    for (int i = 0; i < 20; i++) {
      Person p = new Person(i);
      p.attributes.putAll(person.attributes);
      long shot = C19VaccineAgeDistributions.selectShotTime(p, noon(2021, 3, 2));
      assertTrue(shot == noon(2021, 3, 2) || shot == noon(2021, 3, 3));
    }
    assertEquals(0.9, C19VaccineAgeDistributions.chanceOfGettingShot(
        personBornIn(1940), noon(2021, 3, 2)), 1e-9);
  }

  @Test
  public void unitedStatesBehaviorWhenThePropertyIsEmpty() {
    Config.remove(C19VaccinationConfig.PROPERTY);
    reinitialize();
    assertNull(C19VaccinationConfig.get());
    assertEquals(8, C19VaccineAgeDistributions.rawDistributions.size());
    assertEquals(3, C19Vaccine.EUAs.size());
    assertEquals("208", C19Vaccine.EUAs.get(C19Vaccine.EUASet.PFIZER).getCvx());
    assertEquals(21L * 24 * 60 * 60 * 1000,
        C19Vaccine.EUAs.get(C19Vaccine.EUASet.PFIZER).getTimeBetweenDoses());
    // 16 and over from the first possible shot, 12 and over from 10 May 2021
    Person adult = personBornIn(1980);
    assertTrue(C19ImmunizationModule.eligibleForShot(adult,
        C19ImmunizationModule.FIRST_POSSIBLE_SHOT_TIME));
    Person teen = personBornIn(2008);
    assertFalse(C19ImmunizationModule.eligibleForShot(teen, noon(2021, 5, 9)));
    assertTrue(C19ImmunizationModule.eligibleForShot(teen, noon(2021, 5, 11)));
    assertEquals(C19Vaccine.EUASet.PFIZER, C19ImmunizationModule.selectVaccine(new Person(3),
        C19ImmunizationModule.FIRST_POSSIBLE_SHOT_TIME + 1000));
  }

  @Test
  public void usAgeDistributionsLoadTwiceWithoutDuplicates() {
    Config.remove(C19VaccinationConfig.PROPERTY);
    reinitialize();
    int size = C19VaccineAgeDistributions.rawDistributions
        .get(new C19VaccineAgeDistributions.AgeRange("Ages_75+_yrs")).size();
    C19VaccineAgeDistributions.initialize();
    assertEquals(size, C19VaccineAgeDistributions.rawDistributions
        .get(new C19VaccineAgeDistributions.AgeRange("Ages_75+_yrs")).size());
  }
}
