package io.github.veritasx1.linotes

import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
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
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Code blocks with colors; "Code" in the format panel only with Profi-Funktionen (pictures: -Pshots=<folder>). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class CodeShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    @Test
    fun code() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        fun line(t: String, x: String, lang: String? = null) = JSONObject().put("t", t).put("x", x).also { if (lang != null) it.put("lang", lang) }
        val note = sync.put("note", JSONObject().put("folder", Model.privateFolder(sync.userId)).put("created", Model.now()).put("modified", Model.now())
            .put("body", JSONArray().put(line("title", "Skript-Notiz")).put(line("body", "So rechnet LiNotes:"))
                .put(line("code", "def add(a, b=2):  # Summe", "python")).put(line("code", "    return a + b", "python"))
                .put(line("body", "Und in der Shell:")).put(line("code", "if [ \"\$1\" = \"-v\" ]; then echo \"laut\"; fi  # Ausgabe", "shell"))))
        val state = AppState(sync).apply { signedIn = true }
        state.push(Route.Editor(note.id))
        compose.setContent { LiNotesApp(state) }
        compose.waitForIdle()
        compose.onNodeWithContentDescription("Format").performClick()
        compose.waitForIdle()
        compose.onAllNodesWithText("Python").assertCountEquals(0)   // Profi-Funktionen off: no "Code"
        compose.onRoot().captureRoboImage("$out/code_profi_aus.png")
        compose.onNodeWithContentDescription("Format").performClick()
        compose.runOnUiThread { sync.proFeatures = true }
        compose.onNodeWithContentDescription("Format").performClick()
        compose.waitForIdle()
        compose.onAllNodesWithText("Python").assertCountEquals(1)
        compose.onRoot().captureRoboImage("$out/code_profi_an.png")
    }
}
