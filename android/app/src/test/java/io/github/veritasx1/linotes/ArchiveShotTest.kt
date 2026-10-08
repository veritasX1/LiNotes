package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.notesFor
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** The archive without a server: archived boards fold away under "Archiv", archived notes leave
 *  "Alle Notizen" (pictures: -Pshots=<folder>). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class ArchiveShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    @Test
    fun archive() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        fun note(title: String) = sync.put("note", JSONObject().put("folder", Model.privateFolder(sync.userId)).put("created", Model.now()).put("modified", Model.now())
            .put("body", JSONArray().put(JSONObject().put("t", "title").put("x", title))))
        note("Einkaufsideen")
        val old = note("Steuer 2024")
        sync.put("board", JSONObject().put("name", "Haushalt").put("order", 1))
        val done = sync.put("board", JSONObject().put("name", "Gartenhaus (fertig)").put("order", 2))
        val doneToo = sync.put("board", JSONObject().put("name", "Umzug 2024").put("order", 3))
        for (obj in listOf(old, done, doneToo)) Model.setArchived(sync, obj.id, true)
        assertEquals(listOf("Einkaufsideen"), notesFor(sync, "all").first.map { Model.title(it) })
        assertEquals(listOf("Steuer 2024"), notesFor(sync, "archive").first.map { Model.title(it) })
        Model.setArchived(sync, doneToo.id, false)
        Model.setArchived(sync, doneToo.id, true)

        val state = AppState(sync).apply { signedIn = true }
        state.openTab(2)
        compose.setContent { LiNotesApp(state) }
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/archiv_aufgaben_zu.png")
        compose.onNodeWithText("Archiv").performClick()
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/archiv_aufgaben_offen.png")
        compose.runOnUiThread { state.openTab(0) }
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/archiv_ordner.png")
    }
}
