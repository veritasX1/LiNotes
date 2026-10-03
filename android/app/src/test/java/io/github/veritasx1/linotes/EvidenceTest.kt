package io.github.veritasx1.linotes

import android.graphics.Bitmap
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureScreenRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.CardSheet
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Report
import io.github.veritasx1.linotes.ui.Route
import io.github.veritasx1.linotes.ui.cardEvidence
import io.github.veritasx1.linotes.ui.evidenceDetails
import io.github.veritasx1.linotes.ui.sha256
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.ByteArrayOutputStream

/** Karte ca6d76c2: verification evidence on development cards (SHA-256, who/when, report). */
@RunWith(org.robolectric.RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class EvidenceTest {
    @get:Rule val compose = createComposeRule()
    private val out: String? = System.getProperty("linotes.shots")

    @Test
    fun evidenceOnDevelopmentCards() {
        // Known SHA-256 test vector (FIPS 180-2).
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", sha256("abc".toByteArray()))

        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        val board = sync.put("board", JSONObject().put("name", "Spurhalteassistent").put("order", 1).put("dev", true)).id
        val column = sync.put("column", JSONObject().put("board", board).put("name", "Verifikation").put("order", 1)).id
        val bitmap = Bitmap.createBitmap(300, 120, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.rgb(48, 160, 80)) }
        val image = ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
        val protocol = "HIL-Lauf 2026-09-30: 12/12 bestanden".toByteArray()
        val evidence = JSONArray()
            .put(JSONObject().put("f", sync.uploadFile(protocol, null)).put("n", "HIL-Protokoll.txt").put("m", "text/plain")
                .put("b", protocol.size).put("h", sha256(protocol)).put("at", 1_790_000_000.0).put("by", sync.userId))
            .put(JSONObject().put("f", sync.uploadFile(image, null)).put("n", "SIL-Ergebnis.png").put("m", "image/png")
                .put("b", image.size).put("h", sha256(image)).put("at", 1_790_000_100.0).put("by", sync.userId))
        val card = sync.put("card", JSONObject().put("board", board).put("column", column).put("title", "Abschaltung unter 60 km/h")
            .put("order", 1).put("verification", "SIL-Test TC-LKA-031..036 bestanden").put("evidence", evidence)).id

        val items = cardEvidence(sync.get(card)!!.data)
        assertEquals(listOf("HIL-Protokoll.txt", "SIL-Ergebnis.png"), items.map { it.optString("n") })
        assertTrue(evidenceDetails(sync, items[0]).contains("Olaf") && evidenceDetails(sync, items[0]).contains("SHA-256 ${sha256(protocol).take(12)}"))

        val data = Report.build(sync, board)
        val records = data.rows.single().evidence
        assertEquals(sha256(protocol), records[0].sha256)
        assertNull(records[0].image)                      // only pictures are embedded
        assertEquals(items[1].optString("f"), records[1].image)
        // Pictures are fetched only while the PDF is written (off the main thread). Robolectric has no
        // working PdfDocument, so the PDF itself is checked on the phone.
        assertEquals(sync.fetchFile(records[1].image!!, records[1].share).readBytes().size, image.size)

        val state = AppState(sync).apply { signedIn = true }
        var sheet by androidx.compose.runtime.mutableStateOf(false)
        compose.setContent {
            LiNotesApp(state)
            if (sheet) CardSheet(state, card, sync.all("column").filter { it.data.optString("board") == board }) { sheet = false }
        }
        compose.runOnUiThread { state.openTab(2); state.push(Route.Board(board)); sheet = true }
        compose.mainClock.advanceTimeBy(1500)
        compose.waitForIdle()
        compose.onNodeWithText("Nachweis hinzufügen …").performScrollTo()
        compose.onNodeWithText("SIL-Ergebnis.png").assertExists()
        compose.mainClock.advanceTimeBy(500)
        compose.waitForIdle()
        if (out != null) captureScreenRoboImage("$out/card-evidence.png")
    }
}
