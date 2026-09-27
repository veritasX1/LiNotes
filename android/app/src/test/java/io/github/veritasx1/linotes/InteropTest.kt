package io.github.veritasx1.linotes

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.data.Api
import io.github.veritasx1.linotes.data.Vault
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.RichEditor
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class InteropTest {

    private val scratch = File("/tmp/claude-1000/-home-olaf-winkler/307e9b08-3ef7-4558-9ee3-51920f668e56/scratchpad")

    @Test
    fun vaultFromLinuxOpensOnAndroid() {
        val sample = JSONObject(File(scratch, "vault_py.json").readText())
        val key = Vault.unlock(sample.getJSONObject("vault"), "mein-geheimnis")
        val body = Vault.openBody(key, sample.getJSONObject("box"))
        assertEquals("Geheim äöü", body.getJSONObject(0).getString("x"))
        // And the other direction: Android creates, Linux checks (see python step).
        val (vault, androidKey) = Vault.create("android-geheim", "")
        val box = Vault.sealBody(androidKey, JSONArray().put(JSONObject().put("t", "title").put("x", "Von Android ß")))
        File(scratch, "vault_android.json").writeText(JSONObject().put("vault", vault).put("box", box).toString())
    }

    @Test
    fun wrongPasswordIsRejected() {
        val sample = JSONObject(File(scratch, "vault_py.json").readText())
        var rejected = false
        try { Vault.unlock(sample.getJSONObject("vault"), "falsch") } catch (error: Vault.WrongPassword) { rejected = true }
        assertTrue(rejected)
    }

    @Test
    fun editorRoundTripAndEnterRules() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val colors = EditorColors(0xFF000000.toInt(), 0x99000000.toInt(), 0x4D000000, 0xFFE6A200.toInt(), 0x73FFD83D)
        val editor = RichEditor(context, colors) { _, done -> done(null) }
        val blocks = listOf(
            JSONObject().put("t", "title").put("x", "Einkauf"),
            JSONObject().put("t", "body").put("x", "fett und kursiv").put("s", JSONArray().put(JSONArray().put(0).put(4).put("b"))),
            JSONObject().put("t", "check").put("x", "Milch").put("c", true),
            JSONObject().put("t", "check").put("x", "Brot").put("c", false),
            JSONObject().put("t", "number").put("x", "eins").put("l", 1),
        )
        editor.load(blocks)
        val out = editor.toBlocks()
        assertEquals(blocks.map { it.toString() }, out.map { it.toString() })

        // Enter at the end of "Brot" continues the checklist.
        val text = editor.text!!
        val end = text.indexOf("Brot") + 4
        editor.setSelection(end)
        text.insert(end, "\n")
        text.insert(end + 1, "Butter")
        val afterEnter = editor.toBlocks()
        assertEquals("check", afterEnter[4].getString("t"))
        assertEquals("Butter", afterEnter[4].getString("x"))
        assertEquals(false, afterEnter[4].getBoolean("c"))

        // Enter on an empty list item ends the list.
        val end2 = editor.text!!.indexOf("Butter") + 6
        editor.text!!.insert(end2, "\n")
        editor.text!!.insert(end2 + 1, "\n")
        val afterEmpty = editor.toBlocks()
        assertEquals("body", afterEmpty[5].getString("t"))

        // Enter after the title gives body text.
        val titleEnd = editor.text!!.indexOf("Einkauf") + 7
        editor.text!!.insert(titleEnd, "\n")
        editor.text!!.insert(titleEnd + 1, "Unter dem Titel")
        assertEquals("body", editor.toBlocks()[1].getString("t"))
    }
}
