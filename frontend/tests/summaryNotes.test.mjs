// Bug 3: the hearing summary showed the same key note twice.
import assert from "node:assert/strict";
import { test } from "node:test";
import { currentKeyNotes, editLocalized } from "../src/lib/summaryNotes.ts";

test("a re-submitted hearing update is one key note, not two", () => {
  const order = "SAMPLE_DATA_NOT_REAL_LAW order: reply in two weeks.";
  const notes = currentKeyNotes({ id: "h-purpose", text: "SAMPLE first hearing" }, [
    { id: "u1", text: order },
    { id: "u2", text: order },
  ]);
  assert.deepEqual(notes.map((note) => note.id), ["h-purpose", "u2"]);
});

test("only the latest update version is current; earlier versions are history", () => {
  const notes = currentKeyNotes(null, [
    { id: "u1", text: "SAMPLE draft order" },
    { id: "u2", text: "SAMPLE corrected order" },
  ]);
  assert.deepEqual(notes, [{ id: "u2", text: "SAMPLE corrected order" }]);
});

test("a purpose equal to the update text (spacing, case, NFC) is shown once; empty notes are dropped", () => {
  const notes = currentKeyNotes({ id: "p", text: "  SAMPLE  Bail hearing " }, [{ id: "u", text: "sample bail hearing" }]);
  assert.equal(notes.length, 1);
  assert.deepEqual(currentKeyNotes({ id: "p", text: "   " }, []), []);
});

test("editing an untranslated claim updates both languages; a translated one keeps the other language", () => {
  assert.deepEqual(editLocalized({ en: "old", bn: "old" }, "en", "new"), { en: "new", bn: "new" });
  assert.deepEqual(editLocalized({ en: "old", bn: "পুরনো" }, "en", "new"), { en: "new", bn: "পুরনো" });
});
