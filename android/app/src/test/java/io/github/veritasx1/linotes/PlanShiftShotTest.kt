package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Plans
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import java.time.LocalDate

/** A project plan with shifted milestones, without a server: the timeline with the old days faded and
 *  "verschoben" (the PDF needs a device – Robolectric has no PdfDocument). Pictures: -Pshots=<folder>. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class PlanShiftShotTest {
    @get:Rule val compose = createComposeRule()
    private val out = System.getProperty("linotes.shots") ?: "build/shots"

    @Test
    fun shiftedMilestones() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        val start = Plans.monday(LocalDate.now())
        var plan = Plans.template("projektplan").put("name", "Projektplan LiCal")
        plan = Plans.setTaskDay(plan, 3, "from", start.plusDays(28).toString(), sync.userId, 1_791_000_000.0)
        plan = Plans.setTaskDay(plan, 3, "from", start.plusDays(35).toString(), sync.userId, 1_791_090_000.0)
        val obj = sync.put("plan", plan)
        assertEquals(2, Plans.shifts(sync.get(obj.id)!!.data).size)
        File(out).mkdirs()

        val state = AppState(sync).apply { signedIn = true }
        state.openTab(3)
        state.push(Route.Plan(obj.id))
        compose.setContent { LiNotesApp(state) }
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/plan_shifts.png")
    }
}
