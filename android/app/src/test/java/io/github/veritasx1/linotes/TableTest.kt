package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Model
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Karte d16a78b7: same cases as linux/tests/test_table.py. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class TableTest {
    @Test
    fun sameAsUbuntu() {
        assertEquals("""{"t":"table","r":[["","",""],["","",""]],"x":" |  | \n |  | "}""", Model.newTable(3, 2).toString())
        assertEquals(listOf(listOf("a", ""), listOf("b", "c")), Model.tableRows(JSONObject("""{"r":[["a"],["b","c"]]}""")))
        assertEquals(listOf(listOf("")), Model.tableRows(JSONObject()))
        assertEquals("Tag | Wer\nMo | Olaf", Model.tableBlock(listOf(listOf("Tag", "Wer"), listOf("Mo", "Olaf"))).getString("x"))
        assertFalse(Model.isEmptyBody(org.json.JSONArray().put(JSONObject().put("t", "title").put("x", "")).put(Model.newTable())))
    }
}
