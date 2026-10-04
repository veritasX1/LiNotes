package io.github.veritasx1.linotes.ui

import android.app.DatePickerDialog
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.DpOffset
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject
import org.json.JSONObject
import java.time.LocalDate

val CARD_COLORS = listOf("rot" to Color(0xFFE0463A), "orange" to Color(0xFFF08C00), "gelb" to Color(0xFFE6B800),
    "grün" to Color(0xFF2FA84F), "blau" to Color(0xFF2B7DE0), "lila" to Color(0xFF9B59D0))

/** Like Apple's Reminders: none, low, medium, high – shown as ! / !! / !!! before the title. */
val PRIORITIES = listOf("" to "Keine", "niedrig" to "Niedrig", "mittel" to "Mittel", "hoch" to "Hoch")
val PRIORITY_MARKS = mapOf("niedrig" to "!", "mittel" to "!!", "hoch" to "!!!")

/** One step of a card's status history. The column name is kept as it was,
 *  so the history stays readable after a column is renamed or deleted. */
/** Attachments of a card: the same {f, n, m, b} entries as file blocks in notes. */
fun cardFiles(data: JSONObject): List<JSONObject> {
    val array = data.optJSONArray("files") ?: return emptyList()
    return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
}

fun isImageFile(item: JSONObject) = item.optString("m").startsWith("image/")

/** Verification evidence of a development card: {f, n, m, b} plus SHA-256 (h), when (at) and who (by). */
fun cardEvidence(data: JSONObject): List<JSONObject> {
    val array = data.optJSONArray("evidence") ?: return emptyList()
    return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
}

fun sha256(bytes: ByteArray): String =
    java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

fun evidenceDetails(sync: SyncEngine, item: JSONObject): String {
    val parts = mutableListOf(humanSize(item.optLong("b")))
    val at = item.optDouble("at", 0.0)
    if (at > 0) {
        val moment = java.time.Instant.ofEpochMilli((at * 1000).toLong()).atZone(java.time.ZoneId.systemDefault())
        parts += "%02d.%02d.%d %02d:%02d".format(moment.dayOfMonth, moment.monthValue, moment.year, moment.hour, moment.minute)
    }
    if (item.has("by")) parts += sync.userName(item.optInt("by"))
    item.optString("h").takeIf { it.isNotEmpty() }?.let { parts += "SHA-256 ${it.take(12)}…" }
    return parts.joinToString(" · ")
}

fun humanSize(bytes: Long): String = when {
    bytes < 1024 -> "$bytes Bytes"
    bytes < 1024 * 1024 -> "${bytes / 1024} KB"
    else -> "%.1f MB".format(java.util.Locale.GERMANY, bytes / 1024.0 / 1024.0)
}

fun historyEntry(column: SyncObject?, columnId: String, userId: Int): JSONObject =
    JSONObject().put("c", columnId).put("n", column?.data?.optString("name") ?: "").put("at", Model.now()).put("by", userId)

/** Moving a card to another column: done date (last column) and history.
 *  The history is written on every board; only development projects show it. */
fun recordMove(data: JSONObject, columns: List<SyncObject>, columnId: String, userId: Int) {
    if (columns.lastOrNull()?.id == columnId) data.put("done_at", Model.now()) else data.remove("done_at")
    val history = data.optJSONArray("history") ?: org.json.JSONArray()
    history.put(historyEntry(columns.firstOrNull { it.id == columnId }, columnId, userId))
    data.put("history", history)
}

fun isDevBoard(board: SyncObject?) = board?.data?.optBoolean("dev") == true

fun shortId(id: String) = id.take(8)

private fun momentLabel(seconds: Double): String {
    val moment = java.time.Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(java.time.ZoneId.systemDefault())
    val time = "%02d:%02d".format(moment.hour, moment.minute)
    return when (java.time.temporal.ChronoUnit.DAYS.between(moment.toLocalDate(), LocalDate.now())) {
        0L -> "heute, $time"
        1L -> "gestern, $time"
        else -> "%02d.%02d.%d".format(moment.dayOfMonth, moment.monthValue, moment.year)
    }
}

/** Erstellt … · Bearbeitet … · Erledigt … (whatever is known). Ordinary boards keep it short. */
fun cardDates(card: SyncObject, dev: Boolean): String {
    val created = card.data.optDouble("created", 0.0)
    val done = card.data.optDouble("done_at", 0.0)
    return buildList {
        if (created > 0) add("Erstellt " + momentLabel(created))
        if (dev && card.updated > 0 && (created <= 0 || card.updated - created > 60)) add("Bearbeitet " + momentLabel(card.updated))
        if (done > 0) add("Erledigt " + momentLabel(done))
    }.joinToString(" · ")
}

@Composable
fun BoardsScreen(state: AppState, revision: Long) {
    val sync = state.sync
    val context = LocalContext.current
    val boards = remember(revision) { sync.all("board").sortedWith(compareBy({ it.data.optDouble("order", 0.0) }, { it.data.optString("name") })) }
    val cards = remember(revision) { sync.all("card") }
    var creating by remember { mutableStateOf<String?>(null) }
    var menu by remember { mutableStateOf<SyncObject?>(null) }
    var renaming by remember { mutableStateOf<SyncObject?>(null) }
    var moving by remember { mutableStateOf<SyncObject?>(null) }

    LargeTitleScreen(
        title = "Aufgaben",
        actions = { BarButton(Glyph.Plus, "Neues Board") { creating = "new" } },
    ) {
        if (boards.isEmpty()) item { EmptyState("Keine Boards", glyph = Glyph.Board) }
        // Grouped by folder: unfiled boards first, then one section per folder.
        // Drag a board onto a section heading to move it into that folder (or out, on "Boards").
        for ((folder, group) in groupByFolder(sync, boards)) section("boards-${folder?.id}", header = folder?.let { folderPath(sync, it) } ?: "Boards",
            headerDrop = Pair({ it.startsWith("board:") }, { dropOnFolder(state, it, folder?.id) })) {
            group.forEachIndexed { index, board ->
                GroupRow(board.data.optString("name", "Board"), Glyph.Board,
                    subtitle = shareLabel(sync, board),
                    detail = "${cards.count { it.data.optString("board") == board.id && !it.data.optBoolean("archived") }}",
                    divider = index < group.lastIndex, dragPayload = "board:${board.id}", onLongClick = { menu = board }) { state.push(Route.Board(board.id)) }
            }
        }
    }
    creating?.let { _ ->
        AlertDialog("Neues Board", confirm = "Erstellen", fields = listOf(AlertField("z. B. Haushalt")), onDismiss = { creating = null }) { values ->
            if (values[0].isNotBlank()) {
                val board = sync.put("board", JSONObject().put("name", values[0].trim()).put("order", Model.now()))
                Model.defaultColumns.forEachIndexed { order, (_, name) ->
                    sync.put("column", JSONObject().put("board", board.id).put("name", name).put("order", order))
                }
                state.push(Route.Board(board.id))
            }
            creating = null
        }
    }
    menu?.let { board ->
        ActionSheet(board.data.optString("name"), listOf(
            SheetAction("Umbenennen") { renaming = board },
            SheetAction("Verschieben nach …") { moving = board },
            SheetAction("Teilen …") { state.push(Route.Share(board.id)) },
            SheetAction("Bericht teilen (PDF) …") { Report.share(state, context, board.id) },
            SheetAction(if (isDevBoard(board)) "Entwicklungsprojekt ausschalten" else "Als Entwicklungsprojekt führen") {
                val dev = !isDevBoard(board)
                sync.update(board.id) { it.put("dev", dev) }
                state.toastLater(if (dev) "„${board.data.optString("name")}“ ist jetzt ein Entwicklungsprojekt." else "„${board.data.optString("name")}“ ist wieder ein einfaches Board.")
            },
            SheetAction("Board löschen", destructive = true) {
                for (child in sync.all("card") + sync.all("column")) if (child.data.optString("board") == board.id) sync.delete(child.id)
                sync.delete(board.id)
            },
        )) { menu = null }
    }
    moving?.let { board -> MoveToFolderSheet(state, board) { moving = null } }
    renaming?.let { board ->
        AlertDialog("Board umbenennen", confirm = "Sichern", fields = listOf(AlertField("Name", board.data.optString("name"))),
            onDismiss = { renaming = null }) { values ->
            if (values[0].isNotBlank()) sync.update(board.id) { it.put("name", values[0].trim()) }
            renaming = null
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun BoardScreen(state: AppState, boardId: String, revision: Long) {
    val colors = palette
    val sync = state.sync
    val board = remember(revision, boardId) { sync.get(boardId) } ?: return
    val columns = remember(revision, boardId) { sync.all("column").filter { it.data.optString("board") == boardId }.sortedBy { it.data.optDouble("order", 0.0) } }
    val cards = remember(revision, boardId) { sync.all("card").filter { it.data.optString("board") == boardId && !it.data.optBoolean("archived") } }
    var editing by remember { mutableStateOf<String?>(null) }
    var moving by remember { mutableStateOf<SyncObject?>(null) }
    var columnMenu by remember { mutableStateOf<SyncObject?>(null) }
    var renameColumn by remember { mutableStateOf<SyncObject?>(null) }
    var addColumn by remember { mutableStateOf(false) }
    // The magnifier finds cards by id, title, notes, fields, commits … (Model.cardMatches).
    var searching by remember(boardId) { mutableStateOf(false) }
    var query by remember(boardId) { mutableStateOf("") }
    val shown = if (searching && query.isNotBlank()) cards.filter { Model.cardMatches(it, query) { id -> sync.userName(id) } } else cards
    val width = LocalConfiguration.current.screenWidthDp

    Column(Modifier.fillMaxSize().background(colors.background).imePadding()) {
        NavBar("", "Aufgaben", { state.pop() }, actions = {
            BarButton(Glyph.Search, "Karten suchen") { searching = !searching; if (!searching) query = "" }
            BarButton(Glyph.Share, "Teilen") { state.push(Route.Share(board.id)) }
            BarButton(Glyph.Plus, "Spalte hinzufügen") { addColumn = true }
        })
        Text(board.data.optString("name"), style = Type.largeTitle, color = colors.label, modifier = Modifier.padding(horizontal = 16.dp))
        Text("${cards.size} Karten · " + shareLabel(sync, board) + if (isDevBoard(board)) " · Entwicklungsprojekt" else "",
            style = Type.subheadline, color = colors.secondary, modifier = Modifier.padding(horizontal = 16.dp))
        if (searching) {
            val focus = remember { androidx.compose.ui.focus.FocusRequester() }
            Row(Modifier.padding(horizontal = 16.dp).padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                SearchField(query, { query = it }, "Karten-ID, Titel, Notizen, Commit …", Modifier.weight(1f), focus)
                Spacer(Modifier.width(10.dp))
                TextButton("Abbrechen") { searching = false; query = "" }
            }
            if (query.isNotBlank()) Text(if (shown.size == 1) "1 Treffer" else "${shown.size} Treffer", style = Type.footnote, color = colors.secondary,
                modifier = Modifier.padding(horizontal = 16.dp).padding(top = 4.dp))
            androidx.compose.runtime.LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
        }
        Spacer(Modifier.height(10.dp))
        LazyRow(Modifier.weight(1f).navigationBarsPadding(), contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            // While searching only the columns with hits – the hit is right there, no swiping.
            items(if (shown === cards) columns else columns.filter { column -> shown.any { it.data.optString("column") == column.id } },
                key = { it.id }) { column ->
                val columnCards = shown.filter { it.data.optString("column") == column.id }.sortedBy { it.data.optDouble("order", 0.0) }
                val columnTotal = if (shown === cards) columnCards.size else cards.count { it.data.optString("column") == column.id }
                Column(Modifier.width((width * 0.82f).dp).fillMaxHeight().clip(RoundedCornerShape(14.dp)).background(if (colors.dark) colors.fill.copy(alpha = 0.5f) else colors.fill).padding(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(column.data.optString("name"), style = Type.headline, color = colors.label)
                        Spacer(Modifier.width(6.dp))
                        Text(if (shown === cards) "${columnCards.size}" else "${columnCards.size} / $columnTotal", style = Type.subheadline,
                            color = colors.secondary, modifier = Modifier.weight(1f))
                        BarButton(Glyph.More, "Spalte ${column.data.optString("name")} bearbeiten", tint = colors.secondary) { columnMenu = column }
                    }
                    LazyColumn(Modifier.weight(1f, fill = false), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(columnCards, key = { it.id }) { card ->
                            CardView(state, card, isLast = columns.lastOrNull()?.id == column.id, dev = isDevBoard(board),
                                onClick = { editing = card.id }, onLongClick = { moving = card })
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    AddCardField(colors.accent) { title ->
                        val order = (columnCards.lastOrNull()?.data?.optDouble("order", 0.0) ?: 0.0) + 1
                        sync.put("card", JSONObject().put("board", boardId).put("column", column.id).put("title", title)
                            .put("order", order).put("created_by", sync.userId).put("created", Model.now())
                            .put("history", org.json.JSONArray().put(historyEntry(column, column.id, sync.userId))), board.share)
                    }
                }
            }
        }
    }

    editing?.let { id -> CardSheet(state, id, columns) { editing = null } }
    moving?.let { card ->
        ActionSheet("„${card.data.optString("title")}“ verschieben nach", columns.filter { it.id != card.data.optString("column") }.map { column ->
            SheetAction(column.data.optString("name")) {
                val last = cards.filter { it.data.optString("column") == column.id }.maxOfOrNull { it.data.optDouble("order", 0.0) } ?: 0.0
                sync.update(card.id) { it.put("column", column.id).put("order", last + 1); recordMove(it, columns, column.id, sync.userId) }
            }
        } + SheetAction("Karte löschen", destructive = true) { sync.delete(card.id) }) { moving = null }
    }
    columnMenu?.let { column ->
        val index = columns.indexOf(column)
        ActionSheet(column.data.optString("name"), buildList {
            add(SheetAction("Umbenennen") { renameColumn = column })
            if (index > 0) add(SheetAction("Nach links") { swapColumns(state, columns, index, index - 1) })
            if (index < columns.lastIndex) add(SheetAction("Nach rechts") { swapColumns(state, columns, index, index + 1) })
            add(SheetAction("Spalte löschen", destructive = true) {
                cards.filter { it.data.optString("column") == column.id }.forEach { sync.delete(it.id) }
                sync.delete(column.id)
            })
        }) { columnMenu = null }
    }
    renameColumn?.let { column ->
        AlertDialog("Spalte umbenennen", confirm = "Sichern", fields = listOf(AlertField("Name", column.data.optString("name"))),
            onDismiss = { renameColumn = null }) { values ->
            if (values[0].isNotBlank()) sync.update(column.id) { it.put("name", values[0].trim()) }
            renameColumn = null
        }
    }
    if (addColumn) {
        AlertDialog("Neue Spalte", confirm = "Hinzufügen", fields = listOf(AlertField("Name")), onDismiss = { addColumn = false }) { values ->
            if (values[0].isNotBlank()) {
                val order = (columns.lastOrNull()?.data?.optDouble("order", 0.0) ?: -1.0) + 1
                sync.put("column", JSONObject().put("board", boardId).put("name", values[0].trim()).put("order", order), board.share)
            }
            addColumn = false
        }
    }
}

private fun swapColumns(state: AppState, columns: List<SyncObject>, a: Int, b: Int) {
    val ids = columns.map { it.id }.toMutableList()
    ids[a] = ids[b].also { ids[b] = ids[a] }
    ids.forEachIndexed { order, id -> state.sync.update(id) { it.put("order", order) } }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun CardView(state: AppState, card: SyncObject, isLast: Boolean, dev: Boolean, onClick: () -> Unit, onLongClick: () -> Unit) {
    val colors = palette
    val data = card.data
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colors.surface)
        .combinedClickable(onClick = onClick, onLongClick = onLongClick).padding(12.dp)) {
        CARD_COLORS.firstOrNull { it.first == data.optString("color") }?.let { (_, color) ->
            Box(Modifier.width(36.dp).height(5.dp).clip(CircleShape).background(color))
            Spacer(Modifier.height(6.dp))
        }
        val files = cardFiles(data)
        files.firstOrNull(::isImageFile)?.let { cover ->
            // The first picture as a cover, as in Trello or Apple's Freeform.
            Thumbnail(state.sync, cover.optString("f"), card.share, 96, Modifier.fillMaxWidth().height(96.dp))
            Spacer(Modifier.height(8.dp))
        }
        val mark = PRIORITY_MARKS[data.optString("priority")]
        Row {
            if (mark != null) {
                Text(mark, style = Type.headline.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.ExtraBold), color = colors.accentText)
                Spacer(Modifier.width(5.dp))
            }
            // Long titles take at most two lines; the whole title is in the card sheet.
            Text(data.optString("title"), style = Type.headline, color = colors.label, maxLines = 2,
                overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
        }
        if (data.optString("notes").isNotEmpty()) {
            // At most two lines, ending in "…" (like Mail's two-line preview); line breaks of the notes
            // become spaces so no line is wasted. The whole text is in the card sheet.
            Text(data.optString("notes").split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ").take(400),
                style = Type.footnote, color = colors.secondary, maxLines = 2, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
        }
        val due = runCatching { LocalDate.parse(data.optString("due")) }.getOrNull()
        val doneAt = data.optDouble("done_at", 0.0).takeIf { isLast && it > 0 }
        val assignee = data.optInt("assignee")
        if (due != null || doneAt != null || assignee != 0 || dev || files.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (files.isNotEmpty()) {
                    Text("📎 ${files.size}", style = Type.footnote, color = colors.secondary)
                    Spacer(Modifier.width(8.dp))
                }
                if (dev) {
                    Text(shortId(card.id), style = Type.caption.copy(fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace),
                        color = colors.tertiary)
                    Spacer(Modifier.width(8.dp))
                }
                if (due != null) {
                    val overdue = due.isBefore(LocalDate.now()) && !isLast
                    Text("Fällig: " + dueLabel(due), style = Type.footnote, color = if (overdue) colors.red else colors.secondary, modifier = Modifier.weight(1f))
                } else if (doneAt != null) {
                    val day = java.time.Instant.ofEpochMilli((doneAt * 1000).toLong()).atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                    Text("Erledigt: " + dueLabel(day), style = Type.footnote, color = colors.secondary, modifier = Modifier.weight(1f))
                } else Spacer(Modifier.weight(1f))
                if (assignee != 0) {
                    Text(state.sync.userName(assignee), style = Type.caption, color = colors.label,
                        modifier = Modifier.clip(CircleShape).background(colors.accent.copy(alpha = 0.25f)).padding(horizontal = 8.dp, vertical = 2.dp))
                }
            }
        }
    }
}

fun dueLabel(day: LocalDate): String {
    val delta = java.time.temporal.ChronoUnit.DAYS.between(LocalDate.now(), day)
    return when (delta) {
        0L -> "Heute"
        1L -> "Morgen"
        -1L -> "Gestern"
        else -> "%02d.%02d.".format(day.dayOfMonth, day.monthValue)
    }
}

@Composable
private fun AddCardField(accent: Color, onAdd: (String) -> Unit) {
    val colors = palette
    var text by remember { mutableStateOf("") }
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colors.surface.copy(alpha = 0.7f)).heightIn(min = 44.dp).padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically) {
        GlyphIcon(Glyph.Plus, accent, 14.dp)
        Spacer(Modifier.width(8.dp))
        Box(Modifier.weight(1f)) {
            if (text.isEmpty()) Text("Karte hinzufügen", style = Type.body, color = colors.secondary)
            BasicTextField(text, { text = it }, singleLine = true, textStyle = Type.body.copy(color = colors.label), cursorBrush = SolidColor(accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { if (text.isNotBlank()) onAdd(text.trim()); text = "" }),
                modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
internal fun CardSheet(state: AppState, cardId: String, columns: List<SyncObject>, onDone: () -> Unit) {
    val colors = palette
    val sync = state.sync
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val card = sync.get(cardId) ?: return onDone()
    var title by remember { mutableStateOf(card.data.optString("title")) }
    var notes by remember { mutableStateOf(card.data.optString("notes")) }
    var due by remember { mutableStateOf(card.data.optString("due").takeIf { it.isNotEmpty() && it != "null" }) }
    var assignee by remember { mutableStateOf(card.data.optInt("assignee")) }
    // Only people the board is shared with (and oneself) – not everyone one knows. Someone assigned
    // earlier who is no longer in the board stays visible, so it can be undone.
    val assignable = remember(card.share) {
        val inBoard = sync.shareMembers(card.share).toSet() + sync.userId
        val assigned = card.data.optInt("assignee")
        (inBoard + listOfNotNull(assigned.takeIf { it != 0 }))
            .map { id -> id to sync.userName(id) + if (id in inBoard) "" else " (nicht im Board)" }
            .sortedBy { it.second.lowercase() }
    }
    var color by remember { mutableStateOf(card.data.optString("color").takeIf { it.isNotEmpty() && it != "null" }) }
    var column by remember { mutableStateOf(card.data.optString("column")) }
    var priority by remember { mutableStateOf(card.data.optString("priority").takeIf { it in PRIORITY_MARKS } ?: "") }
    val dev = isDevBoard(sync.get(card.data.optString("board")))
    fun text(key: String) = card.data.optString(key).takeIf { it != "null" }.orEmpty()
    var impact by remember { mutableStateOf(text("impact")) }
    var verification by remember { mutableStateOf(text("verification")) }
    var version by remember { mutableStateOf(text("version")) }
    val scope = rememberCoroutineScope()
    var filesRevision by remember { mutableIntStateOf(0) }
    // Which list the attach menu adds to: "files" (attachments) or "evidence" (verification records).
    var attachMenu by remember { mutableStateOf<String?>(null) }
    val files = remember(filesRevision) { sync.get(cardId)?.let { cardFiles(it.data) } ?: emptyList() }
    val evidence = remember(filesRevision) { sync.get(cardId)?.let { cardEvidence(it.data) } ?: emptyList() }

    fun attach(name: String, mime: String, bytes: ByteArray, key: String = "files") {
        // Runs on in the background when the card is closed; the entry goes to the card either way.
        state.upload(name, bytes, card.share, target = "$cardId/$key") { reference ->
            val entry = JSONObject().put("f", reference).put("n", name).put("m", mime).put("b", bytes.size)
            if (key == "evidence") entry.put("h", sha256(bytes)).put("at", Model.now()).put("by", sync.userId)
            sync.update(cardId) { data ->
                val array = data.optJSONArray(key) ?: org.json.JSONArray()
                array.put(entry)
                data.put(key, array)
            }
            filesRevision++
        }
    }

    fun photoName(mime: String) = "Foto " + java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH.mm.ss")) +
        (if (mime == "image/png") ".png" else ".jpg")

    fun removeFile(index: Int, key: String = "files") {
        sync.update(cardId) { data ->
            val array = data.optJSONArray(key) ?: return@update
            array.remove(index)
            if (array.length() == 0) data.remove(key)
        }
        filesRevision++
    }

    fun openFile(item: JSONObject) {
        scope.launch {
            try {
                val file = withContext(Dispatchers.IO) {
                    val source = sync.fetchFile(item.getString("f"), card.share)
                    val folder = java.io.File(context.cacheDir, "attachments/" + item.getString("f").substringAfter(":").take(12)).apply { mkdirs() }
                    java.io.File(folder, java.io.File(item.optString("n", "Datei")).name).also { source.copyTo(it, overwrite = true) }
                }
                state.quickLook = LookFile(file, item.optString("m", "application/octet-stream"))
            } catch (error: Exception) {
                state.showToast(errorText(error))
            }
        }
    }

    fun save() {
        sync.update(cardId) { data ->
            data.put("title", title.trim().ifEmpty { data.optString("title") })
            data.put("notes", notes)
            if (due != null) data.put("due", due) else data.remove("due")
            if (assignee != 0) data.put("assignee", assignee) else data.remove("assignee")
            if (color != null) data.put("color", color) else data.remove("color")
            if (priority.isNotEmpty()) data.put("priority", priority) else data.remove("priority")
            if (dev) {
                for ((key, value) in listOf("impact" to impact, "verification" to verification, "version" to version)) {
                    if (value.isNotBlank()) data.put(key, value.trim()) else data.remove(key)
                }
            }
            if (column != data.optString("column")) {
                data.put("column", column)
                data.put("order", Model.now())
                recordMove(data, columns, column, sync.userId)
            }
        }
        onDone()
    }

    Dialog(onDismissRequest = { save() }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        UseWholeScreen()
        Column(Modifier.fillMaxSize().background(colors.background).navigationBarsPadding().imePadding()) {
            NavBar("Karte", null, null, actions = { TextButton("Fertig", bold = true) { save() } })
            Column(Modifier.verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
                FormSection {
                    FormField(title, { title = it }, "Titel")
                    HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
                    Box(Modifier.fillMaxWidth().heightIn(min = 110.dp).padding(16.dp)) {
                        if (notes.isEmpty()) Text("Notizen", style = Type.body, color = colors.tertiary)
                        BasicTextField(notes, { notes = it }, textStyle = Type.body.copy(color = colors.label), cursorBrush = SolidColor(colors.accent),
                            modifier = Modifier.fillMaxWidth())
                    }
                    val links = remember(notes) { LINK.findAll(notes).map { it.value.trimEnd('.', ',', ')', ';') }.distinct().toList() }
                    links.forEach { link ->
                        HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
                        Text(link, style = Type.subheadline, color = colors.accentText, maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                            modifier = Modifier.fillMaxWidth().clickable(onClickLabel = "Link öffnen") { runCatching { uriHandler.openUri(link) } }
                                .padding(horizontal = 16.dp, vertical = 12.dp))
                    }
                }
                FormSection {
                    PickerRow("Spalte", columns.map { it.id to it.data.optString("name") }, column, divider = true) { column = it }
                    PickerRow("Zuständig", listOf(0 to "Niemand") + assignable, assignee, divider = true) { assignee = it }
                    PickerRow("Priorität", PRIORITIES, priority, divider = true) { priority = it }
                    val label = due?.let { runCatching { LocalDate.parse(it) }.getOrNull() }?.let { "%02d.%02d.%d".format(it.dayOfMonth, it.monthValue, it.year) } ?: "Kein Datum"
                    GroupRow("Fällig", detail = label, chevron = false, divider = due != null) {
                        val start = due?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: LocalDate.now()
                        DatePickerDialog(context, { _, year, month, day ->
                            due = "%04d-%02d-%02d".format(year, month + 1, day)
                        }, start.year, start.monthValue - 1, start.dayOfMonth).show()
                    }
                    if (due != null) GroupRow("Datum entfernen", chevron = false, divider = false, titleColor = colors.red) { due = null }
                }
                FormSection("Farbe") {
                    Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Box(Modifier.size(30.dp).clip(CircleShape).background(colors.fill).clickable { color = null }, contentAlignment = Alignment.Center) {
                            if (color == null) GlyphIcon(Glyph.Close, colors.secondary, 12.dp)
                        }
                        CARD_COLORS.forEach { (name, value) ->
                            Box(Modifier.size(30.dp).clip(CircleShape).background(value).clickable { color = name }, contentAlignment = Alignment.Center) {
                                if (color == name) Box(Modifier.size(10.dp).clip(CircleShape).background(Color.White))
                            }
                        }
                    }
                }
                FormSection("Anhänge") {
                    AttachmentRows(sync, card.share, files, "Anhang entfernen", { humanSize(it.optLong("b")) }, ::openFile) { removeFile(it) }
                    UploadRows(state, "$cardId/files")
                    GroupRow("Datei oder Bild hinzufügen …", glyph = Glyph.Plus, chevron = false, divider = false) { attachMenu = "files" }
                }
                if (dev) {
                    FormSection("Auswirkungsanalyse") { MultiLineField(impact, { impact = it }, "Was ist betroffen, welche Risiken?") }
                    FormSection("Verifikation") { MultiLineField(verification, { verification = it }, "Tests, Prüfungen und Nachweise") }
                    // Evidence right below the verification text, so test records travel with the card.
                    FormSection("Nachweise") {
                        AttachmentRows(sync, card.share, evidence, "Nachweis entfernen", { evidenceDetails(sync, it) }, ::openFile) {
                            removeFile(it, "evidence")
                        }
                        UploadRows(state, "$cardId/evidence")
                        GroupRow("Nachweis hinzufügen …", glyph = Glyph.Plus, chevron = false, divider = false) { attachMenu = "evidence" }
                    }
                    if (evidence.isEmpty()) {
                        Text("Prüfprotokolle, Screenshots, Messdaten – liegen verschlüsselt an der Karte und erscheinen im Bericht mit Prüfsumme (SHA-256).",
                            style = Type.footnote, color = colors.secondary, modifier = Modifier.padding(start = 32.dp, end = 32.dp, top = 6.dp))
                    }
                    TraceSection(sync, card, version) { version = it }
                }
                Spacer(Modifier.height(16.dp))
                FormSection {
                    GroupRow("Karte löschen", chevron = false, divider = false, titleColor = colors.red) { sync.delete(cardId); onDone() }
                }
                if (files.isEmpty()) {
                    Text("Bilder, PDFs oder andere Dateien – verschlüsselt wie in Notizen.", style = Type.footnote, color = colors.secondary,
                        modifier = Modifier.padding(start = 32.dp, end = 32.dp, top = 8.dp))
                }
                val dates = cardDates(card, dev)
                if (dates.isNotEmpty()) {
                    Text(dates, style = Type.footnote, color = colors.secondary, modifier = Modifier.padding(start = 32.dp, end = 32.dp, top = 12.dp))
                }
            }
        }
    }
    attachMenu?.let { key ->
        ActionSheet(null, listOf(
            SheetAction("Foto aufnehmen") { state.takePhoto { bytes, mime -> attach(photoName(mime), mime, bytes, key) } },
            SheetAction("Aus Fotos wählen") { state.pickImage { bytes, mime -> attach(photoName(mime), mime, bytes, key) } },
            SheetAction("Datei wählen …") { state.pickFile { name, mime, bytes -> attach(name, mime, bytes, key) } },
        )) { attachMenu = null }
    }
}

/** Rows of attachments or evidence: picture or document symbol, name, details, remove. */
@Composable
private fun AttachmentRows(
    sync: SyncEngine, share: String?, items: List<JSONObject>, removeLabel: String,
    details: (JSONObject) -> String, onOpen: (JSONObject) -> Unit, onRemove: (Int) -> Unit,
) {
    val colors = palette
    items.forEachIndexed { index, item ->
        Row(Modifier.fillMaxWidth().clickable(onClickLabel = "Öffnen") { onOpen(item) }.padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically) {
            if (isImageFile(item)) Thumbnail(sync, item.optString("f"), share, 40)
            else Box(Modifier.size(40.dp).clip(RoundedCornerShape(6.dp)).background(colors.fill), contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Notes, colors.secondary, 20.dp)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(item.optString("n", "Datei"), style = Type.body, color = colors.label, maxLines = 1,
                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                Text(details(item), style = Type.footnote, color = colors.secondary)
            }
            Box(Modifier.size(44.dp).clickable(onClickLabel = removeLabel) { onRemove(index) }, contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Trash, colors.red, 18.dp)
            }
        }
        HorizontalDivider(Modifier.padding(start = 68.dp), 0.5.dp, colors.separator)
    }
}

@Composable
fun FormSection(header: String? = null, content: @Composable () -> Unit) {
    val colors = palette
    Column(Modifier.padding(horizontal = 16.dp).padding(top = 18.dp)) {
        if (header != null) Text(header, style = Type.footnote, color = colors.secondary, modifier = Modifier.padding(start = 16.dp, bottom = 6.dp))
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colors.surface)) { content() }
    }
}

@Composable
fun FormField(value: String, onChange: (String) -> Unit, placeholder: String) {
    val colors = palette
    Box(Modifier.fillMaxWidth().heightIn(min = 46.dp).padding(horizontal = 16.dp), contentAlignment = Alignment.CenterStart) {
        if (value.isEmpty()) Text(placeholder, style = Type.body, color = colors.tertiary)
        BasicTextField(value, onChange, singleLine = true, textStyle = Type.headline.copy(color = colors.label), cursorBrush = SolidColor(colors.accent),
            modifier = Modifier.fillMaxWidth())
    }
}

/** Development projects: card id and who moved the card where, when. */
@Composable
private fun TraceSection(sync: io.github.veritasx1.linotes.data.SyncEngine, card: SyncObject, version: String, onVersion: (String) -> Unit) {
    val colors = palette
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    FormSection("Nachverfolgung") {
        GroupRow("Karten-ID", detail = shortId(card.id), chevron = false, divider = true) {
            clipboard.setText(androidx.compose.ui.text.AnnotatedString(shortId(card.id)))
        }
        Row(Modifier.fillMaxWidth().heightIn(min = 44.dp).padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Version", style = Type.body, color = colors.label, modifier = Modifier.width(110.dp))
            Box(Modifier.weight(1f), contentAlignment = Alignment.CenterEnd) {
                if (version.isEmpty()) Text("z. B. 2.1", style = Type.body, color = colors.tertiary)
                BasicTextField(version, onVersion, singleLine = true, textStyle = Type.body.copy(color = colors.secondary, textAlign = androidx.compose.ui.text.style.TextAlign.End),
                    cursorBrush = SolidColor(colors.accent), modifier = Modifier.fillMaxWidth())
            }
        }
        HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
        val commits = card.data.optJSONArray("commits")
        if (commits == null || commits.length() == 0) {
            GroupRow("Noch keine Commits", subtitle = "Commits mit der Karten-ID werden verknüpft.", chevron = false, divider = true, titleColor = colors.secondary)
        } else {
            for (index in 0 until commits.length()) {
                val commit = commits.getJSONObject(index)
                GroupRow(commit.optString("s"), subtitle = "Commit " + commit.optString("h"), chevron = false, divider = true)
            }
        }
        val history = card.data.optJSONArray("history")
        if (history == null || history.length() == 0) {
            GroupRow("Noch kein Verlauf", subtitle = "Beginnt mit dem nächsten Verschieben.", chevron = false, divider = false, titleColor = colors.secondary)
        } else {
            for (index in history.length() - 1 downTo 0) {
                val step = history.getJSONObject(index)
                val moment = java.time.Instant.ofEpochMilli((step.optDouble("at", 0.0) * 1000).toLong()).atZone(java.time.ZoneId.systemDefault())
                GroupRow(step.optString("n").ifEmpty { "Spalte" }, chevron = false, divider = index > 0,
                    subtitle = "%02d.%02d.%d %02d:%02d · %s".format(moment.dayOfMonth, moment.monthValue, moment.year,
                        moment.hour, moment.minute, sync.userName(step.optInt("by"))))
            }
        }
    }
}

@Composable
private fun MultiLineField(value: String, onChange: (String) -> Unit, placeholder: String) {
    val colors = palette
    Box(Modifier.fillMaxWidth().heightIn(min = 70.dp).padding(16.dp)) {
        if (value.isEmpty()) Text(placeholder, style = Type.body, color = colors.tertiary)
        BasicTextField(value, onChange, textStyle = Type.body.copy(color = colors.label), cursorBrush = SolidColor(colors.accent),
            modifier = Modifier.fillMaxWidth())
    }
}

private val LINK = Regex("""https?://\S+""")

/** A row with the current value that opens a menu of choices (like a UIKit pull-down button). */
@Composable
fun <T> PickerRow(title: String, options: List<Pair<T, String>>, selected: T, divider: Boolean, onSelect: (T) -> Unit) {
    val colors = palette
    var open by remember { mutableStateOf(false) }
    Box {
        GroupRow(title, detail = options.firstOrNull { it.first == selected }?.second ?: "", chevron = false, divider = divider,
            trailing = { Spacer(Modifier.width(6.dp)); GlyphIcon(Glyph.UpDown, colors.tertiary, 14.dp) }) { open = true }
        // Anchored at the right edge, under the current value.
        Box(Modifier.align(Alignment.BottomEnd)) {
            DropdownMenu(open, { open = false }, offset = DpOffset((-16).dp, 0.dp),
                shape = RoundedCornerShape(12.dp), containerColor = if (colors.dark) Color(0xFF2C2C2E) else colors.surface) {
                options.forEach { (value, label) ->
                    DropdownMenuItem(
                        text = { Text(label, style = Type.body, color = colors.label) },
                        trailingIcon = { if (value == selected) Text("✓", style = Type.headline, color = colors.accentText) },
                        onClick = { onSelect(value); open = false },
                    )
                }
            }
        }
    }
}
