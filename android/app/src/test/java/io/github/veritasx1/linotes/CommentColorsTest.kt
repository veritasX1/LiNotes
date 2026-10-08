package io.github.veritasx1.linotes

import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import com.github.takahirom.roborazzi.captureScreenRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.CardSheet
import io.github.veritasx1.linotes.ui.CommentColorsSheet
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import io.github.veritasx1.linotes.ui.commentText
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Card 8f29c4b8 (way C, Olaf 07.10.): "[Name dd.mm. HH:MM]" in a card's notes in the colour the board gives that
 *  person; the notes stay plain text. The same cases as Ubuntu's test_comment_colors.py. */
@RunWith(org.robolectric.RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class CommentColorsTest {
    @get:Rule val compose = createComposeRule()
    private val out: String? = System.getProperty("linotes.shots")

    private val notes = "Olaf: bitte prüfen\n\n[Claude 07.10. 12:11] 🟠 gezogen\n\n[Jean-Marie 07.10. 19:36] 🟣 behoben\n" +
        "Text mit [Claude 07.10. 12:11] mittendrin"

    @Test
    fun headsInThePersonsColour() {
        // Heads at a line's start only – a quoted "[Claude …]" in the middle of a line is text.
        assertEquals(listOf("Claude", "Jean-Marie"), Model.commentHeads(notes).map { it.name })
        val head = Model.commentHeads(notes)[1]
        assertEquals("[Jean-Marie 07.10. 19:36]", notes.substring(head.start, head.end))
        assertEquals(listOf("Claude", "Jean-Marie", "Claude"),
            Model.commentHeads(notes.split(Regex("\\s+")).joinToString(" "), lineStart = false).map { it.name })
        assertTrue(Model.commentHeads("").isEmpty() && Model.commentHeads(null).isEmpty())
        assertTrue(Model.commentHeads("[Claude 7.10. 12:11] kein Kopf").isEmpty())

        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        val board = sync.put("board", JSONObject().put("name", "LiMail").put("order", 1).put("dev", true)).id
        val column = sync.put("column", JSONObject().put("board", board).put("name", "Testing").put("order", 1)).id
        val card = sync.put("card", JSONObject().put("board", board).put("column", column).put("title", "Benachrichtige mich")
            .put("order", 1).put("notes", notes)).id

        // „Tante Erna“: without colours nothing is coloured.
        assertEquals(emptyMap<String, Long>(), Model.commentColors(sync, board))
        assertTrue(commentText(notes, Model.commentColors(sync, board)).spanStyles.isEmpty())
        assertEquals(listOf("Claude", "Jean-Marie", "Olaf"), Model.commentNames(sync, board))

        // Chosen in the sheet: a name, then a colour – kept in the board.
        val state = AppState(sync).apply { signedIn = true }
        var open by androidx.compose.runtime.mutableStateOf(true)
        var sheet by androidx.compose.runtime.mutableStateOf(false)
        compose.setContent {
            if (open) CommentColorsSheet(sync, board) { open = false }
            else {
                LiNotesApp(state)
                if (sheet) CardSheet(state, card, sync.all("column").filter { it.data.optString("board") == board }) { sheet = false }
            }
        }
        compose.onNodeWithText("Jean-Marie").performClick()
        compose.onNodeWithText("Lila").performClick()
        compose.onNodeWithText("Claude").performClick()
        compose.onNodeWithText("Orange").performClick()
        compose.waitForIdle()
        assertTrue(open)   // back at the names, not closed
        compose.onNodeWithText("Jean-Marie – Lila").assertExists()
        if (out != null) captureScreenRoboImage("$out/comment-colors-sheet.png")
        assertEquals(mapOf("Jean-Marie" to 0xFF9B51E0, "Claude" to 0xFFE07A00), Model.commentColors(sync, board))

        // Only the heads take the colour, the text itself is unchanged; an unknown key is ignored.
        val shown = commentText(notes, Model.commentColors(sync, board))
        assertEquals(notes, shown.text)
        assertEquals(listOf(Color(0xFFE07A00), Color(0xFF9B51E0)), shown.spanStyles.map { it.item.color })
        assertEquals(head.start to head.end, shown.spanStyles[1].start to shown.spanStyles[1].end)
        sync.update(board) { it.getJSONObject("colors").put("Olaf", "gold") }
        assertEquals(2, Model.commentColors(sync, board).size)

        // Other changes of the board keep the colours (an update copies the whole data).
        sync.update(board) { it.put("name", "LiMail – Team") }
        assertEquals("purple", sync.get(board)!!.data.getJSONObject("colors").getString("Jean-Marie"))

        compose.runOnUiThread { open = false }
        compose.waitForIdle()
        compose.runOnUiThread { state.openTab(2); state.push(Route.Board(board)) }
        compose.mainClock.advanceTimeBy(1500)
        compose.waitForIdle()
        if (out != null) compose.onRoot().captureRoboImage("$out/comment-colors-board.png")
        compose.runOnUiThread { sheet = true }
        compose.mainClock.advanceTimeBy(1500)
        compose.waitForIdle()
        if (out != null) captureScreenRoboImage("$out/comment-colors-card.png")
        // Saving the card writes the plain text back – no colour in the notes.
        compose.runOnUiThread { sheet = false }
        compose.waitForIdle()
        assertEquals(notes, sync.get(card)!!.data.optString("notes"))
    }
}
