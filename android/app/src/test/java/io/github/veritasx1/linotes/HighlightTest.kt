package io.github.veritasx1.linotes

import android.view.View
import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.RichEditor
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Karte 323ae9ca: Markieren in Farben (Olafs Finding: nach Enter nicht markiert weiterschreiben);
 *  Karte 6a3b4e37: Trennlinie. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class HighlightTest {

    private fun editor(vararg blocks: JSONObject): RichEditor {
        val colors = EditorColors(0xFF000000.toInt(), 0xFF666666.toInt(), 0xFF999999.toInt(), 0xFFE6A200.toInt(), 0x73FFD83D)
        val editor = RichEditor(ApplicationProvider.getApplicationContext(), colors) { _, done -> done(null) }
        editor.layoutParams = android.view.ViewGroup.LayoutParams(1080, android.view.ViewGroup.LayoutParams.WRAP_CONTENT)
        editor.load(blocks.toList())
        editor.measure(View.MeasureSpec.makeMeasureSpec(1080, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
        editor.layout(0, 0, 1080, editor.measuredHeight)
        return editor
    }

    private fun type(editor: RichEditor, text: String) {
        val position = editor.selectionEnd
        editor.text!!.insert(position, text)
    }

    private fun spans(editor: RichEditor) = editor.toBlocks().map { it.optJSONArray("s")?.toString() ?: "-" }

    private fun body(text: String, vararg spans: JSONArray) =
        JSONObject().put("t", "body").put("x", text).apply { if (spans.isNotEmpty()) put("s", JSONArray(spans.toList())) }

    @Test
    fun colorsReplaceEachOther() {
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), body("eins zwei"))
        editor.setSelection(2, 6)
        editor.setHighlight("h:pink")
        editor.setSelection(2, 6)
        editor.setHighlight("h:blue")
        assertEquals("""[[0,4,"h:blue"]]""", spans(editor)[1].replace(" ", ""))
        editor.setSelection(2, 6)
        editor.setHighlight(null)
        assertEquals("-", spans(editor)[1])
    }

    @Test
    fun enterEndsTheHighlight() {
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), body("eins zwei", JSONArray("[5,9,\"h:pink\"]")))
        editor.setSelection(editor.text!!.length)
        type(editor, "\n")
        type(editor, "drei")
        assertEquals(listOf("-", """[[5,9,"h:pink"]]""", "-"), spans(editor))
    }

    @Test
    fun enterInsideKeepsTheRestMarked() {
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), body("eins zwei", JSONArray("[0,9,\"h:mint\"]")))
        editor.setSelection(2 + 4)
        type(editor, "\n")
        assertEquals(listOf("-", """[[0,4,"h:mint"]]""", """[[0,5,"h:mint"]]"""), spans(editor))
    }

    private fun kinds(editor: RichEditor) = editor.toBlocks().map { it.getString("t") + ":" + it.optString("x") }

    @Test
    fun dividerLoadsSavesAndComesFromDashes() {
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), body("oben"), JSONObject().put("t", "divider"), body("unten"))
        assertEquals(listOf("title:T", "body:oben", "divider:", "body:unten"), kinds(editor))
        editor.setSelection(editor.text!!.length)
        type(editor, "\n")
        type(editor, "---")
        type(editor, "\n")
        type(editor, "weiter")
        assertEquals(listOf("title:T", "body:oben", "divider:", "body:unten", "divider:", "body:weiter"), kinds(editor))
    }

    @Test
    fun dividerFromTheMenuInTheMiddleOfALine() {
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), body("eins"))
        editor.setSelection(editor.text!!.length)
        editor.insertDivider()
        type(editor, "zwei")
        assertEquals(listOf("title:T", "body:eins", "divider:", "body:zwei"), kinds(editor))
        // Backspace at the start of "zwei" removes the divider, the text stays.
        val zwei = editor.text!!.indexOf("zwei")
        editor.text!!.delete(zwei - 1, zwei)
        assertEquals(listOf("title:T", "body:eins", "body:zwei"), kinds(editor))
    }
}
