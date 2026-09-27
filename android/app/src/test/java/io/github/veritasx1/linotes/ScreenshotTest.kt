package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Api
import io.github.veritasx1.linotes.data.E2E
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.Pairing
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * Screens against a local v2 server (see docs/PLAN.md): the scratch server on
 * 127.0.0.1:8499 has user "anna"; the invite for "olaf" is in android_invite.txt.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class ScreenshotTest {
    @get:Rule val compose = createComposeRule()
    private val scratch = "/tmp/claude-1000/-home-olaf-winkler/307e9b08-3ef7-4558-9ee3-51920f668e56/scratchpad"
    private val out = "$scratch/android"
    private val server = "http://127.0.0.1:8499"

    private fun note(sync: SyncEngine, folder: String, vararg lines: Pair<String, String>) {
        val body = JSONArray()
        lines.forEach { (type, text) -> body.put(JSONObject().put("t", type).put("x", text)) }
        val now = Model.now()
        sync.put("note", JSONObject().put("folder", folder).put("body", body).put("created", now).put("modified", now))
    }

    private fun signedIn(): AppState {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        val account = E2E.Account.create()
        val identity = E2E.Identity.create()
        val invite = File("$scratch/android_invite.txt").readText().trim()
        val response = Api(server).register(invite, "olaf", "Olaf", account.auth, identity.exportSealed(account), "robolectric")
        sync.signIn(server, response, account)
        sync.syncNow()
        Model.ensureDefaults(sync)
        val folder = Model.privateFolder(sync.userId)
        note(sync, folder, "title" to "Urlaub an der Ostsee", "body" to "Zimmer in Kühlungsborn buchen", "check" to "Fahrräder mitnehmen")
        note(sync, folder, "title" to "Geschenkideen", "body" to "Anna: Kochbuch, Konzertkarten")
        val list = Model.defaultList(sync.userId)
        listOf("Milch", "Äpfel", "Brot", "Spülmittel").forEachIndexed { index, text ->
            sync.put("item", JSONObject().put("list", list).put("text", text).put("order", index).put("by", sync.userId))
        }
        val anna = sync.users.first { it.username == "anna" }
        Pairing.markVerified(sync, anna.id, E2E.fingerprint(anna.identity))
        sync.setSharing(list, listOf(anna.id))
        sync.syncNow()
        return AppState(sync).apply { signedIn = true }
    }

    private fun shot(name: String) {
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/$name.png")
    }

    @Test
    fun onboarding() {
        val state = AppState(SyncEngine(ApplicationProvider.getApplicationContext())).apply { signedIn = false }
        compose.setContent { LiNotesApp(state) }
        shot("a_onboarding")
    }

    @Test
    fun screens() {
        val state = signedIn()
        val sync = state.sync
        // Nothing readable on the server: the list name is encrypted.
        val raw = sync.api!!.pull(0).toString()
        assertFalse(raw.contains("Einkaufsliste") || raw.contains("Ostsee") || raw.contains("Milch"))
        assertTrue(sync.get(Model.defaultList(sync.userId))!!.share != null)

        compose.setContent { LiNotesApp(state) }
        shot("b_folders")
        state.push(Route.NoteList("all")); shot("c_notelist")
        val ostsee = sync.all("note").first { it.data.toString().contains("Ostsee") }
        state.push(Route.Editor(ostsee.id)); shot("d_editor")
        state.tab = 1; shot("e_lists")
        state.push(Route.ListDetail(Model.defaultList(sync.userId))); shot("f_listdetail")
        state.push(Route.Share(Model.defaultList(sync.userId))); shot("g_share")
        state.tab = 2; state.push(Route.Board(Model.defaultBoard(sync.userId))); shot("h_board")
        state.tab = 0; while (state.stack.size > 1) state.pop(); state.push(Route.Settings); shot("i_settings")
        state.push(Route.People); shot("j_people")
        state.push(Route.Help); shot("k_help")
    }
}
