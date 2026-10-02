package io.github.veritasx1.linotes.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.height
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
    var newSubfolder by remember { mutableStateOf<SyncObject?>(null) }
    var movingFolder by remember { mutableStateOf<SyncObject?>(null) }
    var keyfileHint by remember { mutableStateOf(sync.keyfileHintDue()) }
    var keyfile by remember { mutableStateOf(false) }
    var newHere by remember { mutableStateOf<Pair<SyncObject, String>?>(null) }

    val notes = remember(revision) { sync.all("note") }
    val live = notes.filter { !it.data.has("trashed") }
    val folders = remember(revision) { sync.all("folder").sortedWith(compareBy({ it.data.optDouble("order", 0.0) }, { it.data.optString("name").lowercase() })) }
    val tags = live.flatMap { Model.tags(it) }.groupingBy { it }.eachCount().toSortedMap()
    fun count(predicate: (SyncObject) -> Boolean) = live.count(predicate)

    LargeTitleScreen(
        title = "Ordner",
        actions = {
            // Like Apple's "Lock Now": shown while locked notes are open.
            if (state.vaultKey != null) BarButton(Glyph.LockOpen, "Gesperrte Notizen jetzt sperren") { state.lockAll() }
            BarButton(Glyph.Gear, "Einstellungen") { state.push(Route.Settings) }
            BarButton(Glyph.FolderPlus, "Neuer Ordner") { newFolder = true }
            BarButton(Glyph.Compose, "Neue Notiz") { newNote(state, null) }
        },
    ) {
        item(key = "search") {
            SearchField(query, { query = it }, modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp))
        }
        if (keyfileHint) item(key = "keyfile-hint") {
            // A friendly reminder after a few days of use – not at the first start (Tante Erna).
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp).clip(RoundedCornerShape(12.dp)).background(colors.surface).padding(16.dp)) {
                Text("Sichere dein Konto", style = Type.headline, color = colors.label)
                Text("Mit einer Schlüsseldatei kommst du an deine Notizen, auch wenn dein Handy einmal verloren geht.",
                    style = Type.subheadline, color = colors.secondary, modifier = Modifier.padding(top = 4.dp, bottom = 8.dp))
                Row {
                    TextButton("Jetzt sichern", bold = true) { keyfile = true }
                    TextButton("Später", color = colors.secondary) { sync.snoozeKeyfileHint(); keyfileHint = false }
                }
            }
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
        // Drag a folder onto the heading to take it to the top level.
        section("mine", header = "Meine Notizen", headerDrop = Pair({ it.startsWith("folder:") }, { dropOnFolder(state, it, null) })) {
            GroupRow("Alle Notizen", Glyph.Notes, detail = "${live.size}") { state.push(Route.NoteList("all")) }
            folderTree(sync, folders.filter { it.share == null }).forEach { (folder, depth) ->
                GroupRow(folder.data.optString("name", "Ordner"), Glyph.Folder, detail = "${count { it.data.optString("folder") == folder.id }}",
                    indent = (20 * depth).dp, dragPayload = "folder:${folder.id}",
                    modifier = Modifier.dropZone({ acceptsOnFolder(it, folder.id) }) { dropOnFolder(state, it, folder.id) },
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
            val sharedTree = folderTree(sync, shared)
            sharedTree.forEachIndexed { index, (folder, depth) ->
                GroupRow(folder.data.optString("name", "Ordner"), if (depth == 0) Glyph.FolderShared else Glyph.Folder,
                    detail = "${count { it.data.optString("folder") == folder.id }}", indent = (20 * depth).dp,
                    dragPayload = "folder:${folder.id}",
                    modifier = Modifier.dropZone({ acceptsOnFolder(it, folder.id) }) { dropOnFolder(state, it, folder.id) },
                    divider = index < sharedTree.lastIndex, onLongClick = { folderMenu = folder }) {
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
    newSubfolder?.let { parent -> CreateInFolder(state, parent, "folder") { newSubfolder = null } }
    movingFolder?.let { folder -> MoveToFolderSheet(state, folder) { movingFolder = null } }
    if (keyfile) KeyfileDialog(state) { keyfile = false; keyfileHint = sync.keyfileHintDue() }
    newHere?.let { (folder, kind) -> CreateInFolder(state, folder, kind) { newHere = null } }
    folderMenu?.let { folder ->
        val protected = folder.id == Model.privateFolder(sync.userId)
        ActionSheet(folder.data.optString("name"), buildList {
            add(SheetAction("Umbenennen") { rename = folder })
            add(SheetAction("Teilen …") { state.push(Route.Share(folder.id)) })
            add(SheetAction("Neuer Unterordner …") { newSubfolder = folder })
            add(SheetAction("Neue Liste hier …") { newHere = folder to "list" })
            add(SheetAction("Neues Board hier …") { newHere = folder to "board" })
            add(SheetAction("Verschieben nach …") { movingFolder = folder })
            if (!protected) add(SheetAction("Ordner löschen", destructive = true) {
                // The folder, its subfolders and all their notes (notes go to "Zuletzt gelöscht").
                val doomed = folderDescendants(sync, folder.id) + folder.id
                for (note in sync.all("note")) if (note.data.optString("folder") in doomed) sync.update(note.id) { it.put("trashed", Model.now()) }
                (doomed - folder.id).forEach { sync.delete(it) }
                // Lists and boards have no trash: they stay, just without a folder.
                for (item in sync.all("list") + sync.all("board")) if (item.data.optString("folder") in doomed) sync.update(item.id) { it.remove("folder") }
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
    val folderId = key.removePrefix("folder:").takeIf { key.startsWith("folder:") }
    val folderLists = remember(revision, key) { if (folderId == null) emptyList() else sync.all("list").filter { it.data.optString("folder") == folderId }.sortedBy { it.data.optString("name").lowercase() } }
    val folderBoards = remember(revision, key) { if (folderId == null) emptyList() else sync.all("board").filter { it.data.optString("folder") == folderId }.sortedBy { it.data.optString("name").lowercase() } }
    val subfolders = remember(revision, key) {
        if (!key.startsWith("folder:")) emptyList()
        else sync.all("folder").filter { folderParent(sync, it) == key.removePrefix("folder:") }
            .sortedWith(compareBy({ it.data.optDouble("order", 0.0) }, { it.data.optString("name").lowercase() }))
    }
    var query by remember { mutableStateOf("") }
    var menu by remember { mutableStateOf<SyncObject?>(null) }
    var createMenu by remember { mutableStateOf(false) }
    var creating by remember { mutableStateOf<String?>(null) }
    var moving by remember { mutableStateOf<SyncObject?>(null) }
    var locking by remember { mutableStateOf<Pair<SyncObject, Boolean>?>(null) }

    val shown = notes.filter { query.isBlank() || Model.text(it).contains(query, true) }
    var sortMenu by remember { mutableStateOf(false) }
    var gallery by remember { mutableStateOf(sync.noteGallery) }
    val sorted = Model.sortNotes(shown, sync.noteSort(), pinnedFirst = key != "trash")
    val groups = sorted.groupBy { it.group }

    LargeTitleScreen(
        title = title,
        backLabel = "Ordner",
        onBack = { state.pop() },
        subtitle = if (notes.size == 1) "1 Notiz" else "${notes.size} Notizen",
        actions = {
            if (state.vaultKey != null) BarButton(Glyph.LockOpen, "Gesperrte Notizen jetzt sperren") { state.lockAll() }
            // Inside a folder: create a subfolder, list or board here – the folder as a project's filing place.
            if (folderId != null) BarButton(Glyph.FolderPlus, "Neu in diesem Ordner") { createMenu = true }
            BarButton(Glyph.More, "Ansicht und Sortierung") { sortMenu = true }
            if (key != "trash") BarButton(Glyph.Compose, "Neue Notiz") { newNote(state, key.takeIf { it.startsWith("folder:") }) }
        },
    ) {
        item(key = "search") { SearchField(query, { query = it }, modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) }
        if (subfolders.isNotEmpty() && query.isBlank()) section("subfolders", header = "Ordner") {
            subfolders.forEachIndexed { index, folder ->
                GroupRow(folder.data.optString("name", "Ordner"), Glyph.Folder,
                    detail = "${sync.all("note").count { it.data.optString("folder") == folder.id && !it.data.has("trashed") }}",
                    dragPayload = "folder:${folder.id}",
                    modifier = Modifier.dropZone({ acceptsOnFolder(it, folder.id) }) { dropOnFolder(state, it, folder.id) },
                    divider = index < subfolders.lastIndex) { state.push(Route.NoteList("folder:${folder.id}")) }
            }
        }
        if (folderLists.isNotEmpty() && query.isBlank()) section("folder-lists", header = "Listen") {
            folderLists.forEachIndexed { index, list ->
                GroupRow(list.data.optString("name", "Liste"), Glyph.Cart, tint = listColor(list),
                    detail = "${sync.all("item").count { it.data.optString("list") == list.id && !it.data.optBoolean("done") }}",
                    dragPayload = "list:${list.id}", divider = index < folderLists.lastIndex) { state.push(Route.ListDetail(list.id)) }
            }
        }
        if (folderBoards.isNotEmpty() && query.isBlank()) section("folder-boards", header = "Boards") {
            folderBoards.forEachIndexed { index, board ->
                GroupRow(board.data.optString("name", "Board"), Glyph.Board,
                    detail = "${sync.all("card").count { it.data.optString("board") == board.id && !it.data.optBoolean("archived") }}",
                    dragPayload = "board:${board.id}", divider = index < folderBoards.lastIndex) { state.push(Route.Board(board.id)) }
            }
        }
        val folderHasMore = subfolders.isNotEmpty() || folderLists.isNotEmpty() || folderBoards.isNotEmpty()
        if (shown.isEmpty() && (!folderHasMore || query.isNotBlank())) item(key = "empty") { EmptyState(if (query.isBlank()) "Keine Notizen" else "Keine Treffer") }
        if (gallery) groups.forEach { (group, items) ->
            item(key = "gallery-$group") {
                GalleryGroup(state, group.ifEmpty { null }, items) { menu = it }
            }
        } else groups.forEach { (group, items) ->
            section("group-$group", header = group.ifEmpty { null }) {
                items.forEachIndexed { index, item ->
                    SwipeNoteRow(state, item.note, index < items.lastIndex, key, stamp = item.stamp, onMenu = { menu = item.note })
                }
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
    // Like Apple: "View as Gallery / List" and the sort order in one menu.
    if (sortMenu) ActionSheet(null, listOf(
        SheetAction(if (gallery) "Als Liste anzeigen" else "Als Galerie anzeigen") { gallery = !gallery; sync.noteGallery = gallery },
    ) + Model.NOTE_SORTS.map { (order, label) ->
        SheetAction("Sortieren nach $label" + if (order == sync.noteSort()) " ✓" else "") { sync.setNoteSort(order) }
    }) { sortMenu = false }
    if (createMenu) ActionSheet("Neu in diesem Ordner", listOf(
        SheetAction("Neuer Unterordner") { creating = "folder" },
        SheetAction("Neue Liste") { creating = "list" },
        SheetAction("Neues Board") { creating = "board" },
    )) { createMenu = false }
    creating?.let { kind -> sync.get(folderId ?: "")?.let { folder -> CreateInFolder(state, folder, kind) { creating = null } } }
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
fun SwipeNoteRow(state: AppState, note: SyncObject, divider: Boolean, key: String, stamp: Double? = null, onMenu: () -> Unit) {
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
            NoteRow(state, note, divider, stamp = stamp, onLongClick = onMenu) { state.push(Route.Editor(note.id)) }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun NoteRow(state: AppState, note: SyncObject, divider: Boolean, stamp: Double? = null, onLongClick: (() -> Unit)? = null, onClick: () -> Unit) {
    val colors = palette
    val sync = state.sync
    val image = Model.image(note)
    // Hold and move to drag the note onto a folder; hold and release for the menu.
    Column(Modifier.fillMaxWidth().background(colors.surface).combinedClickable(onClick = onClick).holdToDrag("note:${note.id}", onLongClick)) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (sync.unread(note)) {
                        // Changed by someone else since I looked (like Apple's blue dot).
                        Box(Modifier.size(8.dp).background(colors.accent, androidx.compose.foundation.shape.CircleShape))
                        Spacer(Modifier.width(6.dp))
                    }
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
                    Text(Model.shortDate(stamp ?: Model.modified(note)), style = Type.subheadline, color = colors.label)
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

/** One date group of the gallery: two cards per row (photo or the start of the text, title, date). */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun GalleryGroup(state: AppState, header: String?, items: List<Model.Sorted>, onMenu: (SyncObject) -> Unit) {
    val colors = palette
    Column(Modifier.padding(horizontal = 16.dp).padding(top = if (header != null) 18.dp else 10.dp)) {
        if (header != null) Text(header, style = Type.title3.copy(fontWeight = FontWeight.Bold), color = colors.label,
            modifier = Modifier.padding(start = 4.dp, bottom = 8.dp))
        for (row in items.chunked(2)) {
            Row(Modifier.fillMaxWidth().padding(bottom = 14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                for (item in row) {
                    val note = item.note
                    Column(Modifier.weight(1f).combinedClickable(onLongClick = { onMenu(note) }) { state.push(Route.Editor(note.id)) },
                        horizontalAlignment = Alignment.CenterHorizontally) {
                        val image = Model.image(note)
                        Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(10.dp)).background(colors.surface)
                            .border(0.5.dp, colors.separator, RoundedCornerShape(10.dp))) {
                            when {
                                image != null -> Thumbnail(state.sync, image, note.share, 0, Modifier.fillMaxSize())
                                Model.isLocked(note) -> GlyphIcon(Glyph.Lock, colors.secondary, 28.dp, Modifier.align(Alignment.Center))
                                else -> Text(Model.preview(note).take(160), style = Type.footnote, color = colors.secondary,
                                    overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(10.dp))
                            }
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(Model.title(note), style = Type.subheadline.copy(fontWeight = FontWeight.SemiBold), color = colors.label,
                            maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(Model.shortDate(item.stamp), style = Type.footnote, color = colors.secondary)
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
fun Thumbnail(sync: SyncEngine, fileId: String, share: String?, size: Int, modifier: Modifier = Modifier.size(size.dp)) {
    val bitmap by produceState<ImageBitmap?>(null, fileId) {
        value = withContext(Dispatchers.IO) {
            try {
                val bytes = sync.fetchFile(fileId, share).readBytes()
                RichEditor.decodeImage(bytes, maxSize = 480)?.asImageBitmap()
                    .also { if (it == null) android.util.Log.w("LiNotes", "Vorschaubild nicht lesbar: $fileId (${bytes.size} Bytes)") }
            } catch (error: Exception) {
                android.util.Log.w("LiNotes", "Vorschaubild nicht geladen: $fileId", error)
                null
            }
        }
    }
    Box(modifier.clip(RoundedCornerShape(6.dp)).background(palette.fill)) {
        bitmap?.let { Image(it, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
    }
}

@Composable
fun MoveSheet(state: AppState, note: SyncObject, onDone: () -> Unit) {
    val sync = state.sync
    val folders = sync.all("folder").filter { it.id != note.data.optString("folder") }
        .sortedWith(compareBy({ it.share != null }, { folderPath(sync, it).lowercase() }))
    ActionSheet("Verschieben nach", folders.map { folder ->
        val label = folderPath(sync, folder) + if (folder.share != null) " (geteilt)" else ""
        SheetAction(label) { moveNoteTo(state, note.id, folder.id) }
    }, onDone)
}
