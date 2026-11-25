package org.mitre.synthea.modules;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.gson.Gson;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.Test;

/**
 * Checks the immunization schedule files of the localized configurations, which the main
 * Immunizations tests (US schedule) do not cover.
 */
public class ImmunizationScheduleFilesTest {

  @SuppressWarnings("unchecked")
  private static Map<String, Map<String, Object>> load(String country) throws IOException {
    String json = new String(
        Files.readAllBytes(Paths.get("config/" + country + "/immunization_schedule.json")),
        StandardCharsets.UTF_8);
    return new Gson().fromJson(json, Map.class);
  }

  @SuppressWarnings("unchecked")
  private void checkWellFormed(String country) throws IOException {
    Map<String, Map<String, Object>> schedule = load(country);
    assertFalse(country, schedule.isEmpty());
    for (Map.Entry<String, Map<String, Object>> entry : schedule.entrySet()) {
      String name = country + "/" + entry.getKey();
      Map<String, String> code = (Map<String, String>) entry.getValue().get("code");
      assertEquals(name, "http://hl7.org/fhir/sid/cvx", code.get("system"));
      assertTrue(name, code.get("code") != null && code.get("display") != null);
      List<Double> months = (List<Double>) entry.getValue().get("at_months");
      assertFalse(name, months.isEmpty());
      for (int i = 1; i < months.size(); i++) {
        assertTrue(name + " at_months must increase", months.get(i) > months.get(i - 1));
      }
      assertTrue(name, (Double) entry.getValue().get("first_available") >= 1900);
    }
    // each CVX code is used by one entry, so the dose count by code is unambiguous
    Set<String> codes = new HashSet<>();
    for (Map<String, Object> value : schedule.values()) {
      assertTrue(country, codes.add(((Map<String, String>) value.get("code")).get("code")));
    }
  }

  @Test
  public void greeceIsWellFormed() throws IOException {
    checkWellFormed("gr");
  }

  @Test
  public void albaniaIsWellFormed() throws IOException {
    checkWellFormed("al");
  }

  @SuppressWarnings("unchecked")
  @Test
  public void greeceSpotChecks() throws IOException {
    Map<String, Map<String, Object>> s = load("gr");
    assertEquals(List.of(2.0, 4.0, 6.0, 15.0, 48.0), s.get("dtap").get("at_months"));
    assertEquals(List.of(12.0, 24.0), s.get("mmr").get("at_months"));
    assertEquals(List.of(24.0, 30.0), s.get("hepa").get("at_months"));
    assertEquals(List.of(720.0, 722.0), s.get("zoster").get("at_months"));
    // the two rotavirus doses common to both products
    assertEquals(List.of(2.0, 4.0), s.get("rotavirus").get("at_months"));
    // adults: yearly from 60 years; children 6 months to 5 years are a separate entry
    List<Double> flu = (List<Double>) s.get("flu").get("at_months");
    assertEquals(720.0, flu.get(0), 0.0);
    List<Double> child = (List<Double>) s.get("flu_child").get("at_months");
    assertEquals(List.of(6.0, 18.0, 30.0, 42.0, 54.0), child);
    assertEquals(2007.0, (Double) s.get("flu").get("first_available"), 0.0);
    assertEquals(2024.0, (Double) s.get("flu_child").get("first_available"), 0.0);
  }

  @Test
  public void greeceRsvIsOneDoseFrom75() throws IOException {
    Map<String, Map<String, Object>> s = load("gr");
    assertEquals(List.of(900.0), s.get("rsv").get("at_months"));
    assertEquals(2025.0, (Double) s.get("rsv").get("first_available"), 0.0);
  }

  @Test
  public void greeceAvailabilityYears() throws IOException {
    Map<String, Map<String, Object>> s = load("gr");
    // years from the WHO vaccine introduction data
    assertEquals(2000.0, (Double) s.get("hepb").get("first_available"), 0.0);
    assertEquals(2011.0, (Double) s.get("rotavirus").get("first_available"), 0.0);
    assertEquals(2008.0, (Double) s.get("var").get("first_available"), 0.0);
    assertEquals(2009.0, (Double) s.get("hpv").get("first_available"), 0.0);
  }

  @Test
  public void albaniaAvailabilityYears() throws IOException {
    Map<String, Map<String, Object>> s = load("al");
    assertEquals(1960.0, (Double) s.get("bcg").get("first_available"), 0.0);
    assertEquals(2009.0, (Double) s.get("penta").get("first_available"), 0.0);
    assertEquals(2019.0, (Double) s.get("rota").get("first_available"), 0.0);
    assertEquals(2022.0, (Double) s.get("hpv").get("first_available"), 0.0);
  }

  @SuppressWarnings("unchecked")
  @Test
  public void albaniaSpotChecks() throws IOException {
    Map<String, Map<String, Object>> s = load("al");
    assertEquals(List.of(2.0, 4.0, 6.0), s.get("penta").get("at_months"));
    assertEquals(List.of(12.0, 60.0), s.get("mmr").get("at_months"));
    assertEquals(List.of(156.0, 216.0), s.get("td").get("at_months"));
    // IPV only at 2 and 4 months; the later polio doses are OPV
    assertEquals(List.of(2.0, 4.0), s.get("ipv").get("at_months"));
    assertEquals(List.of(6.0, 24.0, 72.0), s.get("bopv").get("at_months"));
    assertEquals(List.of(2.0, 4.0, 6.0), s.get("rota").get("at_months"));
    // the national calendar has no adult or influenza vaccines
    assertFalse(s.containsKey("flu"));
  }
}
