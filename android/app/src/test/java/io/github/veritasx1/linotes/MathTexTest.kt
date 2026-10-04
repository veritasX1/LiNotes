package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.MathTex
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.MathEditorContent
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.unit.dp
import io.github.veritasx1.linotes.ui.RichEditor
import io.github.veritasx1.linotes.ui.Route
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import kotlin.math.abs

/** Formulas (card 25ae467f): MathTex sets every case in linux/tests/data/math-cases.json exactly like
 *  Ubuntu's mathtex.py (made-up measure: each character half the font size wide); the block survives
 *  the editor; pictures with -Pshots=<folder>. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class MathTexTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    private fun near(expected: Double, actual: Double, what: String) =
        assertTrue("$what: erwartet $expected, bekommen $actual", abs(expected - actual) < 0.02)

    @Test
    fun sameAsUbuntu() {
        val file = listOf("../../linux/tests/data/math-cases.json", "../linux/tests/data/math-cases.json").map(::File).first { it.exists() }
        val cases = JSONArray(file.readText())
        assertTrue(cases.length() >= 15)
        val measure = { text: String, size: Double, _: String -> 0.5 * size * text.codePointCount(0, text.length) }
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val source = case.getString("source")
            val expected = case.getJSONArray("result")
            val formula = MathTex.layout(source, 20.0, measure)
            near(expected.getDouble(0), formula.width, "$source Breite")
            near(expected.getDouble(1), formula.ascent, "$source Oberlänge")
            near(expected.getDouble(2), formula.descent, "$source Unterlänge")
            val ops = expected.getJSONArray(3)
            assertEquals("$source Anzahl Schritte", ops.length(), formula.ops.size)
            for (i in 0 until ops.length()) {
                val want = ops.getJSONArray(i)
                val what = "$source Schritt $i"
                when (val op = formula.ops[i]) {
                    is MathTex.Text -> {
                        assertEquals(what, "text", want.getString(0))
                        near(want.getDouble(1), op.x, what); near(want.getDouble(2), op.y, what)
                        assertEquals(what, want.getString(3), op.text)
                        near(want.getDouble(4), op.size, what)
                        assertEquals(what, want.getString(5), op.style)
                    }
                    is MathTex.Rule -> {
                        assertEquals(what, "rule", want.getString(0))
                        near(want.getDouble(1), op.x, what); near(want.getDouble(2), op.y, what)
                        near(want.getDouble(3), op.w, what); near(want.getDouble(4), op.h, what)
                    }
                    is MathTex.Path -> {
                        assertEquals(what, "path", want.getString(0))
                        val points = want.getJSONArray(1)
                        assertEquals(what, points.length(), op.points.size)
                        op.points.forEachIndexed { p, (x, y) ->
                            near(points.getJSONArray(p).getDouble(0), x, what); near(points.getJSONArray(p).getDouble(1), y, what)
                        }
                        near(want.getDouble(2), op.thick, what)
                    }
                }
            }
        }
    }

    private val blocks = listOf(
        JSONObject("""{"t":"title","x":"Mathe-Hausaufgabe"}"""),
        JSONObject("""{"t":"body","x":"Die Lösungsformel:"}"""),
        JSONObject().put("t", "math").put("x", "x_{1,2} = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"),
        JSONObject("""{"t":"body","x":"Summe und Integral:"}"""),
        JSONObject().put("t", "math").put("x", "\\sum_{k=1}^{n} k = \\frac{n(n+1)}{2}, \\qquad \\int_0^\\infty e^{-x^2}\\,dx = \\frac{\\sqrt{\\pi}}{2}"),
        JSONObject().put("t", "math").put("x", "A = \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}, \\quad |x| = \\begin{cases} x & \\text{wenn } x \\geq 0 \\\\ -x & \\text{sonst} \\end{cases}"),
        JSONObject("""{"t":"body","x":"Fehler werden rot markiert:"}"""),
        JSONObject().put("t", "math").put("x", "\\frac{a}{b} \\foo"))

    @Test
    fun roundTrip() {
        val editor = RichEditor(ApplicationProvider.getApplicationContext(), EditorColors(0xFF000000.toInt(), 0xFF666666.toInt(), 0xFF999999.toInt(), 0xFFE6A200.toInt(), 0xFFFFE680.toInt())) { _, done -> done(null) }
        editor.load(blocks)
        assertEquals(blocks.map { it.toString() }, editor.toBlocks().map { it.toString() })
        editor.replaceBlock(blocks[2], JSONObject(blocks[2].toString()).put("x", "\\sqrt{2}"))
        assertEquals("\\sqrt{2}", editor.toBlocks()[2].getString("x"))
        editor.replaceBlock(JSONObject(blocks[2].toString()).put("x", "\\sqrt{2}"), null)
        assertEquals(blocks.size - 1, editor.toBlocks().size)
        editor.setSelection(editor.text!!.length)
        editor.insertMath(JSONObject().put("t", "math").put("x", "x^2"))
        assertEquals("x^2", editor.toBlocks().last { it.optString("t") == "math" }.getString("x"))
    }

    @Test
    fun screen() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        sync.proFeatures = true
        val note = sync.put("note", JSONObject().put("folder", Model.privateFolder(sync.userId)).put("created", Model.now()).put("modified", Model.now())
            .put("body", JSONArray(blocks)))
        val state = AppState(sync).apply { signedIn = true }
        state.push(Route.Editor(note.id))
        compose.setContent { LiNotesApp(state) }
        compose.waitForIdle()
        compose.mainClock.advanceTimeBy(500)
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/formeln.png")
        compose.onNodeWithContentDescription("Format").performClick()
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/formeln_format.png")
    }
}
