package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.unit.dp
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject

/** At the end of the lists, boards or plans: "Archiv" with its number, folded away until tapped
 *  (like the completed reminders in Apple's Reminders). */
fun LazyListScope.archiveSection(key: String, items: List<SyncObject>, open: Boolean, onToggle: () -> Unit,
                                 row: @Composable (SyncObject, Boolean) -> Unit) {
    if (items.isEmpty()) return
    section("archive-$key", header = null) {
        GroupRow(tr("Archiv"), Glyph.Archive, detail = "${items.size}", chevron = false, divider = open,
            trailing = { GlyphIcon(Glyph.Chevron, palette.tertiary, 14.dp, Modifier.rotate(if (open) 90f else 0f)) }) { onToggle() }
        if (open) items.forEachIndexed { index, item -> row(item, index < items.lastIndex) }
    }
}

/** "Archivieren" / "Aus dem Archiv holen" for a long-press menu. */
fun archiveAction(state: AppState, obj: SyncObject): SheetAction {
    val archived = Model.archived(obj)
    return SheetAction(if (archived) tr("Aus dem Archiv holen") else tr("Archivieren")) {
        Model.setArchived(state.sync, obj.id, !archived)
        state.toastLater(if (archived) tr("Aus dem Archiv geholt") else tr("Ins Archiv verschoben"))
    }
}

fun SyncEngine.unarchived(kind: String) = all(kind).filter { !Model.archived(it) }
