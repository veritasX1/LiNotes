package io.github.veritasx1.linotes.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

// ================================================================
// FOLDERS (the start screen of Notes)
// ================================================================

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun FoldersScreen(state: AppState, revision: Long) {
    val colors = palette
    val sync = state.sync
    var query by remember { mutableStateOf("") }
    var newFolder by remember { mutableStateOf(false) }
    var folderMenu by remember { mutableStateOf<SyncObject?>(null) }
    var rename by remember { mutableStateOf<SyncObject?>(null) }

    val notes = remember(revision) { sync.all("note") }
    val live = notes.filter { !it.data.has("trashed") }
    val folders = remember(revision) { sync.all("folder").sortedWith(compareBy({ it.data.optDouble("order", 0.0) }, { it.data.optString("name").lowercase() })) }
    val tags = live.flatMap { Model.tags(it) }.groupingBy { it }.eachCount().toSortedMap()
    fun count(predicate: (SyncObject) -> Boolean) = live.count(predicate)

    LargeTitleScreen(
        title = "Ordner",
        actions = { BarButton(Glyph.Gear, "Einstellungen") { state.push(Route.Settings) } },
        bottomBar = {
            BottomToolbar(
                center = "",
                leading = { BarButton(Glyph.FolderShared, "Neuer Ordner") { newFolder = true } },
                trailing = { BarButton(Glyph.Compose, "Neue Notiz") { newNote(state, null) } },
            )
        },
    ) {
        item(key = "search") {
            SearchField(query, { query = it }, modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp))
        }
        if (query.isNotBlank()) {
            val hits = live.filter { Model.text(it).contains(query, true) || Model.title(it).contains(query, true) }
            section("hits", header = "${hits.size} Treffer") {
                hits.sortedByDescending { Model.modified(it) }.forEachIndexed { index, note ->
                    NoteRow(state, note, index < hits.lastIndex) { state.push(Route.Editor(note.id)) }
                }
            }
            return@LargeTitleScreen
        }
        section("mine", header = "Meine Notizen") {
            GroupRow("Alle Notizen", Glyph.Notes, detail = "${live.size}") { state.push(Route.NoteList("all")) }
            folders.filter { it.share == null }.forEach { folder ->
                GroupRow(folder.data.optString("name", "Ordner"), Glyph.Folder, detail = "${count { it.data.optString("folder") == folder.id }}",
                    onLongClick = { folderMenu = folder }) { state.push(Route.NoteList("folder:${folder.id}")) }
            }
            GroupRow("Gesperrt", Glyph.Lock, detail = "${count { it.data.has("enc") }}") { state.push(Route.NoteList("locked")) }
            GroupRow("Zuletzt gelöscht", Glyph.Trash, detail = "${notes.count { it.data.has("trashed") }}", divider = false) {
                state.push(Route.NoteList("trash"))
            }
        }
        val shared = folders.filter { it.share != null }
        val loose = live.filter { it.share != null && sync.get(it.data.optString("folder")) == null }
        if (shared.isNotEmpty() || loose.isNotEmpty()) section("shared", header = "Geteilt", footer = "Geteilte Ordner und Notizen – Ende-zu-Ende verschlüsselt.") {
            if (loose.isNotEmpty()) GroupRow("Mit mir geteilt", Glyph.Person, detail = "${loose.size}", divider = shared.isNotEmpty()) {
                state.push(Route.NoteList("shared-notes"))
            }
            shared.forEachIndexed { index, folder ->
                GroupRow(folder.data.optString("name", "Ordner"), Glyph.FolderShared, detail = "${count { it.data.optString("folder") == folder.id }}",
                    divider = index < shared.lastIndex, onLongClick = { folderMenu = folder }) {
                    state.push(Route.NoteList("folder:${folder.id}"))
                }
            }
        }
        if (tags.isNotEmpty()) {
            item(key = "tags") {
                Column(Modifier.padding(horizontal = 16.dp).padding(top = 18.dp)) {
                    Text("Tags", style = Type.title3.copy(fontWeight = FontWeight.Bold), color = colors.label, modifier = Modifier.padding(start = 4.dp, bottom = 8.dp))
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        tags.forEach { (tag, _) ->
                            Text("#$tag", style = Type.subheadline, color = colors.label,
                                modifier = Modifier.clip(RoundedCornerShape(16.dp)).background(colors.surface)
                                    .clickable { state.push(Route.NoteList("tag:$tag")) }.padding(horizontal = 12.dp, vertical = 6.dp))
                        }
                    }
                }
            }
        }
    }

    if (newFolder) {
        FolderDialog(onDismiss = { newFolder = false }) { name, isShared ->
            sync.put("folder", JSONObject().put("name", name).put("order", Model.now()))
            newFolder = false
        }
    }
    folderMenu?.let { folder ->
        val protected = folder.id == Model.privateFolder(sync.userId)
        ActionSheet(folder.data.optString("name"), buildList {
            add(SheetAction("Umbenennen") { rename = folder })
            add(SheetAction("Teilen …") { state.push(Route.Share(folder.id)) })
            if (!protected) add(SheetAction("Ordner löschen", destructive = true) {
                for (note in sync.all("note")) if (note.data.optString("folder") == folder.id) sync.update(note.id) { it.put("trashed", Model.now()) }
                sync.delete(folder.id)
            })
        }) { folderMenu = null }
    }
    rename?.let { folder ->
        AlertDialog("Ordner umbenennen", confirm = "Sichern", fields = listOf(AlertField("Name", folder.data.optString("name"))),
            onDismiss = { rename = null }) { values ->
            if (values[0].isNotBlank()) sync.update(folder.id) { it.put("name", values[0].trim()) }
            rename = null
        }
    }
}

@Composable
fun FolderDialog(onDismiss: () -> Unit, onCreate: (String, Boolean) -> Unit) {
    AlertDialog("Neuer Ordner", "Neue Ordner sind privat. Über „Teilen“ kannst du sie freigeben.", "Sichern",
        fields = listOf(AlertField("Name")), onDismiss = onDismiss) { values ->
        if (values[0].isNotBlank()) onCreate(values[0].trim(), false) else onDismiss()
    }
}

fun newNote(state: AppState, folderKey: String?) {
    val sync = state.sync
    val folder = folderKey?.removePrefix("folder:")?.let { sync.get(it) } ?: sync.get(Model.privateFolder(sync.userId))
    val now = Model.now()
    val body = org.json.JSONArray().put(JSONObject().put("t", "title").put("x", ""))
    val note = sync.put("note", JSONObject().put("folder", folder?.id).put("body", body).put("created", now).put("modified", now),
        folder?.share)
    state.push(Route.Editor(note.id))
}

// ================================================================
// NOTE LIST
// ================================================================

fun notesFor(sync: SyncEngine, key: String): Pair<List<SyncObject>, String> {
    val notes = sync.all("note")
    if (key == "trash") return notes.filter { it.data.has("trashed") } to "Zuletzt gelöscht"
    val live = notes.filter { !it.data.has("trashed") }
    return when {
        key == "locked" -> live.filter { it.data.has("enc") } to "Gesperrt"
        key == "shared-notes" -> live.filter { it.share != null && sync.get(it.data.optString("folder")) == null } to "Mit mir geteilt"
        key.startsWith("folder:") -> {
            val id = key.removePrefix("folder:")
            live.filter { it.data.optString("folder") == id } to (sync.get(id)?.data?.optString("name") ?: "Ordner")
        }
        key.startsWith("tag:") -> {
            val tag = key.removePrefix("tag:")
            live.filter { tag in Model.tags(it) } to "#$tag"
        }
        else -> live to "Alle Notizen"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NoteListScreen(state: AppState, key: String, revision: Long) {
    val sync = state.sync
    val (notes, title) = remember(revision, key) { notesFor(sync, key) }
    var query by remember { mutableStateOf("") }
    var menu by remember { mutableStateOf<SyncObject?>(null) }
    var moving by remember { mutableStateOf<SyncObject?>(null) }
    var locking by remember { mutableStateOf<Pair<SyncObject, Boolean>?>(null) }

    val shown = notes.filter { query.isBlank() || Model.text(it).contains(query, true) }
    val pinned = shown.filter { it.data.optBoolean("pinned") && key != "trash" }.sortedByDescending { Model.modified(it) }
    val others = (shown - pinned.toSet()).sortedByDescending { Model.modified(it) }
    val groups = others.groupBy { Model.dateGroup(Model.modified(it)) }

    LargeTitleScreen(
        title = title,
        backLabel = "Ordner",
        onBack = { state.pop() },
        bottomBar = {
            BottomToolbar(
                center = if (notes.size == 1) "1 Notiz" else "${notes.size} Notizen",
                trailing = { if (key != "trash") BarButton(Glyph.Compose, "Neue Notiz") { newNote(state, key.takeIf { it.startsWith("folder:") }) } },
            )
        },
    ) {
        item(key = "search") { SearchField(query, { query = it }, modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) }
        if (shown.isEmpty()) item(key = "empty") { EmptyState(if (query.isBlank()) "Keine Notizen" else "Keine Treffer") }
        if (pinned.isNotEmpty()) section("pinned", header = "Angeheftet") {
            pinned.forEachIndexed { index, note -> SwipeNoteRow(state, note, index < pinned.lastIndex, key, onMenu = { menu = note }) }
        }
        groups.forEach { (group, items) ->
            section("group-$group", header = group) {
                items.forEachIndexed { index, note -> SwipeNoteRow(state, note, index < items.lastIndex, key, onMenu = { menu = note }) }
            }
        }
    }

    menu?.let { note ->
        val trashed = note.data.has("trashed")
        val locked = note.data.has("enc")
        ActionSheet(Model.title(note), if (trashed) listOf(
            SheetAction("Wiederherstellen") { restoreNote(state, note) },
            SheetAction("Endgültig löschen", destructive = true) { sync.delete(note.id) },
        ) else listOf(
            SheetAction(if (note.data.optBoolean("pinned")) "Lösen" else "Anheften") { sync.update(note.id) { it.put("pinned", !it.optBoolean("pinned")) } },
            SheetAction("Verschieben …") { moving = note },
            SheetAction("Teilen …") { if (locked) state.toastLater("Gesperrte Notizen können nicht geteilt werden.") else state.push(Route.Share(note.id)) },
            SheetAction(if (locked) "Sperre entfernen" else "Notiz sperren") { locking = note to !locked },
            SheetAction("Löschen", destructive = true) { trashNote(state, note) },
        )) { menu = null }
    }
    moving?.let { note -> MoveSheet(state, note) { moving = null } }
    locking?.let { (note, lock) -> LockFlow(state, note, lock) { locking = null } }
}

fun trashNote(state: AppState, note: SyncObject) {
    state.sync.update(note.id) { it.put("trashed", Model.now()) }
    state.toastLater("In „Zuletzt gelöscht“ verschoben")
}

fun restoreNote(state: AppState, note: SyncObject) {
    val sync = state.sync
    sync.update(note.id) { data ->
        data.remove("trashed")
        if (sync.get(data.optString("folder")) == null)
            data.put("folder", Model.privateFolder(sync.userId))
    }
    state.toastLater("Notiz wiederhergestellt")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SwipeNoteRow(state: AppState, note: SyncObject, divider: Boolean, key: String, onMenu: () -> Unit) {
    val colors = palette
    val dismiss = rememberSwipeToDismissBoxState(confirmValueChange = { value ->
        when (value) {
            SwipeToDismissBoxValue.EndToStart -> {
                if (note.data.has("trashed")) state.sync.delete(note.id) else trashNote(state, note)
                true
            }
            SwipeToDismissBoxValue.StartToEnd -> {
                if (!note.data.has("trashed")) state.sync.update(note.id) { it.put("pinned", !it.optBoolean("pinned")) }
                false
            }
            else -> false
        }
    })
    SwipeToDismissBox(
        state = dismiss,
        backgroundContent = {
            val toDelete = dismiss.dismissDirection == SwipeToDismissBoxValue.EndToStart
            Box(
                Modifier.fillMaxSize().background(if (toDelete) colors.red else colors.accent).padding(horizontal = 20.dp),
                contentAlignment = if (toDelete) Alignment.CenterEnd else Alignment.CenterStart,
            ) {
                GlyphIcon(if (toDelete) Glyph.Trash else Glyph.Pin, Color.White, 22.dp)
            }
        },
    ) {
        Box(Modifier.background(colors.surface)) {
            NoteRow(state, note, divider, onLongClick = onMenu) { state.push(Route.Editor(note.id)) }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun NoteRow(state: AppState, note: SyncObject, divider: Boolean, onLongClick: (() -> Unit)? = null, onClick: () -> Unit) {
    val colors = palette
    val sync = state.sync
    val image = Model.image(note)
    Column(Modifier.fillMaxWidth().background(colors.surface).combinedClickable(onClick = onClick, onLongClick = onLongClick)) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (Model.isLocked(note)) {
                        GlyphIcon(Glyph.Lock, colors.secondary, 15.dp)
                        Spacer(Modifier.width(4.dp))
                    }
                    Text(Model.title(note), style = Type.headline, color = colors.label, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false))
                    if (note.share != null) {
                        Spacer(Modifier.width(6.dp))
                        GlyphIcon(Glyph.Person, colors.secondary, 14.dp)
                    }
                }
                Row {
                    Text(Model.shortDate(Model.modified(note)), style = Type.subheadline, color = colors.label)
                    Spacer(Modifier.width(8.dp))
                    Text(Model.preview(note).ifEmpty { if (Model.isLocked(note)) "Gesperrt" else "Kein weiterer Text" },
                        style = Type.subheadline, color = colors.secondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                if (note.share != null && note.updatedBy != 0 && note.updatedBy != sync.userId) {
                    Text("Zuletzt bearbeitet von ${sync.userName(note.updatedBy)}", style = Type.footnote, color = colors.secondary)
                }
            }
            if (image != null) {
                Spacer(Modifier.width(10.dp))
                Thumbnail(sync, image, note.share, 48)
            }
        }
        if (divider) HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
    }
}

@Composable
fun Thumbnail(sync: SyncEngine, fileId: String, share: String?, size: Int) {
    val bitmap by produceState<ImageBitmap?>(null, fileId) {
        value = withContext(Dispatchers.IO) {
            try {
                val bytes = sync.fetchFile(fileId, share).readBytes()
                val options = BitmapFactory.Options().apply { inSampleSize = 4 }
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)?.asImageBitmap()
            } catch (error: Exception) {
                null
            }
        }
    }
    Box(Modifier.size(size.dp).clip(RoundedCornerShape(6.dp)).background(palette.fill)) {
        bitmap?.let { Image(it, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
    }
}

@Composable
fun MoveSheet(state: AppState, note: SyncObject, onDone: () -> Unit) {
    val sync = state.sync
    val folders = sync.all("folder").filter { it.id != note.data.optString("folder") }
        .sortedWith(compareBy({ it.share != null }, { it.data.optString("name") }))
    ActionSheet("Verschieben nach", folders.map { folder ->
        val label = folder.data.optString("name") + if (folder.share != null) " (geteilt)" else ""
        SheetAction(label) {
            when {
                folder.share != null && note.data.has("enc") -> state.toastLater("Gesperrte Notizen können nicht geteilt werden.")
                folder.share != note.share && note.owner != sync.userId -> state.toastLater("Nur wer die Notiz erstellt hat, kann sie verschieben.")
                else -> sync.launch {
                    val current = sync.get(note.id) ?: return@launch
                    val data = if (folder.share != current.share) sync.rekeyFiles(current, folder.share) else JSONObject(current.data.toString())
                    data.put("folder", folder.id)
                    sync.put("note", data, folder.share, current.id)
                    state.toastLater("Nach „${folder.data.optString("name")}“ verschoben")
                }
            }
        }
    }, onDone)
}
