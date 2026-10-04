package io.github.veritasx1.linotes

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.ui.InlineCalendar
import io.github.veritasx1.linotes.ui.LiNotesTheme
import io.github.veritasx1.linotes.ui.palette
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.LocalDate

/** The inline calendar for due dates, light and dark (pictures: -Pshots=<folder>). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class CalendarShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    private fun shot(name: String) {
        compose.setContent {
            LiNotesTheme {
                Box(Modifier.background(palette.background).padding(16.dp)) {
                    Box(Modifier.background(palette.surface)) { InlineCalendar(LocalDate.of(2026, 10, 16)) {} }
                }
            }
        }
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/$name.png")
    }

    @Test @Config(sdk = [34], qualifiers = "w393dp-h600dp-xxhdpi")
    fun light() = shot("kalender_hell")

    @Test @Config(sdk = [34], qualifiers = "w393dp-h600dp-night-xxhdpi")
    fun dark() = shot("kalender_dunkel")
}
