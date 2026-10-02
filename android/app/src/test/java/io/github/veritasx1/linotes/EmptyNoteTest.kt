package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Model
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Karte 56732238: same cases as linux/tests/test_empty_note.py. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class EmptyNoteTest {
    private fun check(json: String, expected: Boolean) = assertEquals(json, expected, Model.isEmptyBody(JSONArray(json)))

    @Test
    fun sameAsUbuntu() {
        check("""[{"t":"title","x":""}]""", true)
        check("""[{"t":"title","x":"  "},{"t":"body","x":"\t"}]""", true)
        check("""[{"t":"check","x":""},{"t":"bullet","x":""}]""", true)
        check("""[{"t":"title","x":"Einkauf"}]""", false)
        check("""[{"t":"title","x":""},{"t":"body","x":"x"}]""", false)
        check("""[{"t":"title","x":""},{"t":"image","f":"a:b"}]""", false)
        check("""[{"t":"title","x":""},{"t":"file","f":"a:b","n":"x.pdf"}]""", false)
        check("""[{"t":"title","x":""},{"t":"divider"}]""", false)
    }
}
