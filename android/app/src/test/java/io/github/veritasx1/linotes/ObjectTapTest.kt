package io.github.veritasx1.linotes

import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.RichEditor
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Card 900036dc: tapping a picture or a recording opens/plays it – also when pressed longer – and the
 *  cursor stays where it was; the player card's controls (play/pause, ±15 s, seek) are hit where drawn. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class ObjectTapTest {
    private val blocks = listOf(
        JSONObject("""{"t":"title","x":"Urlaub"}"""),
        JSONObject("""{"t":"body","x":"Text davor"}"""),
        JSONObject("""{"t":"image","f":"srv1:bild"}"""),
        JSONObject("""{"t":"body","x":"Text dazwischen"}"""),
        JSONObject("""{"t":"file","f":"srv1:ton","n":"Aufnahme.m4a","m":"audio/mp4","b":12000,"d":4.0}"""),
        JSONObject("""{"t":"body","x":"Text danach"}"""))

    private fun editor(): RichEditor {
        val editor = RichEditor(ApplicationProvider.getApplicationContext(), EditorColors(0xFF000000.toInt(), 0xFF666666.toInt(), 0xFF999999.toInt(), 0xFFE6A200.toInt(), 0xFFFFE680.toInt())) { _, done -> done(null) }
        editor.layoutParams = android.view.ViewGroup.LayoutParams(1179, android.view.ViewGroup.LayoutParams.WRAP_CONTENT)
        editor.load(blocks)
        editor.measure(View.MeasureSpec.makeMeasureSpec(1179, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
        editor.layout(0, 0, 1179, editor.measuredHeight)
        return editor
    }

    private fun tap(editor: RichEditor, offset: Int, hold: Long = 50, dx: Float = 40f) {
        val layout = editor.layout!!
        val line = layout.getLineForOffset(offset)
        val x = layout.getPrimaryHorizontal(offset) + editor.totalPaddingLeft + dx
        val y = (layout.getLineTop(line) + layout.getLineBottom(line)) / 2f + editor.totalPaddingTop
        val down = SystemClock.uptimeMillis()
        editor.dispatchTouchEvent(MotionEvent.obtain(down, down, MotionEvent.ACTION_DOWN, x, y, 0))
        SystemClock.sleep(hold)
        editor.dispatchTouchEvent(MotionEvent.obtain(down, down + hold, MotionEvent.ACTION_UP, x, y, 0))
    }

    @Test
    fun labels() {
        // Same cases as linux/tests/test_object_tap.py.
        assertEquals("Aufnahme" to "4. Okt. 2026, 14:22 · 0:07", io.github.veritasx1.linotes.ui.AudioNotes.label(JSONObject("""{"n":"Aufnahme 2026-10-04 14-22.ogg","d":7.4}""")))
        assertEquals("Interview" to "1:05", io.github.veritasx1.linotes.ui.AudioNotes.label(JSONObject("""{"n":"Interview.m4a","d":65}""")))
        assertEquals("Aufnahme 2026-13-04 14-22" to "", io.github.veritasx1.linotes.ui.AudioNotes.label(JSONObject("""{"n":"Aufnahme 2026-13-04 14-22.ogg"}""")))
        assertEquals("Audioaufnahme" to "", io.github.veritasx1.linotes.ui.AudioNotes.label(JSONObject("{}")))
    }

    @Test
    fun tapsOpenAndPlay() {
        for (hold in listOf(50L, 700L)) {  // a tap and a longer press ("andrücken")
            val editor = editor()
            val opened = mutableListOf<String>()
            val audio = mutableListOf<String>()
            editor.onOpenImage = { opened.add(it) }
            editor.onAudio = { block, action, _ -> audio.add(block.optString("f") + ":" + action) }
            editor.setSelection(3)
            val image = editor.text!!.indexOf('\uFFFC')
            tap(editor, image, hold)
            assertEquals("Bild ($hold ms)", listOf("srv1:bild"), opened)
            assertEquals("Cursor nach Bild ($hold ms)", 3, editor.selectionStart)
            val recording = editor.text!!.indexOf('\uFFFC', image + 1)
            tap(editor, recording, hold)
            assertEquals("Ton ($hold ms)", listOf("srv1:ton:toggle"), audio)
            assertEquals("Cursor nach Ton ($hold ms)", 3, editor.selectionStart)
        }
    }

    @Test
    fun playerControls() {
        val editor = editor()
        val actions = mutableListOf<String>()
        editor.onAudio = { _, action, fraction -> actions.add(if (action == "seek") "seek:" + "%.1f".format(java.util.Locale.ROOT, fraction) else action) }
        editor.showAudio("srv1:ton", RichEditor.AudioView(true, 5000, 18000))
        editor.measure(View.MeasureSpec.makeMeasureSpec(1179, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
        editor.layout(0, 0, 1179, editor.measuredHeight)
        val text = editor.text!!
        val start = text.indexOf('\uFFFC', text.indexOf('\uFFFC') + 1)
        val layout = editor.layout!!
        val line = layout.getLineForOffset(start)
        val density = editor.resources.displayMetrics.density
        val card = editor.text!!.getSpans(start, start + 1, android.text.style.ImageSpan::class.java).first().drawable.bounds
        val left = layout.getPrimaryHorizontal(start) + editor.totalPaddingLeft
        val top = layout.getLineBottom(line) - card.height() + editor.totalPaddingTop
        fun press(x: Float, y: Float) {
            val down = SystemClock.uptimeMillis()
            editor.dispatchTouchEvent(MotionEvent.obtain(down, down, MotionEvent.ACTION_DOWN, left + x, top + y, 0))
            editor.dispatchTouchEvent(MotionEvent.obtain(down, down + 60, MotionEvent.ACTION_UP, left + x, top + y, 0))
        }
        press(34 * density, 38 * density)                       // the round button
        press(card.width() - 92 * density, 38 * density)        // −15
        press(card.width() - 42 * density, 38 * density)        // +15
        press(16 * density + (card.width() - 32 * density) * 0.5f, 86 * density)  // middle of the bar
        assertEquals(listOf("toggle", "back", "forward", "seek:0.5"), actions)
        assertTrue(card.height() > 100 * density)  // the open card is taller (bar and times)
        editor.showAudio("srv1:ton", null)
        assertTrue(editor.text!!.getSpans(start, start + 1, android.text.style.ImageSpan::class.java).first().drawable.bounds.height() < 80 * density)
        assertEquals(blocks.map { it.toString() }, editor.toBlocks().map { it.toString() })
    }
}
