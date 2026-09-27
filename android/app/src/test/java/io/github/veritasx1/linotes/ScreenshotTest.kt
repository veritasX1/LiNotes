package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Api
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class ScreenshotTest {
    @get:Rule val compose = createComposeRule()
    private val out = "/tmp/claude-1000/-home-olaf-winkler/307e9b08-3ef7-4558-9ee3-51920f668e56/scratchpad/android"

    private fun signedIn(): AppState {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        val server = "http://127.0.0.1:8499"
        sync.signIn(server, Api(server).login("olaf", "testpass1", "robolectric"))
        sync.syncNow()
        Model.ensureDefaults(sync)
        return AppState(sync).apply { signedIn = true }
    }

    private fun shot(name: String) {
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/$name.png")
    }

    @Test
    fun login() {
        val state = AppState(SyncEngine(ApplicationProvider.getApplicationContext())).apply { signedIn = false }
        compose.setContent { LiNotesApp(state) }
        shot("a_login")
    }

    @Test
    fun screens() {
        val state = signedIn()
        compose.setContent { LiNotesApp(state) }
        shot("b_folders")
        state.push(Route.NoteList("all")); shot("c_notelist")
        val ostsee = state.sync.all("note").first { it.data.toString().contains("Ostsee") }
        state.push(Route.Editor(ostsee.id)); shot("d_editor")
        state.tab = 1; shot("e_lists")
        state.push(Route.ListDetail(Model.SHARED_LIST)); shot("f_listdetail")
        state.tab = 2; state.push(Route.Board(Model.SHARED_BOARD)); shot("g_board")
        state.tab = 0; while (state.stack.size > 1) state.pop(); state.push(Route.Settings); shot("h_settings")
    }
}
