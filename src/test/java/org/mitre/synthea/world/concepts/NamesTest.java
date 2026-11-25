package org.mitre.synthea.world.concepts;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;
import org.mitre.synthea.world.agents.Person;

public class NamesTest {

  private static final String GREEK = "^[\\u0370-\\u03FF\\u1F00-\\u1FFF]+$";
  private static final String LATIN = "^[A-Za-z\\u00C7\\u00E7\\u00CB\\u00EB]+$";

  /** Greek male surname, female surname. Pairs marked (W) are listed by Wiktionary. */
  private static final String[][] SURNAMES = {
      {"Παπαδόπουλος", "Παπαδοπούλου"}, // (W)
      {"Αλεξόπουλος", "Αλεξοπούλου"}, // (W)
      {"Παρασκευόπουλος", "Παρασκευοπούλου"}, // (W)
      {"Αθανασάκης", "Αθανασάκη"}, // (W)
      {"Ελευθερουδάκης", "Ελευθερουδάκη"}, // (W)
      {"Πανταζής", "Πανταζή"}, // (W)
      {"Φακίρης", "Φακίρη"}, // (W)
      {"Άγγελος", "Αγγέλου"}, // (W) stress moves, first letter loses its accent
      {"Νικολάου", "Νικολάου"}, // (W) already in the genitive
      {"Παπανδρέου", "Παπανδρέου"}, // (W)
      {"Μικρούτσικος", "Μικρουτσίκου"}, // stress on the third-last syllable moves
      {"Ευτύχιος", "Ευτυχίου"},
      {"Σκαρλάτος", "Σκαρλάτου"}, // stress already on the second-last syllable
      {"Μπάρος", "Μπάρου"},
      {"Σπανός", "Σπανού"}, // stress on the last syllable stays
      {"Τσάκωνας", "Τσάκωνα"},
      {"Κριεζής", "Κριεζή"},
      {"Φιξ", "Φιξ"}, // unknown ending is unchanged
  };

  private static void assertMatches(String name, String regex) {
    // the default config appends digits to names; they are not part of the script check
    assertTrue(name, name.replaceAll("[0-9]+$", "").matches(regex));
  }

  @Test
  public void greekFemaleSurnames() {
    for (String[] pair : SURNAMES) {
      assertEquals(pair[0], pair[1], Names.surnameForGender(pair[0], "F", "greek"));
      assertEquals(pair[0], Names.surnameForGender(pair[0], "M", "greek"));
    }
  }

  @Test
  public void trailingDigitsAreKept() {
    assertEquals("Παπαδοπούλου512", Names.surnameForGender("Παπαδόπουλος512", "F", "greek"));
  }

  @Test
  public void otherLanguagesAreNotInflected() {
    assertEquals("Παπαδόπουλος", Names.surnameForGender("Παπαδόπουλος", "F", "english"));
    assertEquals("Hoxha", Names.surnameForGender("Hoxha", "F", "albanian"));
  }

  @Test
  public void greekNamesAreGreekScript() {
    for (int seed = 0; seed < 200; seed++) {
      Person person = new Person(seed);
      assertMatches(Names.fakeFirstName("M", "greek", person), GREEK);
      assertMatches(Names.fakeFirstName("F", "greek", person), GREEK);
      assertMatches(Names.fakeLastName("M", "greek", person), GREEK);
      assertMatches(Names.fakeLastName("F", "greek", person), GREEK);
    }
  }

  @Test
  public void albanianNamesAreLatinScript() {
    for (int seed = 0; seed < 200; seed++) {
      Person person = new Person(seed);
      assertMatches(Names.fakeFirstName("M", "albanian", person), LATIN);
      assertMatches(Names.fakeFirstName("F", "albanian", person), LATIN);
      assertMatches(Names.fakeLastName("M", "albanian", person), LATIN);
    }
  }

  @Test
  public void femaleSurnameIsTheInflectedMaleSurname() {
    for (int seed = 0; seed < 50; seed++) {
      String male = Names.fakeLastName("M", "greek", new Person(seed));
      String female = Names.fakeLastName("F", "greek", new Person(seed));
      assertEquals(Names.surnameForGender(male, "F", "greek"), female);
    }
  }

  @Test
  public void sameSeedGivesSameNames() {
    for (String language : new String[] {"greek", "albanian", "english", "spanish"}) {
      Person a = new Person(7);
      Person b = new Person(7);
      assertEquals(Names.fakeFirstName("F", language, a), Names.fakeFirstName("F", language, b));
      assertEquals(Names.fakeLastName("F", language, a), Names.fakeLastName("F", language, b));
    }
  }

  @Test
  public void greekNamesDifferFromEnglish() {
    assertNotEquals(Names.fakeFirstName("M", "greek", new Person(3)),
        Names.fakeFirstName("M", "english", new Person(3)));
  }

  @Test
  public void usNamesAreUnchanged() {
    // a language without its own block, and the gender-less call, still use the english names
    for (int seed = 0; seed < 50; seed++) {
      assertEquals(Names.fakeFirstName("M", "english", new Person(seed)),
          Names.fakeFirstName("M", "french", new Person(seed)));
      assertEquals(Names.fakeLastName("english", new Person(seed)),
          Names.fakeLastName("F", "english", new Person(seed)));
      assertEquals(Names.fakeLastName("english", new Person(seed)),
          Names.fakeLastName("M", "french", new Person(seed)));
      assertEquals(Names.fakeLastName("spanish", new Person(seed)),
          Names.fakeLastName("F", "spanish", new Person(seed)));
    }
  }
}
