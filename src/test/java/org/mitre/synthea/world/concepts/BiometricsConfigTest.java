package org.mitre.synthea.world.concepts;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;

import java.util.List;

import org.junit.Test;
import org.mitre.synthea.helpers.SimpleYML;

public class BiometricsConfigTest {
  private static final SimpleYML BASE = new SimpleYML(
      "lifecycle:\n  adult_weight_gain: [1.0,2.0]\n  adult_max_weight_age: 49\n"
      + "metabolic:\n  blood_pressure:\n    normal:\n      systolic: [100,139]\n");

  @Test
  public void withoutAnOverrideTheBaseIsUsed() {
    assertNull(BiometricsConfig.loadOverride(""));
    assertNull(BiometricsConfig.loadOverride(null));
    assertEquals(49, BiometricsConfig.lookup("lifecycle.adult_max_weight_age", null, BASE));
  }

  @Test
  public void overriddenKeysWinAndOthersFallBack() {
    SimpleYML override = new SimpleYML("lifecycle:\n  adult_weight_gain: [0.2,0.6]\n");
    List<?> gain = (List<?>) BiometricsConfig.lookup("lifecycle.adult_weight_gain", override, BASE);
    assertEquals(0.2, ((Number) gain.get(0)).doubleValue(), 0.0001);
    assertEquals(0.6, ((Number) gain.get(1)).doubleValue(), 0.0001);
    // not in the override: the base value
    assertEquals(49, BiometricsConfig.lookup("lifecycle.adult_max_weight_age", override, BASE));
    // a whole section missing from the override: the base value
    assertNotNull(BiometricsConfig.lookup("metabolic.blood_pressure.normal.systolic",
        override, BASE));
  }

  @Test
  public void theShippedFileIsUnchangedByDefault() {
    // no override property is set in the test configuration
    assertEquals(49, BiometricsConfig.get("lifecycle.adult_max_weight_age"));
    double[] gain = BiometricsConfig.doubles("lifecycle.adult_weight_gain");
    assertEquals(1.0, gain[0], 0.0001);
    assertEquals(2.0, gain[1], 0.0001);
  }
}
