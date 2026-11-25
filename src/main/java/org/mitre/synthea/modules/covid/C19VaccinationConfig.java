package org.mitre.synthea.modules.covid;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;

import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

import org.mitre.synthea.helpers.Config;
import org.mitre.synthea.helpers.Utilities;
import org.mitre.synthea.world.agents.Person;

/**
 * Country-specific COVID-19 vaccination settings, read from the JSON file named by the property
 * {@value #PROPERTY}. When the property is empty, {@link #get()} returns null and the
 * {@link C19ImmunizationModule} keeps its built-in United States behavior.
 * <p>
 * The file holds the eligibility rules (minimum age from a date), the vaccines in use, the share
 * of each vaccine over time, the share of each age band that ever gets a first shot (percent), the
 * CSV with doses per day and age band (used for when a first shot is given), and whether people
 * who did not decide to get a shot can still become late adopters. An optional last date for
 * starting a vaccination (the end of the data) stops people who become eligible later, for example
 * by turning 12, from starting one.
 * </p>
 */
public class C19VaccinationConfig {
  /** Property naming the JSON file. Empty or unset means the built-in US behavior. */
  public static final String PROPERTY = "generate.covid.vaccination.default_file";

  /** The file last loaded and its path; replaced as a whole so reads need no lock. */
  private static class Loaded {
    final String path;
    final C19VaccinationConfig config;

    Loaded(String path, C19VaccinationConfig config) {
      this.path = path;
      this.config = config;
    }
  }

  private static volatile Loaded loaded;

  /** A minimum age that is eligible from a date. */
  public static class EligibilityRule {
    @SerializedName("min_age")
    public int minAge;
    public String from;

    long fromTime() {
      return toTime(from);
    }
  }

  /**
   * A vaccine. Its name must be a {@link C19Vaccine.EUASet} value.
   */
  public static class VaccineDefinition {
    public String name;
    public String cvx;
    public String display;
    @SerializedName("two_dose")
    public boolean twoDose;
    @SerializedName("days_between_doses")
    public int daysBetweenDoses;
  }

  /** From a date on, vaccines are chosen with these relative weights. */
  public static class MixPeriod {
    public String from;
    public Map<String, Double> share;

    long fromTime() {
      return toTime(from);
    }
  }

  @SerializedName("dose_rates_file")
  public String doseRatesFile;
  public List<EligibilityRule> eligibility = new ArrayList<>();
  @SerializedName("uptake_by_age")
  public Map<String, Double> uptakeByAge;
  @SerializedName("first_shots_until")
  public String firstShotsUntil;
  @SerializedName("late_adoption_start")
  public String lateAdoptionStart;
  public List<VaccineDefinition> vaccines = new ArrayList<>();
  @SerializedName("vaccine_mix")
  public List<MixPeriod> vaccineMix = new ArrayList<>();

  /**
   * The configuration named by the property, or null if the property is empty.
   * @return the configuration or null
   */
  public static C19VaccinationConfig get() {
    String path = Config.get(PROPERTY, "");
    if (path == null || path.trim().isEmpty()) {
      return null;
    }
    path = path.trim();
    Loaded snapshot = loaded;
    if (snapshot != null && snapshot.path.equals(path)) {
      return snapshot.config;
    }
    synchronized (C19VaccinationConfig.class) {
      if (loaded == null || !loaded.path.equals(path)) {
        loaded = new Loaded(path, load(path));
      }
      return loaded.config;
    }
  }

  private static C19VaccinationConfig load(String path) {
    try {
      C19VaccinationConfig config =
          new Gson().fromJson(Utilities.readResource(path, true, true),
              C19VaccinationConfig.class);
      config.validate(path);
      config.eligibility.sort(Comparator.comparingLong(EligibilityRule::fromTime));
      config.vaccineMix.sort(Comparator.comparingLong(MixPeriod::fromTime));
      return config;
    } catch (IOException e) {
      throw new IllegalArgumentException("Unable to read COVID-19 vaccination file " + path, e);
    }
  }

  private void validate(String path) {
    if (doseRatesFile == null || uptakeByAge == null || eligibility.isEmpty()
        || vaccines.isEmpty() || vaccineMix.isEmpty()) {
      throw new IllegalArgumentException("COVID-19 vaccination file " + path
          + " needs dose_rates_file, eligibility, uptake_by_age, vaccines and vaccine_mix");
    }
    for (MixPeriod period : vaccineMix) {
      for (String name : period.share.keySet()) {
        boolean defined = vaccines.stream().anyMatch(v -> v.name.equals(name));
        if (!defined) {
          throw new IllegalArgumentException("Vaccine " + name + " in vaccine_mix of " + path
              + " is not in vaccines");
        }
      }
    }
  }

  static long toTime(String date) {
    return LocalDateTime.of(LocalDate.parse(date), LocalTime.NOON)
        .toInstant(ZoneOffset.UTC).toEpochMilli();
  }

  /**
   * The first time anybody is eligible for a shot.
   * @return time in milliseconds
   */
  public long firstPossibleShotTime() {
    return eligibility.get(0).fromTime();
  }

  /**
   * Start of late adoption, or Long.MAX_VALUE if people who did not decide never get a shot.
   * @return time in milliseconds
   */
  public long lateAdoptionStartTime() {
    return lateAdoptionStart == null ? Long.MAX_VALUE : toTime(lateAdoptionStart);
  }

  /**
   * Whether a person of the age is eligible at the time.
   * @param age age in years
   * @param time time in milliseconds
   * @return true if one of the rules applies
   */
  public boolean eligible(int age, long time) {
    if (firstShotsUntil != null && time > toTime(firstShotsUntil)) {
      return false;
    }
    for (EligibilityRule rule : eligibility) {
      if (age >= rule.minAge && time >= rule.fromTime()) {
        return true;
      }
    }
    return false;
  }

  /**
   * Choose a vaccine for a person at a time, using the weights of the latest period that has
   * started (the first period if none has).
   * @param person the person, who supplies the random number
   * @param time time in milliseconds
   * @return the name of the vaccine, a {@link C19Vaccine.EUASet} value
   */
  public String selectVaccine(Person person, long time) {
    MixPeriod period = vaccineMix.get(0);
    for (MixPeriod candidate : vaccineMix) {
      if (candidate.fromTime() <= time) {
        period = candidate;
      }
    }
    double total = period.share.values().stream().mapToDouble(Double::doubleValue).sum();
    double draw = person.rand() * total;
    String last = null;
    for (Map.Entry<String, Double> entry : period.share.entrySet()) {
      last = entry.getKey();
      draw -= entry.getValue();
      if (draw < 0) {
        return last;
      }
    }
    return last;
  }
}
