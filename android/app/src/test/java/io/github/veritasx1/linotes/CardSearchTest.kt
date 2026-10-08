package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncObject
import org.json.JSONObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Searching cards in a board – the same cases as tests/test_card_search.py. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CardSearchTest {
    private val card = SyncObject("65a4dd44c0ffee0123456789abcdef01", "card", null, 1, JSONObject("""{
        "title": "Suche in Aufgaben (Lupe)", "notes": "Olaf: Karte xyz123abc987 finden",
        "impact": "Board-Ansicht", "verification": "Screenshots", "version": "2.3.0",
        "commits": [{"h": "e4afa02", "m": "Pläne (Android)"}], "files": [{"n": "Skizze.png"}],
        "evidence": [{"n": "Prüfprotokoll.pdf"}], "assignee": 3}"""), false, 1, 0.0, 1)
    private fun found(query: String) = Model.cardMatches(card, query) { if (it == 3) "Claude" else "?" }

    @Test
    fun search() {
        assertTrue(found("") && found("   "))
        assertTrue(found("65a4dd44") && found("65A4DD") && found("c0ffee"))
        assertTrue(found("lupe") && found("XYZ123ABC987") && found("board-ansicht"))
        assertTrue(found("2.3.0") && found("e4afa02") && found("pläne"))
        assertTrue(found("skizze") && found("prüfprotokoll") && found("claude"))
        assertTrue(found("suche lupe") && !found("suche anna"))
        assertFalse(found("65a4dd45"))
        val bare = SyncObject("x", "card", null, 1, JSONObject(), false, 1, 0.0, 1)
        assertTrue(Model.cardMatches(bare, "x") && !Model.cardMatches(bare, "y"))
    }
}
