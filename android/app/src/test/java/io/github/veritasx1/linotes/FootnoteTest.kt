package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Model
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Footnotes – the same cases as tests/test_footnotes.py. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class FootnoteTest {
    @Test
    fun footnotes() {
        assertEquals("Müller 2020, S. 4", Model.footnoteText("fn:Müller 2020, S. 4"))
        assertEquals("", Model.footnoteText("fn:")); assertNull(Model.footnoteText("n:abc")); assertNull(Model.footnoteText(null))
        val blocks = listOf(JSONObject("""{"t":"title","x":"Quellen"}"""),
            JSONObject("""{"t":"body","x":"Erst1 dann2","s":[[10,11,"fn:Zweite"],[0,4,"b"],[4,5,"fn:Erste"]]}"""),
            JSONObject("""{"t":"body","x":"kein Verweis"}"""),
            JSONObject("""{"t":"body","x":"Ende3","s":[[4,5,"fn:Dritte, mit Komma"]]}"""))
        assertEquals(listOf("Erste", "Zweite", "Dritte, mit Komma"), Model.footnotes(blocks))
        assertEquals(emptyList<String>(), Model.footnotes(listOf(JSONObject("""{"t":"body","x":"x","s":[[0,1]]}"""))))
    }
}
