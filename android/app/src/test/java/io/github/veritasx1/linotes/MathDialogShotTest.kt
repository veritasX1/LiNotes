package io.github.veritasx1.linotes

import androidx.compose.foundation.layout.padding
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.ui.MathEditorContent
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Picture of the formula dialog (card 25ae467f), only with -Pshots=<folder>: run on its own it
 *  passes, in the full suite Compose never gets idle around the text field (something left running
 *  by other test classes) – the dialog's logic is covered by MathTexTest. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class MathDialogShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    @Test
    fun dialog() {
        org.junit.Assume.assumeTrue("nur mit -Pshots", System.getProperty("linotes.shots") != null)
        compose.setContent {
            io.github.veritasx1.linotes.ui.LiNotesTheme {
                androidx.compose.foundation.layout.Box(androidx.compose.ui.Modifier.padding(16.dp)) {
                    MathEditorContent(JSONObject().put("t", "math").put("x", "\\int_0^1 x^2\\,dx = \\frac{1}{3} \\foo"), {}, {}, picture = true)
                }
            }
        }
        compose.onNodeWithText("Rot markierte Teile kennt LiNotes nicht.").assertExists()
        compose.onRoot().captureRoboImage("$out/formeln_dialog.png")
    }
}
