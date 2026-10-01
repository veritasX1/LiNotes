package io.github.veritasx1.linotes.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncObject
import org.json.JSONObject

// The first entry is the default for lists without a color: the app's accent yellow.
val LIST_COLORS = listOf(
    "gelb" to Color(0xFFE6A200), "orange" to Color(0xFFFF9500), "rot" to Color(0xFFFF3B30),
    "grün" to Color(0xFF34C759), "blau" to Color(0xFF007AFF), "lila" to Color(0xFFAF52DE),
)

fun listColor(obj: SyncObject): Color = LIST_COLORS.firstOrNull { it.first == obj.data.optString("color") }?.second ?: LIST_COLORS[0].second

@Composable
fun ListsScreen(state: AppState, revision: Long) {
    val sync = state.sync
    val lists = remember(revision) { sync.all("list").sortedWith(compareBy({ it.data.optDouble("order", 0.0) }, { it.data.optString("name") })) }
    val items = remember(revision) { sync.all("item") }
    var creating by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf<SyncObject?>(null) }
    var renaming by remember { mutableStateOf<SyncObject?>(null) }
    var moving by remember { mutableStateOf<SyncObject?>(null) }

    LargeTitleScreen(
        title = "Listen",
        actions = { BarButton(Glyph.Plus, "Neue Liste") { creating = true } },
    ) {
        if (lists.isEmpty()) item { EmptyState("Keine Listen", glyph = Glyph.Cart) }
        // Grouped by folder: unfiled lists first ("Meine Listen"), then one section per folder.
        for ((folder, group) in groupByFolder(sync, lists)) section("lists-${folder?.id}", header = folder?.let { folderPath(sync, it) } ?: "Meine Listen") {
            group.forEachIndexed { index, list ->
                val open = items.count { it.data.optString("list") == list.id && !it.data.optBoolean("done") }
                GroupRow(
                    title = list.data.optString("name", "Liste"),
                    subtitle = shareLabel(sync, list),
                    detail = "$open",
                    divider = index < group.lastIndex,
                    onLongClick = { menu = list },
                    glyph = Glyph.Cart,
                    tint = listColor(list),
                ) { state.push(Route.ListDetail(list.id)) }
            }
        }
    }

    if (creating) {
        AlertDialog("Neue Liste", confirm = "Erstellen", fields = listOf(AlertField("z. B. Drogerie")), onDismiss = { creating = false }) { values ->
            if (values[0].isNotBlank()) {
                val list = sync.put("list", JSONObject().put("name", values[0].trim()).put("grocery", true).put("order", Model.now()))
                state.push(Route.ListDetail(list.id))
            }
            creating = false
        }
    }
    menu?.let { list -> ListMenu(state, list, onRename = { renaming = list }, onMove = { moving = list }) { menu = null } }
    moving?.let { list -> MoveToFolderSheet(state, list) { moving = null } }
    renaming?.let { list ->
        AlertDialog("Liste umbenennen", confirm = "Sichern", fields = listOf(AlertField("Name", list.data.optString("name"))),
            onDismiss = { renaming = null }) { values ->
            if (values[0].isNotBlank()) sync.update(list.id) { it.put("name", values[0].trim()) }
            renaming = null
        }
    }
}

@Composable
private fun ListMenu(state: AppState, list: SyncObject, onRename: () -> Unit, onMove: () -> Unit, onDone: () -> Unit) {
    val sync = state.sync
    ActionSheet(list.data.optString("name"), listOf(
        SheetAction("Umbenennen") { onRename() },
        SheetAction("Verschieben nach …") { onMove() },
        SheetAction("Teilen …") { state.push(Route.Share(list.id)) },
        SheetAction(if (list.data.optBoolean("grocery")) "Warengruppen ausschalten" else "Nach Warengruppen sortieren") {
            sync.update(list.id) { it.put("grocery", !it.optBoolean("grocery")) }
        },
        SheetAction("Liste löschen", destructive = true) {
            for (item in sync.all("item")) if (item.data.optString("list") == list.id) sync.delete(item.id)
            sync.delete(list.id)
            state.pop()
        },
    ), onDone)
}

@Composable
fun ListDetailScreen(state: AppState, listId: String, revision: Long) {
    val colors = palette
    val sync = state.sync
    val list = remember(revision, listId) { sync.get(listId) } ?: return
    val items = remember(revision, listId) { sync.all("item").filter { it.data.optString("list") == listId } }
    var showDone by remember { mutableStateOf(true) }
    var menu by remember { mutableStateOf(false) }
    var renaming by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf("") }
    val focus = remember { FocusRequester() }
    val accent = listColor(list)

    val open = items.filter { !it.data.optBoolean("done") }.sortedBy { it.data.optDouble("order", it.updated) }
    val done = items.filter { it.data.optBoolean("done") }.sortedByDescending { it.updated }

    fun add() {
        val text = draft
        draft = ""
        val base = Model.now()
        text.lines().map { it.trim(' ', '-', '•', '\t') }.filter { it.isNotEmpty() }.forEachIndexed { index, line ->
            sync.put("item", JSONObject().put("list", listId).put("text", line).put("done", false)
                .put("order", base + index * 0.001).put("by", sync.userId), list.share)
        }
    }

    Column(Modifier.fillMaxSize().background(colors.background).imePadding()) {
        Box(Modifier.weight(1f)) {
            LargeTitleScreen(
                title = list.data.optString("name", "Liste"),
                subtitle = "${open.size} offen · " + shareLabel(sync, list),
                backLabel = "Listen",
                onBack = { state.pop() },
                actions = { BarButton(Glyph.More, "Mehr") { menu = true } },
            ) {
                if (items.isEmpty()) item { EmptyState("Die Liste ist leer", "Tippe unten einen Eintrag ein.", Glyph.Cart) }
                if (list.data.optBoolean("grocery")) {
                    val grouped = open.groupBy { it.data.optString("category").ifEmpty { Model.groceryCategory(it.data.optString("text")) } }
                    for (category in Model.categoryOrder) {
                        val group = grouped[category] ?: continue
                        section("cat-$category", header = category) {
                            group.forEachIndexed { index, item -> ItemRow(state, item, accent, index < group.lastIndex) }
                        }
                    }
                } else if (open.isNotEmpty()) {
                    section("open") { open.forEachIndexed { index, item -> ItemRow(state, item, accent, index < open.lastIndex) } }
                }
                if (done.isNotEmpty() && showDone) {
                    section("done", header = "Erledigt (${done.size})") {
                        done.forEachIndexed { index, item -> ItemRow(state, item, accent, index < done.lastIndex) }
                    }
                }
            }
        }
        // Entry field at the bottom, like "Neue Erinnerung" in Reminders.
        Column(Modifier.fillMaxWidth().background(colors.bar)) {
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().navigationBarsPadding().heightIn(min = 52.dp).padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(24.dp).clip(CircleShape).background(accent), contentAlignment = Alignment.Center) {
                    GlyphIcon(Glyph.Plus, Color.White, 12.dp)
                }
                Spacer(Modifier.width(12.dp))
                Box(Modifier.weight(1f)) {
                    if (draft.isEmpty()) Text("Neuer Eintrag", style = Type.body, color = colors.secondary)
                    BasicTextField(draft, { draft = it }, singleLine = true, textStyle = Type.body.copy(color = colors.label),
                        cursorBrush = SolidColor(accent),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { add() }),
                        modifier = Modifier.fillMaxWidth().focusRequester(focus))
                }
                if (draft.isNotBlank()) TextButton("Hinzufügen", color = accent) { add() }
            }
        }
    }

    if (menu) {
        ActionSheet(list.data.optString("name"), listOf(
            SheetAction(if (showDone) "Erledigte ausblenden" else "Erledigte einblenden") { showDone = !showDone },
            SheetAction("Erledigte löschen", destructive = true) { done.forEach { sync.delete(it.id) } },
            SheetAction(if (list.data.optBoolean("grocery")) "Warengruppen ausschalten" else "Nach Warengruppen sortieren") {
                sync.update(list.id) { it.put("grocery", !it.optBoolean("grocery")) }
            },
            SheetAction("Farbe ändern") {
                val index = LIST_COLORS.indexOfFirst { it.first == list.data.optString("color") }
                sync.update(list.id) { it.put("color", LIST_COLORS[(index + 1).mod(LIST_COLORS.size)].first) }
            },
            SheetAction("Teilen …") { state.push(Route.Share(list.id)) },
            SheetAction("Umbenennen") { renaming = true },
        )) { menu = false }
    }
    if (renaming) {
        AlertDialog("Liste umbenennen", confirm = "Sichern", fields = listOf(AlertField("Name", list.data.optString("name"))),
            onDismiss = { renaming = false }) { values ->
            if (values[0].isNotBlank()) sync.update(list.id) { it.put("name", values[0].trim()) }
            renaming = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ItemRow(state: AppState, item: SyncObject, accent: Color, divider: Boolean) {
    val colors = palette
    val sync = state.sync
    val doneFlag = item.data.optBoolean("done")
    var editing by remember(item.id) { mutableStateOf(false) }
    var text by remember(item.id, item.data.optString("text")) { mutableStateOf(item.data.optString("text")) }
    val dismiss = rememberSwipeToDismissBoxState(confirmValueChange = {
        if (it == SwipeToDismissBoxValue.EndToStart) { sync.delete(item.id); true } else false
    })
    SwipeToDismissBox(dismiss, enableDismissFromStartToEnd = false, backgroundContent = {
        Box(Modifier.fillMaxSize().background(colors.red).padding(horizontal = 20.dp), contentAlignment = Alignment.CenterEnd) {
            GlyphIcon(Glyph.Trash, Color.White, 22.dp)
        }
    }) {
        Column(Modifier.background(colors.surface)) {
            Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(start = 14.dp, end = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                CheckCircleIcon(doneFlag, accent, colors.tertiary, 26.dp, Modifier.clip(CircleShape).clickable {
                    sync.update(item.id) { data -> data.put("done", !doneFlag); if (!doneFlag) data.put("done_by", sync.userId) else data.remove("done_by") }
                })
                Spacer(Modifier.width(12.dp))
                if (editing) {
                    val focus = remember { FocusRequester() }
                    BasicTextField(text, { text = it }, singleLine = true, textStyle = Type.body.copy(color = colors.label),
                        cursorBrush = SolidColor(accent),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = {
                            editing = false
                            if (text.isBlank()) sync.delete(item.id)
                            else if (text != item.data.optString("text")) sync.update(item.id) { it.put("text", text.trim()); it.remove("category") }
                        }),
                        modifier = Modifier.weight(1f).focusRequester(focus))
                    androidx.compose.runtime.LaunchedEffect(Unit) { focus.requestFocus() }
                } else {
                    Text(item.data.optString("text"), style = Type.body,
                        color = if (doneFlag) colors.secondary else colors.label,
                        textDecoration = if (doneFlag) TextDecoration.None else null,
                        modifier = Modifier.weight(1f).clickable { editing = true }.padding(vertical = 12.dp))
                }
                val by = item.data.optInt("by")
                if (by != 0 && by != sync.userId && item.share != null) {
                    Text(sync.userName(by).take(1), style = Type.caption, color = colors.label,
                        modifier = Modifier.clip(CircleShape).background(accent.copy(alpha = 0.25f)).padding(horizontal = 7.dp, vertical = 2.dp))
                }
            }
            if (divider) HorizontalDivider(Modifier.padding(start = 52.dp), 0.5.dp, colors.separator)
        }
    }
}
