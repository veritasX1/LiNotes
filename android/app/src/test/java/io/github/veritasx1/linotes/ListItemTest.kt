package io.github.veritasx1.linotes

import android.view.View
import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.RichEditor
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Karte 0ba372ba: Listenpunkt auf leerer Zeile, Enter rückt den vorigen Punkt nicht ein,
 *  Rücktaste auf leerem Punkt entfernt den Punkt. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class ListItemTest {

    private fun editor(vararg blocks: JSONObject): RichEditor {
        val colors = EditorColors(0xFF000000.toInt(), 0xFF666666.toInt(), 0xFF999999.toInt(), 0xFFE6A200.toInt(), 0x73FFD83D)
        val editor = RichEditor(ApplicationProvider.getApplicationContext(), colors) { _, done -> done(null) }
        editor.layoutParams = android.view.ViewGroup.LayoutParams(1080, android.view.ViewGroup.LayoutParams.WRAP_CONTENT)
        editor.load(blocks.toList())
        layout(editor)
        return editor
    }

    private fun layout(editor: RichEditor) {
        editor.measure(View.MeasureSpec.makeMeasureSpec(1080, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
        editor.layout(0, 0, 1080, editor.measuredHeight)
    }

    private fun type(editor: RichEditor, text: String) {
        val position = editor.selectionEnd
        editor.text!!.insert(position, text)
        layout(editor)
    }

    private fun b(type: String, text: String) = JSONObject().put("t", type).put("x", text)

    private fun types(editor: RichEditor) = editor.toBlocks().map { it.getString("t") + ":" + it.getString("x") }

    @Test
    fun webAddressesBecomeLinksButAreNotSaved() {
        val editor = editor(b("title", "Links"), b("body", "Siehe https://developer.apple.com/design/tips/, und www.linotes.goip.de."))
        val text = editor.text!!
        val links = text.getSpans(0, text.length, io.github.veritasx1.linotes.ui.LinkSpan::class.java)
            .map { text.substring(text.getSpanStart(it), text.getSpanEnd(it)) }.sorted()
        assertEquals(listOf("https://developer.apple.com/design/tips/", "www.linotes.goip.de"), links)
        val saved = editor.toBlocks()[1]
        assertEquals("Siehe https://developer.apple.com/design/tips/, und www.linotes.goip.de.", saved.getString("x"))
        assertEquals(false, saved.has("s"))
    }

    @Test
    fun bulletOnEmptyLineEnterAndBackspace() {
        val editor = editor(b("title", "Einkauf"), b("body", ""))
        editor.setSelection(editor.text!!.length)
        editor.applyParagraph("bullet")
        assertEquals(listOf("title:Einkauf", "bullet:"), types(editor))

        type(editor, "Milch")
        type(editor, "\n")
        assertEquals(listOf("title:Einkauf", "bullet:Milch", "bullet:"), types(editor))
        // Same indentation for both bullets: the empty new one must not shift "Milch".
        val layout = editor.layout
        val milch = layout.getLineForOffset(editor.text!!.indexOf("Milch"))
        val empty = layout.getLineForOffset(editor.selectionEnd)
        assertEquals(layout.getParagraphLeft(milch), layout.getParagraphLeft(empty))

        // Backspace on the empty bullet removes the bullet, the line stays.
        editor.text!!.delete(editor.selectionEnd - 1, editor.selectionEnd)
        layout(editor)
        // (A trailing empty line is not saved; the editor keeps it as normal text.)
        assertEquals("Einkauf\nMilch\n", editor.text.toString())
        assertEquals(listOf("title:Einkauf", "bullet:Milch"), types(editor))
    }
}
