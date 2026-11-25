package org.mitre.synthea.world.concepts;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import org.mitre.synthea.helpers.Config;
import org.mitre.synthea.helpers.SimpleYML;
import org.mitre.synthea.helpers.Utilities;
import org.mitre.synthea.world.agents.Person;

/**
 * Provides utilities for generating and managing names.
 */
public class Names {

  private static SimpleYML names = loadNames();

  private static SimpleYML loadNames() {
    String filename = "names.yml";
    try {
      String namesData = Utilities.readResource(filename);
      return new SimpleYML(namesData);
    } catch (Exception e) {
      System.err.println("ERROR: unable to load yml: " + filename);
      e.printStackTrace();
      throw new ExceptionInInitializerError(e);
    }
  }

  /** Languages that have their own block in names.yml. Any other language uses english. */
  private static final Set<String> NAME_LANGUAGES =
      Set.of("english", "spanish", "greek", "albanian");

  private static String nameBlock(String language) {
    String lang = language == null ? "" : language.toLowerCase(Locale.ROOT);
    return NAME_LANGUAGES.contains(lang) ? lang : "english";
  }

  /**
   * Indicates whether numbers should be appended to generated names.
   * These numbers are used to indicate the patients as not real people.
   */
  public static final boolean appendNumbersToNames =
      Config.getAsBoolean("generate.append_numbers_to_person_names", false);

  /**
   * Generate a first name appropriate for a given gender and language.
   * If `generate.append_numbers_to_person_names` == true,
   * then numbers will be appended automatically.
   * @param gender Gender of the name, "M" or "F"
   * @param language Origin language of the name, "english", "spanish", "greek", "albanian".
   *     Any other language uses the english names.
   * @param person person to generate a name for.
   * @return First name.
   */
  @SuppressWarnings("unchecked")
  public static String fakeFirstName(String gender, String language, Person person) {
    List<String> choices = (List<String>) names.get(nameBlock(language) + "." + gender);

    // pick a random item from the list
    String name = choices.get(person.randInt(choices.size()));

    if (appendNumbersToNames) {
      name = addHash(name);
    }

    return name;
  }

  /**
   * Generate a surname appropriate for a given language.
   * If `generate.append_numbers_to_person_names` == true,
   * then numbers will be appended automatically.
   * For greek this is the male form of the surname; use
   * {@link #surnameForGender(String, String, String)} for a female form.
   * @param language Origin language of the name, "english", "spanish", "greek", "albanian".
   *     Any other language uses the english names.
   * @param person person to generate a name for.
   * @return Surname or Family Name.
   */
  @SuppressWarnings("unchecked")
  public static String fakeLastName(String language, Person person) {
    List<String> choices = (List<String>) names.get(nameBlock(language) + ".family");
    // pick a random item from the list
    String name = choices.get(person.randInt(choices.size()));

    if (appendNumbersToNames) {
      name = addHash(name);
    }

    return name;
  }

  /**
   * Generate a surname appropriate for a given gender and language. Same random draw as
   * {@link #fakeLastName(String, Person)}, so the sequence of random numbers does not depend on
   * the gender.
   * @param gender Gender of the person, "M" or "F"
   * @param language Origin language of the name
   * @param person person to generate a name for.
   * @return Surname in the form that matches the gender.
   */
  public static String fakeLastName(String gender, String language, Person person) {
    return surnameForGender(fakeLastName(language, person), gender, language);
  }

  /**
   * Convert a surname to the form used for a gender. Only Greek surnames change: a male surname
   * is turned into its female (genitive) form, for example Παπαδόπουλος into Παπαδοπούλου.
   * A name that already ends in -ου (Νικολάου), and any other ending not covered, is unchanged.
   * Trailing digits (see `generate.append_numbers_to_person_names`) are kept.
   * @param surname The surname in its male (base) form.
   * @param gender "M" or "F"
   * @param language Origin language of the name
   * @return The surname for the gender.
   */
  public static String surnameForGender(String surname, String gender, String language) {
    if (!"F".equals(gender) || !"greek".equalsIgnoreCase(language)) {
      return surname;
    }
    int end = surname.length();
    while (end > 0 && Character.isDigit(surname.charAt(end - 1))) {
      end--;
    }
    return greekFemaleSurname(surname.substring(0, end)) + surname.substring(end);
  }

  private static final String GREEK_VOWELS = "αεηιουω";
  private static final List<String> GREEK_DIPHTHONGS =
      List.of("αι", "ει", "οι", "υι", "αυ", "ευ", "ηυ", "ου");
  private static final char ACUTE = (char) 0x0301; // combining acute accent
  private static final char DIAERESIS = (char) 0x0308; // combining diaeresis

  /**
   * Female form of a Greek male surname:
   * -ος becomes -ου (the stress moves from the third-last to the second-last syllable, so
   * Αλεξόπουλος becomes Αλεξοπούλου), -ός becomes -ού, -ης -η, -ής -ή, -ας -α, -άς -ά.
   */
  private static String greekFemaleSurname(String male) {
    String w = Normalizer.normalize(male, Normalizer.Form.NFC);
    if (w.endsWith("ου")) {
      return w;
    } else if (w.endsWith("ός")) {
      return w.substring(0, w.length() - 2) + "ού";
    } else if (w.endsWith("ος")) {
      String stem = moveStressForGenitive(w);
      return stem.substring(0, stem.length() - 2) + "ου";
    } else if (w.endsWith("ής")) {
      return w.substring(0, w.length() - 2) + "ή";
    } else if (w.endsWith("ης")) {
      return w.substring(0, w.length() - 2) + "η";
    } else if (w.endsWith("άς")) {
      return w.substring(0, w.length() - 2) + "ά";
    } else if (w.endsWith("ας")) {
      return w.substring(0, w.length() - 2) + "α";
    }
    return w;
  }

  /**
   * If the stress of a word is on the third-last syllable, move it to the second-last syllable.
   * Syllables are counted by vowel groups: a diphthong is one syllable unless its first vowel
   * is accented or either vowel has a diaeresis.
   */
  private static String moveStressForGenitive(String word) {
    String d = Normalizer.normalize(word, Normalizer.Form.NFD);
    StringBuilder letters = new StringBuilder();
    ArrayList<Boolean> acute = new ArrayList<>();
    ArrayList<Boolean> diaeresis = new ArrayList<>();
    for (char c : d.toCharArray()) {
      if (c == ACUTE) {
        acute.set(acute.size() - 1, true);
      } else if (c == DIAERESIS) {
        diaeresis.set(diaeresis.size() - 1, true);
      } else {
        letters.append(c);
        acute.add(false);
        diaeresis.add(false);
      }
    }
    // each syllable is the index of its last vowel; stressedSyllable is -1 if none
    ArrayList<Integer> syllables = new ArrayList<>();
    int stressed = -1;
    int n = letters.length();
    for (int i = 0; i < n; i++) {
      String lower = letters.substring(i, i + 1).toLowerCase(Locale.ROOT);
      if (!GREEK_VOWELS.contains(lower)) {
        continue;
      }
      int last = i;
      if (i + 1 < n && !acute.get(i) && !diaeresis.get(i) && !diaeresis.get(i + 1)
          && GREEK_DIPHTHONGS.contains(
              (lower + letters.substring(i + 1, i + 2)).toLowerCase(Locale.ROOT))) {
        last = i + 1;
      }
      if (acute.get(i) || acute.get(last)) {
        stressed = syllables.size();
      }
      syllables.add(last);
      i = last;
    }
    if (stressed < 0 || stressed != syllables.size() - 3) {
      return word;
    }
    for (int i = 0; i < n; i++) {
      acute.set(i, false);
    }
    acute.set(syllables.get(syllables.size() - 2), true);
    StringBuilder out = new StringBuilder();
    for (int i = 0; i < n; i++) {
      out.append(letters.charAt(i));
      if (acute.get(i)) {
        out.append(ACUTE);
      }
      if (diaeresis.get(i)) {
        out.append(DIAERESIS);
      }
    }
    return Normalizer.normalize(out.toString(), Normalizer.Form.NFC);
  }

  /**
   * Generate a Street Address.
   * @param includeLine2 Whether or not the address should have a second line,
   *     which can take the form of an apartment, unit, or suite number.
   * @param person person to generate an address for.
   * @return First name.
   */
  @SuppressWarnings("unchecked")
  public static String fakeAddress(boolean includeLine2, Person person) {
    int number = person.randInt(1000) + 100;
    List<String> n = (List<String>)names.get("english.family");
    // for now just use family names as the street name.
    // could expand with a few more but probably not worth it
    String streetName = n.get(person.randInt(n.size()));
    List<String> a = (List<String>)names.get("street.type");
    String streetType = a.get(person.randInt(a.size()));

    if (includeLine2) {
      int addtlNum = person.randInt(100);
      List<String> s = (List<String>)names.get("street.secondary");
      String addtlType = s.get(person.randInt(s.size()));
      return number + " " + streetName + " " + streetType + " " + addtlType + " " + addtlNum;
    } else {
      return number + " " + streetName + " " + streetType;
    }
  }

  /**
   * Adds a 1- to 3-digit hashcode to the end of the name.
   * @param name Person's name
   * @return The name with a hash appended, ex "John123" or "Smith22"
   */
  public static String addHash(String name) {
    // note that this value should be deterministic
    // It cannot be a random number. It needs to be a hash value or something deterministic.
    // We do not want John10 and John52 -- we want all the Johns to have the SAME numbers. e.g. All
    // people named John become John52
    // Why? Because we do not know how using systems will index names. Say a user of an system
    // loaded with Synthea data wants to find all the people named John Smith. This will be easier
    // if John Smith always resolves to John52 Smith32 and not [John52 Smith32, John10 Smith22, ...]
    return name + Integer.toString(Math.abs(name.hashCode() % 1000));
  }
}