package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject
import org.json.JSONObject

// Folder tree – same rules as linux/linotes/model.py (folder_parent, folder_tree, …).

/** Parent folder id, or null at the top (also when the parent is gone). */
fun folderParent(sync: SyncEngine, folder: SyncObject): String? {
    val parent = folder.data.optString("parent").takeIf { it.isNotEmpty() && it != "null" && it != folder.id }
    return parent?.takeIf { sync.get(it) != null }
}

private val folderOrder = compareBy<SyncObject>({ it.data.optDouble("order", 0.0) }, { it.data.optString("name").lowercase() })

/** Folders depth-first with their depth. A folder whose parent is not among `folders` starts its own tree. */
fun folderTree(sync: SyncEngine, folders: List<SyncObject>): List<Pair<SyncObject, Int>> {
    val ids = folders.map { it.id }.toSet()
    val children = folders.groupBy { folderParent(sync, it)?.takeIf { parent -> parent in ids } }
    val result = mutableListOf<Pair<SyncObject, Int>>()
    val seen = mutableSetOf<String>()
    fun walk(parent: String?, depth: Int) {
        for (folder in children[parent].orEmpty().sortedWith(folderOrder)) {
            if (!seen.add(folder.id)) continue
            result.add(folder to depth)
            walk(folder.id, depth + 1)
        }
    }
    walk(null, 0)
    return result
}

/** Ids of all folders below `folderId` (not including it). */
fun folderDescendants(sync: SyncEngine, folderId: String): Set<String> {
    val folders = sync.all("folder")
    val found = mutableSetOf<String>()
    val todo = ArrayDeque(listOf(folderId))
    while (todo.isNotEmpty()) {
        val current = todo.removeFirst()
        for (folder in folders) {
            if (folder.data.optString("parent") == current && folder.id != folderId && found.add(folder.id)) todo.add(folder.id)
        }
    }
    return found
}

/** "Projekte › LiNotes › Entwicklung" – for move menus. */
fun folderPath(sync: SyncEngine, folder: SyncObject): String {
    val names = mutableListOf<String>()
    var current: SyncObject? = folder
    var guard = 0
    while (current != null && guard++ < 32) {
        names.add(current.data.optString("name", "Ordner"))
        current = folderParent(sync, current)?.let { sync.get(it) }
    }
    return names.reversed().joinToString(" › ")
}

/** "Verschieben nach …" for folders, lists and boards – within the same space (private or one share). */
@androidx.compose.runtime.Composable
fun MoveToFolderSheet(state: AppState, obj: SyncObject, onDone: () -> Unit) {
    val sync = state.sync
    val isFolder = obj.kind == "folder"
    val blocked = if (isFolder) folderDescendants(sync, obj.id) + obj.id else emptySet()
    val current = if (isFolder) folderParent(sync, obj) else obj.data.optString("folder").takeIf { it.isNotEmpty() && it != "null" }
    val targets = sync.all("folder").filter { it.id !in blocked && it.id != current }
        .sortedWith(compareBy({ it.share != null }, { folderPath(sync, it).lowercase() }))
    fun move(target: SyncObject?) = moveObjectTo(state, obj.id, target?.id)
    ActionSheet("„${obj.data.optString("name")}“ verschieben nach", buildList {
        if (current != null) add(SheetAction(if (isFolder) "Oberste Ebene" else "Kein Ordner") { move(null) })
        targets.forEach { target -> add(SheetAction(folderPath(sync, target) + if (target.share != null) " (geteilt)" else "") { move(target) }) }
    }, onDone)
}

/** Lists or boards grouped by folder: (folder or null, items), unfiled first. */
fun groupByFolder(sync: SyncEngine, objects: List<SyncObject>): List<Pair<SyncObject?, List<SyncObject>>> {
    val byFolder = objects.groupBy { obj -> obj.data.optString("folder").let { id -> sync.get(id)?.takeIf { it.kind == "folder" } } }
    return byFolder.entries.sortedWith(compareBy({ it.key != null }, { it.key?.let { folder -> folderPath(sync, folder).lowercase() } ?: "" }))
        .map { it.key to it.value }
}

/** Move a note into a folder – from "Verschieben nach …" or by drag and drop. */
fun moveNoteTo(state: AppState, noteId: String, folderId: String) {
    val sync = state.sync
    val note = sync.get(noteId) ?: return
    val folder = sync.get(folderId)?.takeIf { it.kind == "folder" } ?: return
    if (note.data.optString("folder") == folderId) return
    when {
        folder.share != null && note.data.has("enc") -> state.toastLater("Gesperrte Notizen können nicht geteilt werden.")
        folder.share != note.share && note.owner != sync.userId -> state.toastLater("Nur wer die Notiz erstellt hat, kann sie verschieben.")
        else -> sync.launch {
            val current = sync.get(noteId) ?: return@launch
            val data = if (folder.share != current.share) sync.rekeyFiles(current, folder.share) else JSONObject(current.data.toString())
            data.put("folder", folder.id)
            sync.put("note", data, folder.share, current.id)
            state.toastLater("Nach „${folder.data.optString("name")}“ verschoben")
        }
    }
}

/** Move a folder, list or board into a folder (null = top / no folder) – menu or drag and drop. */
fun moveObjectTo(state: AppState, objectId: String, folderId: String?) {
    val sync = state.sync
    val obj = sync.get(objectId) ?: return
    if (obj.kind == "folder" && folderId != null && folderId in folderDescendants(sync, objectId) + objectId) {
        state.toastLater("Ein Ordner kann nicht in sich selbst liegen.")
        return
    }
    val field = if (obj.kind == "folder") "parent" else "folder"
    if (obj.data.optString(field).takeIf { it.isNotEmpty() && it != "null" } == folderId) return
    if (sync.shareAfterMove(obj, folderId) != obj.share && obj.owner != sync.userId) {
        state.toastLater("Nur wer es erstellt hat, kann es in einen anderen Bereich verschieben.")
        return
    }
    // Into or out of a shared folder everything inside is re-encrypted – runs in the background.
    sync.launch {
        sync.moveToFolder(objectId, folderId)
        state.toastLater("Verschoben")
    }
}

/** Something dropped onto a folder (folderId) or onto "out of any folder" (null). */
fun dropOnFolder(state: AppState, payload: String, folderId: String?) {
    val (kind, id) = payload.split(":", limit = 2).let { it[0] to it.getOrElse(1) { "" } }
    when {
        kind == "note" && folderId != null -> moveNoteTo(state, id, folderId)
        kind in setOf("folder", "list", "board", "plan") -> moveObjectTo(state, id, folderId)
    }
}

fun acceptsOnFolder(payload: String, folderId: String) =
    payload.substringBefore(":") in setOf("note", "folder", "list", "board", "plan") && payload != "folder:$folderId"

/** "Neu in diesem Ordner": subfolder, list or board – a folder as a project's filing place.
 *  Everything new lives where the folder lives (private or in its share). */
@androidx.compose.runtime.Composable
fun CreateInFolder(state: AppState, folder: SyncObject, kind: String, onDone: () -> Unit) {
    val sync = state.sync
    val (title, hint) = when (kind) {
        "folder" -> "Neuer Unterordner" to "Name"
        "list" -> "Neue Liste" to "z. B. Drogerie"
        else -> "Neues Board" to "z. B. Haushalt"
    }
    AlertDialog(title, "In „${folder.data.optString("name")}“.", "Erstellen", fields = listOf(AlertField(hint)), onDismiss = onDone) { values ->
        val name = values[0].trim()
        if (name.isNotEmpty()) {
            val data = JSONObject().put("name", name).put("order", io.github.veritasx1.linotes.data.Model.now())
            when (kind) {
                "folder" -> sync.put("folder", data.put("parent", folder.id), folder.share)
                "list" -> state.push(Route.ListDetail(sync.put("list", data.put("folder", folder.id).put("grocery", true), folder.share).id))
                else -> {
                    val board = sync.put("board", data.put("folder", folder.id), folder.share)
                    io.github.veritasx1.linotes.data.Model.defaultColumns.forEachIndexed { order, (_, column) ->
                        sync.put("column", JSONObject().put("board", board.id).put("name", column).put("order", order), folder.share)
                    }
                    state.push(Route.Board(board.id))
                }
            }
        }
        onDone()
    }
}
