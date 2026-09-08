# ankispiel

A tool that refreshes the example material of an Anki vocabulary deck: every night it
regenerates example sentences (with audio) for the notes whose cards come up the next day,
so revisiting a word always means seeing it in a new sentence.

## Language

**Source language**:
The language the user already knows; translations are written in it.
_Avoid_: native language, known language

**Target language**:
The language being learned; example sentences and their audio are in it.
_Avoid_: learning language

**Note**:
One vocabulary entry in the deck: a word pair plus its example slots. Both of a
note's cards share the note's content.
_Avoid_: card (when meaning the note)

**Card**:
One reviewable direction of a note. Each note has two cards: original
(target→source) and reverse (source→target). Scheduling and review progress
belong to the card.
_Avoid_: note (when meaning the card)

**Target word**:
The target-language word as the learner meets it; for nouns this includes the
article and plural form (e.g. `die Bitte, -n`).
_Avoid_: lemma, base form

**Example slot**:
One fixed position on a note holding an example sentence (target language), its
translation (source language), and the sentence's audio. Empty slots render
nothing on the cards.
_Avoid_: sentence field, s1..s10

**Fresh sentence**:
An example sentence written by the nightly run, replacing what previous reviews
showed, so the same sentence is not memorised.

**Upcoming day**:
The set of notes the nightly run refreshes: those with a card due the next day,
plus the next new notes in the deck's new-card order.
_Avoid_: due cards
