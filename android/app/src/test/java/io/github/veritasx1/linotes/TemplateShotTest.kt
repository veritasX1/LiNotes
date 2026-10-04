package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.LocalDate

/** "Neue Notiz aus Vorlage": own and shipped templates, placeholders filled in (pictures: -Pshots=<folder>). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class TemplateShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    @Test
    fun fromTemplate() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        sync.put("note", JSONObject().put("folder", Model.privateFolder(sync.userId)).put("created", Model.now()).put("modified", Model.now())
            .put("template", true).put("body", JSONArray().put(JSONObject().put("t", "title").put("x", "Wochenbericht {{Datum}}"))))
        val state = AppState(sync).apply { signedIn = true }
        state.push(Route.NoteList("all"))
        compose.setContent { LiNotesApp(state) }
        compose.waitForIdle()
        compose.onNodeWithContentDescription("Ansicht und Sortierung").performClick()
        compose.onNodeWithText("Neue Notiz aus Vorlage …").performClick()
        compose.waitForIdle()
        com.github.takahirom.roborazzi.captureScreenRoboImage("$out/vorlagen.png")
        compose.onNodeWithText("Besprechung").performClick()
        val today = LocalDate.now()
        val expected = "Besprechung %02d.%02d.%d".format(today.dayOfMonth, today.monthValue, today.year)
        compose.waitUntil(5000) { sync.all("note").any { Model.title(it) == expected } }
        assertTrue(sync.all("note").any { Model.title(it) == expected && !it.data.has("template") })
    }
}
