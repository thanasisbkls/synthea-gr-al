package org.mitre.synthea.modules;

import static org.junit.Assert.assertEquals;

import org.junit.Test;
import org.mitre.synthea.world.agents.Person;

public class CardiovascularDiseaseModuleTest {
  @Test
  public void factorsOfOneKeepTheBuiltInRisks() {
    Person person = new Person(1L);
    CardiovascularDiseaseModule.storeMonthlyRisks(person, 0.001, 1.0, 1.0);
    assertEquals(0.001, (double) person.attributes.get("mi_risk"), 1e-12);
    assertEquals(0.005, (double) person.attributes.get("ihd_risk"), 1e-12);
  }

  @Test
  public void factorsScaleTheRisksSeparately() {
    Person person = new Person(1L);
    CardiovascularDiseaseModule.storeMonthlyRisks(person, 0.001, 0.4, 0.1);
    assertEquals(0.0004, (double) person.attributes.get("mi_risk"), 1e-12);
    assertEquals(0.0005, (double) person.attributes.get("ihd_risk"), 1e-12);
  }

  @Test
  public void risksNeverExceedOne() {
    Person person = new Person(1L);
    CardiovascularDiseaseModule.storeMonthlyRisks(person, 0.5, 10.0, 10.0);
    assertEquals(1.0, (double) person.attributes.get("mi_risk"), 0.0);
    assertEquals(1.0, (double) person.attributes.get("ihd_risk"), 0.0);
  }
}
