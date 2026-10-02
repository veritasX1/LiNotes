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

    private fun h(type: String, text: String, collapsed: Boolean = false) =
        JSONObject().put("t", type).put("x", text).apply { if (collapsed) put("z", true) }

    @Test
    fun collapsedSectionsKeepTheirContent() {
        // Karte fc905de4: like Ubuntu's test_fold.py.
        val editor = editor(h("title", "Plan"), h("heading", "Woche 1", collapsed = true), body("Montag"),
            h("subheading", "Details"), h("check", "Einkaufen"), h("heading", "Woche 2"), body("Dienstag"))
        // Folded content is not in the text, but saved in full.
        assertEquals(false, editor.text.toString().contains("Montag"))
        assertEquals(listOf("title:Plan", "heading:Woche 1", "body:Montag", "subheading:Details", "check:Einkaufen", "heading:Woche 2", "body:Dienstag"), kinds(editor))
        assertEquals(true, editor.toBlocks()[1].optBoolean("z"))
        // Expand, then fold only the subheading.
        editor.toggleFold(editor.text!!.indexOf("Woche 1"))
        assertEquals(true, editor.text.toString().contains("Montag"))
        assertEquals(false, editor.toBlocks()[1].has("z"))
        editor.toggleFold(editor.text!!.indexOf("Details"))
        assertEquals(false, editor.text.toString().contains("Einkaufen"))
        assertEquals(true, editor.text.toString().contains("Woche 2"))
        assertEquals(listOf("title:Plan", "heading:Woche 1", "body:Montag", "subheading:Details", "check:Einkaufen", "heading:Woche 2", "body:Dienstag"), kinds(editor))
    }

    @Test
    fun textColorFontAndAlignment() {
        // Karte 55ca5a4f: same data as Ubuntu's test_text_style.py.
        val editor = editor(JSONObject().put("t", "title").put("x", "T"),
            body("rot und blau", JSONArray("[0,3,\"c:pink\"]")).put("a", "center"))
        assertEquals("center", editor.toBlocks()[1].optString("a"))
        editor.setSelection(2, 5)
        editor.setTextColorStyle("c:blue")
        editor.setHighlight("h:mint")
        editor.setSelection(2 + 8, 2 + 12)
        editor.setFont("f:serif")
        assertEquals("""[[0,3,"c:blue"],[0,3,"h:mint"],[8,12,"f:serif"]]""",
            spans(editor)[1].replace(" ", "").let { s -> org.json.JSONArray(s).let { a -> (0 until a.length()).map { a.getJSONArray(it).toString() }.sorted().joinToString(",", "[", "]") } })
        // Alignment survives a style change and carries on with Enter.
        editor.setSelection(editor.text!!.length)
        editor.setAlignment("right")
        editor.applyParagraph("heading")
        type(editor, "\n")
        type(editor, "weiter")
        val blocks = editor.toBlocks()
        assertEquals("right", blocks[1].optString("a"))
        assertEquals("heading", blocks[1].optString("t"))
        assertEquals("right", blocks[2].optString("a"))
        editor.setAlignment(null)
        assertEquals(false, editor.toBlocks()[2].has("a"))
    }

    @Test
    fun equalsSignFillsInTheResult() {
        // Karte de1319cf: like Ubuntu's test_calc.py test_editor.
        val editor = editor(JSONObject().put("t", "title").put("x", "Kosten"), body("Miete = 450"), body("Miete * 12 "))
        editor.setSelection(editor.text!!.length)
        type(editor, "=")
        org.robolectric.shadows.ShadowLooper.idleMainLooper()
        assertEquals("Miete * 12 = 5400", editor.toBlocks()[2].optString("x"))
    }

    @Test
    fun attachedFilesLoadSaveAndStayApart() {
        // Karte 1ed7564d: like Ubuntu's test_attachments.py.
        val file = JSONObject().put("t", "file").put("f", "local:abc").put("n", "Bericht.pdf").put("m", "application/pdf").put("b", 1258291)
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), JSONObject(file.toString()), body("danach"))
        assertEquals(file.toString(), editor.toBlocks()[1].toString())
        assertEquals("PDF-Dokument · 1,2 MB", io.github.veritasx1.linotes.ui.fileDetails(file))
        val other = editor(JSONObject().put("t", "title").put("x", "T"), body("eins"))
        other.setSelection(other.text!!.length)
        other.insertFile(JSONObject(file.toString()).put("n", "Liste.xlsx").put("m", "application/vnd.ms-excel").put("b", 2048))
        type(other, "zwei")
        assertEquals(listOf("title:T", "body:eins", "file:", "body:zwei"), kinds(other))
        // Backspace at the start of "zwei" does not merge it into the file line.
        val zwei = other.text!!.indexOf("zwei")
        other.text!!.delete(zwei - 1, zwei)
        assertEquals(listOf("title:T", "body:eins", "file:", "body:zwei"), kinds(other))
    }

    @Test
    fun mentionsInSharedNotes() {
        // Karte 91fbc637: like Ubuntu's test_mentions.py.
        val editor = editor(JSONObject().put("t", "title").put("x", "T"), body("Frage an @Ol", JSONArray("[9,12,\"m:1\"]")))
        // load() already ran in editor(); reload with the name lookup.
        editor.userName = { if (it == 1) "Olaf" else null }
        editor.mentionPeople = { listOf(1 to "Olaf") }
        editor.load(editor.toBlocks())
        assertEquals("Frage an @Olaf", editor.toBlocks()[1].optString("x"))
        editor.setSelection(editor.text!!.length)
        type(editor, " a")
        type(editor, "@")
        org.robolectric.shadows.ShadowLooper.idleMainLooper()
        assertEquals(null, editor.pendingLinkQuery())   // e-mail address: nothing
        type(editor, "b.de ")
        type(editor, "@")
        type(editor, "Ol")
        assertEquals("Ol", editor.pendingLinkQuery())
        editor.finishLink("1", "Olaf")
        val line = editor.toBlocks()[1]
        assertEquals("Frage an @Olaf a@b.de @Olaf ", line.optString("x"))
        assertEquals("""[[9,14,"m:1"],[22,27,"m:1"]]""", line.getJSONArray("s").toString())
        assertEquals(2, io.github.veritasx1.linotes.data.Model.mentionsOf(org.json.JSONArray(editor.toBlocks()), 1))
    }
}
