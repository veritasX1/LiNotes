package io.github.veritasx1.linotes

import android.view.View
import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.RichEditor
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Überschriften bekommen Luft nach oben, normaler Text nicht. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class HeadingSpacingTest {

    private fun secondLineHeight(type: String): Int {
        val colors = EditorColors(0xFF000000.toInt(), 0xFF666666.toInt(), 0xFF999999.toInt(), 0xFFE6A200.toInt(), 0x73FFD83D)
        val editor = RichEditor(ApplicationProvider.getApplicationContext(), colors) { _, done -> done(null) }
        editor.load(listOf(JSONObject().put("t", "title").put("x", "Titel"), JSONObject().put("t", type).put("x", "Zweiter Absatz")))
        val spec = View.MeasureSpec.makeMeasureSpec(1080, View.MeasureSpec.EXACTLY)
        editor.measure(spec, View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
        editor.layout(0, 0, 1080, editor.measuredHeight)
        val layout = editor.layout!!
        return layout.getLineBottom(1) - layout.getLineTop(1)
    }

    @Test
    fun headingHasSpaceAbove() {
        val heading = secondLineHeight("heading")
        val body = secondLineHeight("body")
        println("heading=$heading body=$body")
        // 1,35-fache Schrift plus 16 dp Luft (Robolectric: 1 dp = 1 px)
        assertTrue("Überschrift $heading, Text $body", heading >= body * 1.35 + 12)
    }
}
