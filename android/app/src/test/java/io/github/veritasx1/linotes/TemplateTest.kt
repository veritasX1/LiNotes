package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Model
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.time.LocalDateTime

/** Templates – the same cases as tests/test_templates.py. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class TemplateTest {
    private val now = LocalDateTime.of(2026, 10, 4, 9, 5)   // a Sunday

    @Test
    fun templates() {
        val filled = Model.fillTemplate(listOf(JSONObject("""{"t":"title","x":"Besprechung {{Datum}}"}"""),
            JSONObject("""{"t":"body","x":"{{Wochentag}} um {{Uhrzeit}} – wichtig","s":[[31,38,"b"]]}"""),
            JSONObject("""{"t":"body","x":"{{Unbekannt}} bleibt"}""")), now)
        assertEquals("Besprechung 04.10.2026", filled[0].getString("x"))
        assertEquals("Sonntag um 09:05 – wichtig", filled[1].getString("x"))
        assertEquals("[[19,26,\"b\"]]", filled[1].getJSONArray("s").toString())
        assertEquals("wichtig", filled[1].getString("x").substring(19, 26))
        assertEquals("{{Unbekannt}} bleibt", filled[2].getString("x"))
        assertEquals(listOf("besprechung", "protokoll", "reise", "tagebuch"), Model.BUILTIN_TEMPLATES.map { it.first })
        val diary = Model.fillTemplate(Model.BUILTIN_TEMPLATES.first { it.first == "tagebuch" }.third, now)
        assertEquals("Sonntag, 04.10.2026", diary[0].getString("x"))
        assertEquals("Besprechung {{Datum}}", Model.BUILTIN_TEMPLATES[0].third[0].getString("x"))
    }
}
