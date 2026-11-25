package org.mitre.synthea.modules;

import static org.junit.Assert.assertEquals;

import org.junit.After;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;
import org.mitre.synthea.TestHelper;
import org.mitre.synthea.helpers.Config;
import org.mitre.synthea.helpers.Utilities;
import org.mitre.synthea.world.agents.PayerManager;
import org.mitre.synthea.world.agents.Person;
import org.mitre.synthea.world.agents.Provider;
import org.mitre.synthea.world.agents.ProviderTest;
import org.mitre.synthea.world.geography.Location;

/**
 * The wellness intervals and symptom thresholds of the Encounter Module can be set with
 * properties; without them the original values apply.
 */
public class EncounterSettingsTest {
  private static final String[] PROPERTIES = {
      "symptom_threshold.pcp", "symptom_threshold.urgent_care", "symptom_threshold.emergency",
      "wellness.interval_months.age_0_1_months", "wellness.interval_months.age_2_5_months",
      "wellness.interval_months.age_6_17_months",
      "wellness.interval_months.age_18_months_to_3_years",
      "wellness.interval_years.age_4_19", "wellness.interval_years.age_20_39",
      "wellness.interval_years.age_40_49", "wellness.interval_years.age_50_plus",
      "wellness.chronic_medication_max_interval_years"};

  // Other tests leave properties behind (for example one record per provider); these tests need
  // a single record per person, so the properties are set here and restored afterwards.
  private static final String[] RECORD_PROPERTIES = {
      "exporter.split_records", "generate.payers.loss_of_care"};
  private static final String[] savedRecordProperties = new String[RECORD_PROPERTIES.length];

  /**
   * Load the test properties, providers and payers.
   * @throws Exception on configuration loading error
   */
  @BeforeClass
  public static void setup() throws Exception {
    TestHelper.loadTestProperties();
    String testState = Config.get("test_state.default", "Massachusetts");
    Location location = new Location(testState, null);
    Provider.loadProviders(location, ProviderTest.providerRandom);
    PayerManager.loadPayers(new Location(testState, null));
  }

  /** Use one health record per person. */
  @Before
  public void oneRecordPerPerson() {
    for (int i = 0; i < RECORD_PROPERTIES.length; i++) {
      savedRecordProperties[i] = Config.get(RECORD_PROPERTIES[i]);
      Config.set(RECORD_PROPERTIES[i], "false");
    }
  }

  /** Restore the properties of other tests. */
  @After
  public void restoreRecordProperties() {
    for (int i = 0; i < RECORD_PROPERTIES.length; i++) {
      if (savedRecordProperties[i] == null) {
        Config.remove(RECORD_PROPERTIES[i]);
      } else {
        Config.set(RECORD_PROPERTIES[i], savedRecordProperties[i]);
      }
    }
  }

  /** Remove the settings of a test. */
  @After
  public void removeSettings() {
    for (String key : PROPERTIES) {
      Config.remove("generate.encounters." + key);
    }
  }

  private static void set(String key, int value) {
    Config.set("generate.encounters." + key, Integer.toString(value));
  }

  private static Person personBornIn1990() {
    long birth = TestHelper.timestamp(1990, 1, 1, 0, 0, 0);
    Person person = new Person(1L);
    person.attributes.put(Person.BIRTHDATE, birth);
    return person;
  }

  private static long wellnessInterval(EncounterModule module, long ageInMonths, boolean chronic) {
    long birth = TestHelper.timestamp(1990, 1, 1, 0, 0, 0);
    Person person = personBornIn1990();
    if (chronic) {
      person.coverage.setPlanToNoInsurance(birth);
      person.chronicMedications.put("test", person.record.new Medication(birth, "test"));
    }
    long time = birth + Utilities.convertTime("days", ageInMonths * 30.4375);
    return module.recommendedTimeBetweenWellnessVisits(person, time);
  }

  private static long months(int n) {
    return Utilities.convertTime("months", n);
  }

  private static long years(int n) {
    return Utilities.convertTime("years", n);
  }

  @Test
  public void defaultWellnessIntervalsAreTheOriginalOnes() {
    EncounterModule module = new EncounterModule();
    assertEquals(months(1), wellnessInterval(module, 0, false));
    assertEquals(months(2), wellnessInterval(module, 3, false));
    assertEquals(months(3), wellnessInterval(module, 12, false));
    assertEquals(months(6), wellnessInterval(module, 30, false));
    assertEquals(years(1), wellnessInterval(module, 10 * 12, false));
    assertEquals(years(3), wellnessInterval(module, 30 * 12, false));
    assertEquals(years(2), wellnessInterval(module, 45 * 12, false));
    assertEquals(years(1), wellnessInterval(module, 60 * 12, false));
    // chronic medication: at least yearly
    assertEquals(years(1), wellnessInterval(module, 30 * 12, true));
    assertEquals(years(1), wellnessInterval(module, 45 * 12, true));
    assertEquals(months(6), wellnessInterval(module, 30, true));
  }

  @Test
  public void configuredWellnessIntervals() {
    set("wellness.interval_months.age_0_1_months", 2);
    set("wellness.interval_months.age_2_5_months", 3);
    set("wellness.interval_months.age_6_17_months", 4);
    set("wellness.interval_months.age_18_months_to_3_years", 12);
    set("wellness.interval_years.age_4_19", 2);
    set("wellness.interval_years.age_20_39", 5);
    set("wellness.interval_years.age_40_49", 4);
    set("wellness.interval_years.age_50_plus", 3);
    set("wellness.chronic_medication_max_interval_years", 2);
    EncounterModule module = new EncounterModule();
    assertEquals(months(2), wellnessInterval(module, 0, false));
    assertEquals(months(3), wellnessInterval(module, 3, false));
    assertEquals(months(4), wellnessInterval(module, 12, false));
    assertEquals(months(12), wellnessInterval(module, 30, false));
    assertEquals(years(2), wellnessInterval(module, 10 * 12, false));
    assertEquals(years(5), wellnessInterval(module, 30 * 12, false));
    assertEquals(years(4), wellnessInterval(module, 45 * 12, false));
    assertEquals(years(3), wellnessInterval(module, 60 * 12, false));
    // chronic medication caps the interval at the configured maximum
    assertEquals(years(2), wellnessInterval(module, 30 * 12, true));
    assertEquals(years(2), wellnessInterval(module, 60 * 12, true));
    assertEquals(years(2), wellnessInterval(module, 10 * 12, true));
  }

  @Test
  public void veryLongIntervalSwitchesWellnessVisitsOff() {
    set("wellness.interval_years.age_20_39", 200);
    EncounterModule module = new EncounterModule();
    assertEquals(years(200), wellnessInterval(module, 30 * 12, false));
  }

  /** Symptom total 450 is above the urgent care threshold (350) and below emergency (500). */
  private static String symptomDrivenEncounterType(EncounterModule module, int symptomTotal) {
    Person person = new Person(2L);
    person.attributes.put(Person.INCOME, 100000);
    person.attributes.put(Person.BIRTHDATE, TestHelper.timestamp(1970, 1, 1, 0, 0, 0));
    Location location = new Location(Config.get("test_state.default", "Massachusetts"), null);
    location.assignPoint(person, location.randomCityName(person));
    long start = TestHelper.timestamp(2020, 6, 1, 8, 0, 0);
    person.coverage.setPlanToNoInsurance(TestHelper.timestamp(1970, 1, 1, 0, 0, 0));
    person.coverage.setPlanToNoInsurance(start + Utilities.convertTime("years", 1));
    // the first call is the scheduled wellness visit; end it, so that only symptoms can start one
    module.process(person, start);
    module.endEncounterModuleEncounters(person, start + Utilities.convertTime("hours", 1));
    int before = person.record.encounters.size();
    long later = start + Utilities.convertTime("days", 1);
    person.setSymptom("Test", "Test", "Test", later, symptomTotal, false);
    module.process(person, later);
    if (person.record.encounters.size() == before) {
      return "none";
    }
    return person.record.encounters.get(person.record.encounters.size() - 1).type.toLowerCase();
  }

  @Test
  public void defaultSymptomThresholdsAreTheOriginalOnes() {
    EncounterModule module = new EncounterModule();
    assertEquals("urgentcare", symptomDrivenEncounterType(module, 450));
    assertEquals("emergency", symptomDrivenEncounterType(module, 550));
    assertEquals("outpatient", symptomDrivenEncounterType(module, 320));
    assertEquals("none", symptomDrivenEncounterType(module, 250));
  }

  @Test
  public void configuredSymptomThresholds() {
    set("symptom_threshold.emergency", 400);
    assertEquals("emergency", symptomDrivenEncounterType(new EncounterModule(), 450));
    removeSettings();
    set("symptom_threshold.urgent_care", 460);
    assertEquals("outpatient", symptomDrivenEncounterType(new EncounterModule(), 450));
    removeSettings();
    set("symptom_threshold.pcp", 460);
    set("symptom_threshold.urgent_care", 470);
    set("symptom_threshold.emergency", 480);
    assertEquals("none", symptomDrivenEncounterType(new EncounterModule(), 450));
  }
}
