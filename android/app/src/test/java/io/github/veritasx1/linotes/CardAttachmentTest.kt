package io.github.veritasx1.linotes

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import com.github.takahirom.roborazzi.captureScreenRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.CardSheet
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Report
import io.github.veritasx1.linotes.ui.Route
import io.github.veritasx1.linotes.ui.cardFiles
import io.github.veritasx1.linotes.ui.humanSize
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.ByteArrayOutputStream

/** Karte 2d2086ee: files and pictures on cards (local mode, encrypted like note attachments). */
@RunWith(org.robolectric.RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class CardAttachmentTest {
    @get:Rule val compose = createComposeRule()
    private val out: String? = System.getProperty("linotes.shots")

    private fun png(): ByteArray {
        val bitmap = Bitmap.createBitmap(400, 250, Bitmap.Config.ARGB_8888)
        Canvas(bitmap).apply {
            drawColor(android.graphics.Color.rgb(40, 110, 200))
            drawCircle(200f, 125f, 70f, Paint().apply { color = android.graphics.Color.rgb(250, 200, 40) })
        }
        return ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
    }

    @Test
    fun attachmentsOnCards() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        val board = sync.put("board", JSONObject().put("name", "Testboard").put("order", 1)).id
        val column = sync.put("column", JSONObject().put("board", board).put("name", "Offen").put("order", 1)).id
        val image = png()
        val pdf = "%PDF-1.4 Test".toByteArray()
        val imageRef = sync.uploadFile(image, null)
        val pdfRef = sync.uploadFile(pdf, null)
        val files = JSONArray()
            .put(JSONObject().put("f", imageRef).put("n", "skizze.png").put("m", "image/png").put("b", image.size))
            .put(JSONObject().put("f", pdfRef).put("n", "lastenheft.pdf").put("m", "application/pdf").put("b", 2_400_000))
        val card = sync.put("card", JSONObject().put("board", board).put("column", column).put("title", "Lenkwinkelsensor kalibrieren")
            .put("order", 1).put("files", files)).id

        // Data: the attachments come back decrypted, and the report names them.
        assertEquals(listOf("skizze.png", "lastenheft.pdf"), cardFiles(sync.get(card)!!.data).map { it.optString("n") })
        assertTrue(sync.fetchFile(pdfRef, null).readBytes().contentEquals(pdf))
        assertEquals("skizze.png, lastenheft.pdf", Report.build(sync, board).rows.single().files)
        assertEquals("2,3 MB", humanSize(2_400_000))

        val state = AppState(sync).apply { signedIn = true }
        var sheet by androidx.compose.runtime.mutableStateOf(false)
        compose.setContent {
            LiNotesApp(state)
            if (sheet) CardSheet(state, card, sync.all("column").filter { it.data.optString("board") == board }) { sheet = false }
        }
        compose.runOnUiThread { state.openTab(2); state.push(Route.Board(board)) }
        compose.mainClock.advanceTimeBy(1500)
        compose.waitForIdle()
        if (out != null) compose.onRoot().captureRoboImage("$out/card-board.png")
        compose.runOnUiThread { sheet = true }
        compose.mainClock.advanceTimeBy(1500)
        compose.waitForIdle()
        if (out != null) captureScreenRoboImage("$out/card-sheet.png")
    }
}
