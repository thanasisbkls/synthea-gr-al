package org.mitre.synthea.modules;

import static org.junit.Assert.assertEquals;

import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;

import org.junit.AfterClass;
import org.junit.Assert;
import org.junit.BeforeClass;
import org.junit.Test;
import org.mitre.synthea.helpers.PhysiologyValueGenerator;
import org.mitre.synthea.helpers.Utilities;
import org.mitre.synthea.world.agents.Person;
import org.mitre.synthea.world.concepts.VitalSign;

public class LifecycleModuleTest {
  public static boolean deathByNaturalCauses;

  @BeforeClass
  public static void before() {
    deathByNaturalCauses = LifecycleModule.ENABLE_DEATH_BY_NATURAL_CAUSES;
  }

  @AfterClass
  public static void after() {
    LifecycleModule.ENABLE_DEATH_BY_NATURAL_CAUSES = deathByNaturalCauses;
  }

  @Test
  public void testDeathByNaturalCauses() {
    LifecycleModule.ENABLE_DEATH_BY_NATURAL_CAUSES = true;
    Person person = new Person(0L);
    long time = System.currentTimeMillis();
    long birth = time - Utilities.convertTime("years", 100);
    person.attributes.put(Person.BIRTHDATE, birth);
    for (int i = 0; i < 100000; i++) {
      LifecycleModule.death(person, time);
    }
    assertEquals(false, person.alive(time));
  }

  @Test
  public void testLikelihoodOfDeathInputs() {
    // should handle zero to very old
    for (int age = 0; age < 100; age++) {
      double likelihood = LifecycleModule.likelihoodOfDeath(age);
      Assert.assertTrue(likelihood >= 0);
    }
  }

  @Test
  public void testAdherenceFade() {
    Person person = new Person(0L);
    long time = System.currentTimeMillis();
    person.attributes.put(Person.ADHERENCE, true);
    person.attributes.put(LifecycleModule.ADHERENCE_PROBABILITY, 1.0);
    for (int i = 0; i < 5; i++) {
      double before = (Double) person.attributes.get(LifecycleModule.ADHERENCE_PROBABILITY);
      LifecycleModule.adherence(person, time);
      double after = (Double) person.attributes.get(LifecycleModule.ADHERENCE_PROBABILITY);
      Assert.assertTrue(after < before);
    }
  }

  @Test
  public void testPercentileForBMI() {
    double percentile = LifecycleModule.percentileForBMI(18.37736191, "M", 26);
    Assert.assertEquals(0.9, percentile, 0.01);
  }

  @Test
  public void lookupGrowthChart() {
    // Uncomment to check performance.
    // long start = System.currentTimeMillis();
    // for (int i = 0; i < 1000000; i++) {
    double height = LifecycleModule.lookupGrowthChart("height", "M", 24, 0.5);
    Assert.assertEquals(86.86160934, height, 0.01);
    // }
    // long end = System.currentTimeMillis();
    // System.out.println("Time to complete: " + (end - start));
  }

  @Test
  public void lookupHeadCircumference() {
    double head = LifecycleModule.lookupGrowthChart("head", "F", 36, 0.9);
    Assert.assertEquals(50.57, head, 0.01);
  }

  @Test
  public void testPhysiologyEnabled() {
    boolean enablePhysiology = LifecycleModule.ENABLE_PHYSIOLOGY_GENERATORS;
    LifecycleModule.ENABLE_PHYSIOLOGY_GENERATORS = true;
    Person person = new Person(0L);

    // Need to set some attributes for birth to work properly
    person.attributes.put(Person.GENDER, "F");
    person.attributes.put(Person.RACE, "white");
    person.attributes.put(Person.ETHNICITY, "english");

    LifecycleModule.birth(person, 0);

    // Person should have some PhysiologyValueGenerators
    Assert.assertEquals(person.vitalSigns.get(VitalSign.SYSTOLIC_BLOOD_PRESSURE).getClass(),
        PhysiologyValueGenerator.class);
    Assert.assertEquals(person.vitalSigns.get(VitalSign.DIASTOLIC_BLOOD_PRESSURE).getClass(),
        PhysiologyValueGenerator.class);

    LifecycleModule.ENABLE_PHYSIOLOGY_GENERATORS = enablePhysiology;
  }

  @Test
  public void testPassportFormatIsAlwaysEightDigits() throws Exception {
    Pattern eightDigitPassport = Pattern.compile("^X\\d{8}X$");
    int sampleSize = 2000;
    int issued = 0;

    java.lang.reflect.Method ageMethod = LifecycleModule.class.getDeclaredMethod(
        "age", Person.class, long.class);
    ageMethod.setAccessible(true);

    for (int i = 0; i < sampleSize; i++) {
      Person person = new Person(i);
      person.attributes.put(Person.GENDER, "F");
      person.attributes.put(Person.RACE, "white");
      person.attributes.put(Person.ETHNICITY, "english");
      long birth = 0L;
      LifecycleModule.birth(person, birth);

      long candidateTime = birth + Utilities.convertTime("years", 20);
      while (person.ageInYears(candidateTime) < 20) {
        candidateTime += Utilities.convertTime("days", 1);
      }

      ageMethod.invoke(null, person, candidateTime);

      String passport = (String) person.attributes.get(Person.IDENTIFIER_PASSPORT);
      if (passport != null) {
        issued++;
        Assert.assertTrue("Passport not 8 digits: " + passport,
            eightDigitPassport.matcher(passport).matches());
      }
    }
    Assert.assertTrue("Expected at least some passports to be issued", issued > 0);
  }

  @Test
  public void testAdultWeightGainYearlyIsUnchanged() {
    double[] range = {1.0, 2.0};
    Person person = new Person(7L);
    Person reference = new Person(7L);
    for (int i = 0; i < 5; i++) {
      assertEquals(reference.rand(range), LifecycleModule.adultWeightGain(person, false, range),
          0.0);
    }
    Assert.assertNull(person.attributes.get(LifecycleModule.ADULT_WEIGHT_GAIN_RATE));
  }

  @Test
  public void testAdultWeightGainPerPersonIsDrawnOnce() {
    double[] range = {0.0, 2.0};
    Person person = new Person(7L);
    double first = LifecycleModule.adultWeightGain(person, true, range);
    Assert.assertTrue(first >= 0.0 && first <= 2.0);
    for (int i = 0; i < 5; i++) {
      assertEquals(first, LifecycleModule.adultWeightGain(person, true, range), 0.0);
    }
    // same seed, same rate; another seed, another rate
    assertEquals(first, LifecycleModule.adultWeightGain(new Person(7L), true, range), 0.0);
    Assert.assertNotEquals(first, LifecycleModule.adultWeightGain(new Person(8L), true, range),
        0.0);
  }

  @Test
  public void testBuiltInDeathRisksAreUnchanged() {
    // no death risk file is set in the test configuration: the built-in United States risks
    double yearly = LifecycleModule.usYearlyRisk(80);
    assertEquals(4877.3 / 100_000.0, yearly, 1e-12);
    double expected = Utilities.convertRiskToTimestep(yearly, TimeUnit.DAYS.toMillis(365));
    assertEquals(expected, LifecycleModule.likelihoodOfDeath(80), 1e-12);
    assertEquals(0.5, LifecycleModule.usYearlyRisk(100), 0.0);
  }

  @Test
  public void testDeathRisksFromFile() {
    LifecycleModule.DeathRisks risks = new LifecycleModule.DeathRisks(
        "min_age,max_age,deaths_per_100000\n0,0,300\n1,64,50\n65,84,2000\n85,120,16000\n");
    assertEquals(0.003, risks.yearlyRisk(0), 1e-12);
    assertEquals(0.0005, risks.yearlyRisk(1), 1e-12);
    assertEquals(0.0005, risks.yearlyRisk(64), 1e-12);
    assertEquals(0.02, risks.yearlyRisk(65), 1e-12);
    assertEquals(0.16, risks.yearlyRisk(90), 1e-12);
    // after the last band: the risk of the last band
    assertEquals(0.16, risks.yearlyRisk(150), 1e-12);
  }

  @Test
  public void testDeathRiskFileIsChecked() {
    String header = "min_age,max_age,deaths_per_100000\n";
    for (String bad : new String[] {"", "age,risk\n0,0,5\n", header, header + "1,5,10\n",
        header + "0,5,10\n7,9,10\n", header + "0,5,-1\n", header + "0,5,200000\n",
        header + "5,2,10\n"}) {
      try {
        new LifecycleModule.DeathRisks(bad);
        Assert.fail("Expected an exception for: " + bad);
      } catch (IllegalArgumentException expected) {
        // expected
      }
    }
  }
}
