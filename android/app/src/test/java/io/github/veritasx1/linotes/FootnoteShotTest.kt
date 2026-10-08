package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.EditorColors
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.RichEditor
import io.github.veritasx1.linotes.ui.Route
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Footnotes renumber themselves and survive a round trip; the list shows under the note (pictures: -Pshots=<folder>). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class FootnoteShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"
    private val blocks = listOf(
        JSONObject("""{"t":"title","x":"Gartenhaus planen"}"""),
        JSONObject("""{"t":"body","x":"Fundament aus Punktfundamenten1 reicht bei leichten Häusern.","s":[[30,31,"fn:Müller, Gartenbau, 2020, S. 41"]]}"""),
        JSONObject("""{"t":"body","x":"Holz vorher lasieren2.","s":[[20,21,"fn:Herstellerhinweis Lasur, Abschnitt 3"]]}"""))

    @Test
    fun renumber() {
        val editor = RichEditor(ApplicationProvider.getApplicationContext(), EditorColors(0xFF000000.toInt(), 0xFF666666.toInt(), 0xFF999999.toInt(), 0xFFE6A200.toInt(), 0xFFFFE680.toInt())) { _, done -> done(null) }
        editor.load(blocks)
        editor.setSelection(editor.text!!.indexOf("Fundament") + 9)
        editor.insertFootnote("DIN 1052 Holzbau")
        val saved = editor.toBlocks().map { JSONObject(it.toString()) }
        assertEquals("Fundament1 aus Punktfundamenten2 reicht bei leichten Häusern.", saved[1].getString("x"))
        assertEquals("Holz vorher lasieren3.", saved[2].getString("x"))
        assertEquals(listOf("DIN 1052 Holzbau", "Müller, Gartenbau, 2020, S. 41", "Herstellerhinweis Lasur, Abschnitt 3"), Model.footnotes(saved))
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
        compose.onRoot().captureRoboImage("$out/fussnoten.png")
        compose.onNodeWithContentDescription("Format").performClick()
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/fussnoten_format.png")
    }
}
