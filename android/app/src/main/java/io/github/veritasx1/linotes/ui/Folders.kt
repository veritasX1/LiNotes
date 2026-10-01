package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject

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
    val targets = sync.all("folder").filter { it.id !in blocked && it.share == obj.share && it.id != current }
        .sortedBy { folderPath(sync, it).lowercase() }
    val field = if (isFolder) "parent" else "folder"
    ActionSheet("„${obj.data.optString("name")}“ verschieben nach", buildList {
        if (current != null) add(SheetAction(if (isFolder) "Oberste Ebene" else "Kein Ordner") { sync.update(obj.id) { it.remove(field) } })
        targets.forEach { target -> add(SheetAction(folderPath(sync, target)) { sync.update(obj.id) { it.put(field, target.id) } }) }
    }, onDone)
}

/** Lists or boards grouped by folder: (folder or null, items), unfiled first. */
fun groupByFolder(sync: SyncEngine, objects: List<SyncObject>): List<Pair<SyncObject?, List<SyncObject>>> {
    val byFolder = objects.groupBy { obj -> obj.data.optString("folder").let { id -> sync.get(id)?.takeIf { it.kind == "folder" } } }
    return byFolder.entries.sortedWith(compareBy({ it.key != null }, { it.key?.let { folder -> folderPath(sync, folder).lowercase() } ?: "" }))
        .map { it.key to it.value }
}
