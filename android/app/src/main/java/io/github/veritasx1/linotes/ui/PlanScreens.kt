package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

import android.graphics.Color as AColor
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.Plans
import io.github.veritasx1.linotes.data.SyncObject
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import java.time.temporal.IsoFields

private fun planColor(name: String?, alpha: Float = 1f): Color =
    Color(Plans.COLORS[name] ?: Plans.COLORS.getValue("grey")).copy(alpha = alpha)

private fun german(date: LocalDate) = "%02d.%02d.%d".format(date.dayOfMonth, date.monthValue, date.year)

private fun parseGerman(text: String): LocalDate? = try {
    val (d, m, y) = text.trim().split(".").map { it.trim().toInt() }
    LocalDate.of(if (y < 100) 2000 + y else y, m, d)
} catch (error: Exception) { null }

// ================================================================
// LIST OF PLANS (tab "Pläne")
// ================================================================

@Composable
fun PlansScreen(state: AppState, revision: Long) {
    val sync = state.sync
    val context = LocalContext.current
    val everything = remember(revision) { sync.all("plan").sortedWith(compareBy({ it.data.optDouble("order", 0.0) }, { it.data.optString("name") })) }
    val plans = everything.filter { !io.github.veritasx1.linotes.data.Model.archived(it) }
    val archivedPlans = everything.filter { io.github.veritasx1.linotes.data.Model.archived(it) }
    var archiveOpen by remember { mutableStateOf(false) }
    var naming by remember { mutableStateOf<String?>(null) }   // template key
    var choosing by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf<SyncObject?>(null) }
    var renaming by remember { mutableStateOf<SyncObject?>(null) }
    var moving by remember { mutableStateOf<SyncObject?>(null) }

    LargeTitleScreen(title = tr("Pläne"), actions = { BarButton(Glyph.Plus, tr("Neuer Plan")) { choosing = true } }) {
        if (plans.isEmpty()) item { EmptyState(tr("Keine Pläne"), tr("Stundenplan, Schichtplan, Putzplan, Raumplan oder Projektplan – mit + anlegen."), glyph = Glyph.Table) }
        for ((folder, group) in groupByFolder(sync, plans)) section("plans-${folder?.id}", header = folder?.let { folderPath(sync, it) } ?: tr("Pläne"),
            headerDrop = Pair({ it.startsWith("plan:") }, { dropOnFolder(state, it, folder?.id) })) {
            group.forEachIndexed { index, plan ->
                GroupRow(plan.data.optString("name").ifEmpty { tr("Plan") }, Glyph.Table,
                    subtitle = (if (Plans.isTimeline(plan.data)) tr("Zeitstrahl") else tr("Raster")) + " · " + shareLabel(sync, plan),
                    divider = index < group.lastIndex, dragPayload = "plan:${plan.id}", onLongClick = { menu = plan }) { state.push(Route.Plan(plan.id)) }
            }
        }
        archiveSection("plans", archivedPlans, archiveOpen, { archiveOpen = !archiveOpen }) { plan, divider ->
            GroupRow(plan.data.optString("name").ifEmpty { tr("Plan") }, Glyph.Table, subtitle = shareLabel(sync, plan), divider = divider,
                onLongClick = { menu = plan }) { state.push(Route.Plan(plan.id)) }
        }
    }
    if (choosing) {
        ActionSheet(tr("Neuer Plan – Vorlage"), Plans.TEMPLATES.map { (key, title, _) -> SheetAction(title) { naming = key } }) { choosing = false }
    }
    naming?.let { key ->
        val title = Plans.TEMPLATES.first { it.first == key }.second
        AlertDialog(tr("Neuer Plan"), "$title: " + Plans.TEMPLATES.first { it.first == key }.third, confirm = tr("Erstellen"), fields = listOf(AlertField(tr("Name"), if (key == "leer") "" else title)),
            onDismiss = { naming = null }) { values ->
            val name = values[0].trim().ifEmpty { title }
            val plan = sync.put("plan", Plans.template(key).put("name", name).put("order", Model.now()))
            naming = null
            state.push(Route.Plan(plan.id))
        }
    }
    menu?.let { plan ->
        ActionSheet(plan.data.optString("name"), listOf(
            SheetAction(tr("Umbenennen")) { renaming = plan },
            SheetAction(tr("Verschieben nach …")) { moving = plan },
            SheetAction(tr("Teilen …")) { state.push(Route.Share(plan.id)) },
            SheetAction(tr("Als PDF teilen …")) { PlanPdf.share(state, context, plan) },
            archiveAction(state, plan),
            SheetAction(tr("Plan löschen"), destructive = true) { sync.delete(plan.id) },
        )) { menu = null }
    }
    moving?.let { plan -> MoveToFolderSheet(state, plan) { moving = null } }
    renaming?.let { plan ->
        AlertDialog(tr("Plan umbenennen"), confirm = tr("Sichern"), fields = listOf(AlertField(tr("Name"), plan.data.optString("name"))),
            onDismiss = { renaming = null }) { values ->
            if (values[0].isNotBlank()) sync.update(plan.id) { it.put("name", values[0].trim()) }
            renaming = null
        }
    }
}

// ================================================================
// ONE PLAN
// ================================================================

@Composable
fun PlanScreen(state: AppState, planId: String, revision: Long) {
    val colors = palette
    val sync = state.sync
    val context = LocalContext.current
    val obj = remember(revision, planId) { sync.get(planId) } ?: return
    val plan = obj.data
    var menu by remember { mutableStateOf(false) }
    var columnsMenu by remember { mutableStateOf(false) }
    var rotation by remember { mutableStateOf(false) }
    // A task just added opens for editing right away.
    var openTask by remember { mutableStateOf<Int?>(null) }
    // Like Reminders: "Reihenfolge ändern" shows arrows on every task until "Fertig".
    var reordering by remember { mutableStateOf(false) }
    fun save(data: JSONObject) = sync.put("plan", data, obj.share, planId)

    Column(Modifier.fillMaxSize().background(colors.background).imePadding()) {
        NavBar("", tr("Pläne"), { state.pop() }, actions = {
            BarButton(Glyph.Share, tr("Teilen")) { state.push(Route.Share(planId)) }
            if (Plans.isTimeline(plan)) BarButton(Glyph.Plus, tr("Aufgabe hinzufügen")) { save(addTask(plan, false)); openTask = Plans.tasks(plan).size }
            else BarButton(Glyph.Plus, tr("Zeile hinzufügen")) { save(Plans.insertRow(plan, Plans.rows(plan).size)) }
            BarButton(Glyph.More, tr("Mehr")) { menu = true }
        })
        Text(plan.optString("name").ifEmpty { tr("Plan") }, style = Type.largeTitle, color = colors.label, modifier = Modifier.padding(horizontal = 16.dp))
        Text((if (Plans.isTimeline(plan)) tr("Zeitstrahl") else tr("Raster")) + " · " + shareLabel(sync, obj),
            style = Type.subheadline, color = colors.secondary, modifier = Modifier.padding(horizontal = 16.dp))
        Spacer(Modifier.height(10.dp))
        Box(Modifier.weight(1f).navigationBarsPadding()) {
            if (Plans.isTimeline(plan)) Timeline(plan, openTask, sync.userId, reordering, onReordered = { reordering = false },
                onOpened = { openTask = null },
                onAdd = { milestone -> save(addTask(plan, milestone)); openTask = Plans.tasks(plan).size }) { save(it) }
            else Grid(plan) { save(it) }
        }
    }
    if (menu) {
        val actions = buildList {
            if (Plans.isTimeline(plan)) {
                add(SheetAction(tr("Aufgabe hinzufügen")) { save(addTask(plan, false)); openTask = Plans.tasks(plan).size })
                add(SheetAction(tr("Meilenstein hinzufügen")) { save(addTask(plan, true)); openTask = Plans.tasks(plan).size })
                if (Plans.tasks(plan).size > 1) {
                    add(SheetAction(tr("Reihenfolge ändern")) { reordering = true })
                    add(SheetAction(tr("Nach Datum sortieren")) { save(Plans.sortTasks(plan)) })
                }
            } else {
                add(SheetAction(tr("Zeile hinzufügen")) { save(Plans.insertRow(plan, Plans.rows(plan).size)) })
                add(SheetAction(if (Plans.columnType(plan) == "free") tr("Spalte hinzufügen") else tr("Spalte anhängen")) { save(Plans.insertColumn(plan, Plans.columnCount(plan))) })
                add(SheetAction(tr("Spalten: {columnTypeName} …", "columnTypeName" to (columnTypeName(Plans.columnType(plan))))) { columnsMenu = true })
                if (Plans.columnType(plan) == "weeks") add(SheetAction(tr("Rotation …")) { rotation = true })
            }
            add(SheetAction(tr("Als PDF teilen …")) { PlanPdf.share(state, context, obj) })
        }
        ActionSheet(null, actions) { menu = false }
    }
    if (columnsMenu) {
        ActionSheet(tr("Was sind die Spalten?"), COLUMN_TYPES.map { (key, label) ->
            SheetAction(label + if (key == Plans.columnType(plan)) " ✓" else "") { save(Plans.setColumnType(plan, key)) }
        }) { columnsMenu = false }
    }
    if (rotation) {
        val rot = plan.optJSONObject("rot")
        val people = rot?.optJSONArray("people")?.let { list -> (0 until list.length()).joinToString(", ") { list.optString(it) } }.orEmpty()
        AlertDialog(tr("Rotation"), tr("Die Namen rücken jede Woche eine Zeile weiter. Ein eigener Eintrag in einer Zelle gilt nur dort."),
            confirm = tr("Übernehmen"), fields = listOf(AlertField(tr("z. B. Tom, Mia, Ben"), people)), onDismiss = { rotation = false }) { values ->
            val names = values[0].split(",", "\n").map { it.trim() }.filter { it.isNotEmpty() }
            val data = JSONObject(plan.toString())
            if (names.isEmpty()) data.remove("rot")
            else data.put("rot", JSONObject().put("people", JSONArray(names)).put("start", rot?.optString("start")?.ifEmpty { null } ?: Plans.monday(LocalDate.now()).toString()))
            save(data)
            rotation = false
        }
    }
}

private val COLUMN_TYPES = listOf("free" to tr("Freie Spalten"), "weekdays" to tr("Wochentage"), "dates" to tr("Datum (Tage)"), "weeks" to tr("Wochen"))
private fun columnTypeName(key: String) = COLUMN_TYPES.firstOrNull { it.first == key }?.second ?: tr("Freie Spalten")

private fun addTask(plan: JSONObject, milestone: Boolean): JSONObject {
    val today = LocalDate.now()
    val task = JSONObject().put("x", if (milestone) tr("Meilenstein") else tr("Neue Aufgabe")).put("from", today.toString())
        .put("to", (if (milestone) today else today.plusDays(4)).toString()).put("k", if (milestone) "pink" else "blue")
    if (milestone) task.put("m", true)
    return JSONObject(plan.toString()).put("tasks", JSONArray(Plans.tasks(plan) + task))
}

// --- grid ---

private sealed class GridTarget {
    data class Cell(val row: Int, val column: Int) : GridTarget()
    data class RowHead(val row: Int) : GridTarget()
    data class ColumnHead(val column: Int) : GridTarget()
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun Grid(plan: JSONObject, save: (JSONObject) -> Unit) {
    val colors = palette
    val labels = Plans.columnLabels(plan)
    val rows = Plans.rows(plan)
    val cells = Plans.cells(plan)
    val today = Plans.todayColumn(plan)
    val free = Plans.columnType(plan) == "free"
    var target by remember { mutableStateOf<GridTarget?>(null) }
    val line = colors.separator
    val cellWidth = 104.dp
    val headWidth = 116.dp
    val headFill = colors.fill.copy(alpha = 0.22f)

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
    Column(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp)) {
        Row(Modifier.height(androidx.compose.foundation.layout.IntrinsicSize.Min)) {
            Box(Modifier.width(headWidth).fillMaxHeight().heightIn(min = 40.dp).border(0.5.dp, line).background(headFill))
            labels.forEachIndexed { c, label ->
                Box(Modifier.width(cellWidth).fillMaxHeight().heightIn(min = 40.dp).border(0.5.dp, line)
                    .background(if (c == today) colors.accent.copy(alpha = 0.18f) else headFill)
                    .clickable { target = GridTarget.ColumnHead(c) }.padding(8.dp), contentAlignment = Alignment.CenterStart) {
                    Text(label.ifEmpty { if (free) tr("Spalte") else "" }, style = Type.subheadline.copy(fontWeight = FontWeight.SemiBold),
                        color = if (c == today) colors.accentText else if (label.isEmpty()) colors.tertiary else colors.label, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
            }
        }
        rows.forEachIndexed { r, label ->
            Row(Modifier.height(androidx.compose.foundation.layout.IntrinsicSize.Min)) {
                Box(Modifier.width(headWidth).fillMaxHeight().heightIn(min = 44.dp).border(0.5.dp, line).background(headFill)
                    .clickable { target = GridTarget.RowHead(r) }.padding(8.dp), contentAlignment = Alignment.CenterStart) {
                    Text(label.ifEmpty { tr("Zeile") }, style = Type.subheadline.copy(fontWeight = FontWeight.SemiBold),
                        color = if (label.isEmpty()) colors.tertiary else colors.label, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                labels.indices.forEach { c ->
                    val cell = cells[r][c]
                    val own = cell?.optString("x").orEmpty()
                    val rotated = if (own.isEmpty()) Plans.rotationName(plan, r, c) else null
                    val fill = cell?.optString("k")?.takeIf { it.isNotEmpty() }?.let { planColor(it, 0.35f) }
                        ?: if (c == today) colors.accent.copy(alpha = 0.12f) else Color.Transparent
                    Box(Modifier.width(cellWidth).fillMaxHeight().heightIn(min = 44.dp).border(0.5.dp, line).background(fill)
                        .clickable { target = GridTarget.Cell(r, c) }.padding(8.dp), contentAlignment = Alignment.CenterStart) {
                        Text(own.ifEmpty { rotated.orEmpty() }, style = Type.subheadline.copy(fontStyle = if (rotated != null) FontStyle.Italic else FontStyle.Normal),
                            color = if (rotated != null) colors.secondary else colors.label, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
        Spacer(Modifier.height(10.dp))
        Text(if (Plans.columnType(plan) == "weeks" && plan.has("rot")) tr("Kursiv: durch die Rotation. Antippen zum Ändern, Kopfzeilen für Zeilen und Spalten.")
            else tr("Zelle antippen zum Bearbeiten, Kopfzeilen für Zeilen und Spalten."), style = Type.footnote, color = colors.secondary,
            modifier = Modifier.padding(horizontal = 16.dp))
    }

    when (val t = target) {
        is GridTarget.Cell -> CellDialog(cells[t.row][t.column]?.optString("x").orEmpty(), cells[t.row][t.column]?.optString("k").orEmpty(),
            Plans.rotationName(plan, t.row, t.column), "${rows[t.row].ifEmpty { "Zeile" }} · ${labels[t.column].ifEmpty { "Spalte" }}",
            onDismiss = { target = null }) { text, color -> save(Plans.setCell(plan, t.row, t.column, text, color)); target = null }
        is GridTarget.RowHead -> HeadSheet(tr("Zeile"), rows[t.row], editable = true, canRemove = rows.size > 1, free = true,
            onDismiss = { target = null }, rename = { save(Plans.setRow(plan, t.row, it)) },
            before = { save(Plans.insertRow(plan, t.row)) }, after = { save(Plans.insertRow(plan, t.row + 1)) }, remove = { save(Plans.removeRow(plan, t.row)) },
            up = if (t.row > 0) ({ save(Plans.moveRow(plan, t.row, t.row - 1)) }) else null,
            down = if (t.row < rows.size - 1) ({ save(Plans.moveRow(plan, t.row, t.row + 1)) }) else null)
        is GridTarget.ColumnHead -> HeadSheet(tr("Spalte"), labels[t.column], editable = free, canRemove = labels.size > 1, free = free,
            onDismiss = { target = null }, rename = { save(Plans.setColumnLabel(plan, t.column, it)) },
            before = { save(Plans.insertColumn(plan, t.column)) }, after = { save(Plans.insertColumn(plan, t.column + 1)) },
            remove = { save(Plans.removeColumn(plan, t.column)) })
        null -> {}
    }
}

@Composable
private fun HeadSheet(kind: String, label: String, editable: Boolean, canRemove: Boolean, free: Boolean, onDismiss: () -> Unit,
                      rename: (String) -> Unit, before: () -> Unit, after: () -> Unit, remove: () -> Unit,
                      up: (() -> Unit)? = null, down: (() -> Unit)? = null) {
    var renaming by remember { mutableStateOf(false) }
    if (renaming) {
        AlertDialog(tr("{kind} umbenennen", "kind" to kind), confirm = tr("Sichern"), fields = listOf(AlertField(kind, label)), onDismiss = onDismiss) { values ->
            rename(values[0].trim()); onDismiss()
        }
        return
    }
    val rowKind = kind == "Zeile"
    ActionSheet(label.ifEmpty { kind }, buildList {
        if (editable) add(SheetAction(tr("Umbenennen …")) { renaming = true })
        if (free) {
            add(SheetAction(if (rowKind) tr("Zeile darüber einfügen") else tr("Spalte links einfügen")) { before(); onDismiss() })
            add(SheetAction(if (rowKind) tr("Zeile darunter einfügen") else tr("Spalte rechts einfügen")) { after(); onDismiss() })
        } else add(SheetAction(tr("Spalte anhängen")) { after(); onDismiss() })
        up?.let { add(SheetAction(tr("Zeile nach oben")) { it(); onDismiss() }) }
        down?.let { add(SheetAction(tr("Zeile nach unten")) { it(); onDismiss() }) }
        if (canRemove) add(SheetAction(if (rowKind) tr("Zeile löschen") else if (free) tr("Spalte löschen") else tr("Letzte Spalte entfernen"), destructive = true) { remove(); onDismiss() })
    }) { if (!renaming) onDismiss() }
}

@Composable
private fun CellDialog(text: String, color: String, rotated: String?, title: String, onDismiss: () -> Unit, onSave: (String, String) -> Unit) {
    val colors = palette
    var value by remember { mutableStateOf(text) }
    var chosen by remember { mutableStateOf(color) }
    Dialog(onDismissRequest = onDismiss) {
        Column(Modifier.width(300.dp).clip(RoundedCornerShape(14.dp)).background(if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2))) {
            Column(Modifier.padding(16.dp)) {
                Text(title, style = Type.headline, color = colors.label)
                if (rotated != null) Text(tr("Rotation: {rotated} – ein Eintrag hier gilt nur für diese Zelle.", "rotated" to rotated), style = Type.footnote, color = colors.secondary)
                Spacer(Modifier.height(10.dp))
                Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(7.dp)).background(colors.surface).padding(10.dp)) {
                    if (value.isEmpty()) Text(rotated ?: tr("Eintrag"), style = Type.body, color = colors.tertiary)
                    BasicTextField(value, { value = it }, textStyle = Type.body.copy(color = colors.label), cursorBrush = SolidColor(colors.accent),
                        modifier = Modifier.fillMaxWidth())
                }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    (listOf("") + Plans.COLORS.keys).forEach { name ->
                        Box(Modifier.size(26.dp).clip(CircleShape).background(if (name.isEmpty()) colors.surface else planColor(name))
                            .border(if (chosen == name) 2.5.dp else 0.5.dp, if (chosen == name) colors.label else colors.separator, CircleShape)
                            .clickable { chosen = name }, contentAlignment = Alignment.Center) {
                            if (name.isEmpty()) Text("–", style = Type.footnote, color = colors.secondary)
                        }
                    }
                }
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().height(46.dp)) {
                Box(Modifier.weight(1f).fillMaxSize().clickable(onClick = onDismiss), contentAlignment = Alignment.Center) {
                    Text(tr("Abbrechen"), style = Type.body, color = colors.accentText)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(Modifier.weight(1f).fillMaxSize().clickable { onSave(value.trim(), chosen) }, contentAlignment = Alignment.Center) {
                    Text(tr("Sichern"), style = Type.headline, color = colors.accentText)
                }
            }
        }
    }
}

// --- timeline ---

@Composable
private fun Timeline(plan: JSONObject, open: Int?, userId: Int, reordering: Boolean, onReordered: () -> Unit, onOpened: () -> Unit,
                     onAdd: (Boolean) -> Unit, save: (JSONObject) -> Unit) {
    val colors = palette
    val tasks = Plans.tasks(plan)
    val (first, last) = Plans.timelineRange(plan)
    val days = ChronoUnit.DAYS.between(first, last).toInt() + 1
    val dayWidth = 14.dp
    val rowHeight = 34.dp
    var editing by remember { mutableStateOf<Int?>(null) }
    androidx.compose.runtime.LaunchedEffect(open, tasks.size) { if (open != null && open < tasks.size) { editing = open; onOpened() } }
    val density = LocalDensity.current
    val labelColor = colors.secondary
    val lineColor = colors.separator
    val today = LocalDate.now()

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
        Box(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp)) {
            val width = dayWidth * days
            Column {
                Row {
                    for (i in 0 until days step 7) {
                        val d = first.plusDays(i.toLong())
                        Text(tr("KW {week} · {date}", "week" to d.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR), "date" to "%02d.%02d.".format(d.dayOfMonth, d.monthValue)), style = Type.caption,
                            color = labelColor, maxLines = 1, modifier = Modifier.width(dayWidth * 7))
                    }
                }
                Canvas(Modifier.width(width).height(rowHeight * maxOf(1, tasks.size) + 8.dp)) {
                    val day = dayWidth.toPx()
                    val row = rowHeight.toPx()
                    for (i in 0..days step 7) drawRect(lineColor, Offset(i * day, 0f), Size(1f, size.height))
                    if (!today.isBefore(first) && !today.isAfter(last)) {
                        val x = (ChronoUnit.DAYS.between(first, today) + 0.5f) * day
                        drawRect(Color(0xCCE01B24), Offset(x - 1.5f, 0f), Size(3f, size.height))
                    }
                    tasks.forEachIndexed { index, task ->
                        val span = Plans.taskSpan(task) ?: return@forEachIndexed
                        val x = ChronoUnit.DAYS.between(first, span.first) * day
                        val y = index * row + 4.dp.toPx()
                        val color = planColor(task.optString("k").ifEmpty { "blue" })
                        if (task.optBoolean("m")) {
                            val cx = x + day / 2; val cy = y + row / 2 - 4.dp.toPx(); val s = 9.dp.toPx()
                            // Earlier days stay visible, faded, joined to the current one by a dashed line.
                            for (entry in Plans.moved(task)) {
                                val was = Plans.day(entry.optString("was")) ?: continue
                                val ox = ChronoUnit.DAYS.between(first, was) * day + day / 2
                                drawPath(Path().apply { moveTo(ox, cy - s); lineTo(ox + s, cy); lineTo(ox, cy + s); lineTo(ox - s, cy); close() }, color.copy(alpha = 0.3f))
                                val sign = if (cx > ox) 1 else -1
                                drawLine(color.copy(alpha = 0.5f), Offset(ox + sign * s, cy), Offset(cx - sign * s, cy), 1.2.dp.toPx(),
                                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(3.dp.toPx(), 3.dp.toPx())))
                            }
                            drawPath(Path().apply { moveTo(cx, cy - s); lineTo(cx + s, cy); lineTo(cx, cy + s); lineTo(cx - s, cy); close() }, color)
                        } else {
                            val w = (ChronoUnit.DAYS.between(span.first, span.second) + 1) * day
                            drawRoundRect(color, Offset(x + 1f, y), Size(maxOf(4f, w - 2f), row - 12.dp.toPx()), CornerRadius(5.dp.toPx()))
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        if (reordering) Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(tr("Reihenfolge ändern"), style = Type.footnote, color = colors.secondary, modifier = Modifier.weight(1f))
            TextButton(tr("Fertig"), bold = true, onClick = onReordered)
        }
        tasks.forEachIndexed { index, task ->
            val span = Plans.taskSpan(task)
            Row(Modifier.fillMaxWidth().clickable(enabled = !reordering) { editing = index }.padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(12.dp).clip(if (task.optBoolean("m")) RoundedCornerShape(2.dp) else CircleShape).background(planColor(task.optString("k").ifEmpty { "blue" })))
                Spacer(Modifier.width(10.dp))
                Text(task.optString("x").ifEmpty { tr("Aufgabe") }, style = Type.body, color = colors.label, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(span?.let { if (task.optBoolean("m")) "◆ " + german(it.first) else "${german(it.first)} – ${german(it.second)}" }.orEmpty(),
                    style = Type.subheadline, color = colors.secondary)
                if (reordering) {
                    Spacer(Modifier.width(6.dp))
                    for ((label, to) in listOf("↑" to index - 1, "↓" to index + 1)) {
                        val possible = to in tasks.indices
                        Box(Modifier.size(40.dp).clip(CircleShape).clickable(enabled = possible) { save(Plans.moveTask(plan, index, to)) },
                            contentAlignment = Alignment.Center) {
                            Text(label, style = Type.title3, color = if (possible) colors.accentText else colors.tertiary)
                        }
                    }
                }
            }
            val moved = Plans.moved(task)
            if (moved.isNotEmpty()) {
                val trail = (moved.map { it.optString("was") } + task.optString("from")).mapNotNull { Plans.day(it)?.let(::german) }.joinToString(" → ")
                Text("verschoben: $trail", style = Type.caption, color = colors.secondary,
                    modifier = Modifier.padding(start = 38.dp, end = 16.dp, bottom = 8.dp))
            }
            HorizontalDivider(Modifier.padding(start = 38.dp), 0.5.dp, colors.separator)
        }
        // Like adding a card or list item: a row at the end of the list.
        for ((label, milestone) in listOf(tr("Aufgabe hinzufügen") to false, tr("Meilenstein hinzufügen") to true)) {
            Row(Modifier.fillMaxWidth().clickable { onAdd(milestone) }.padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                GlyphIcon(Glyph.Plus, colors.accent, 16.dp)
                Spacer(Modifier.width(10.dp))
                Text(label, style = Type.body, color = colors.accentText)
            }
        }
    }
    editing?.let { index ->
        TaskDialog(tasks[index], onDismiss = { editing = null }, onDelete = {
            save(JSONObject(plan.toString()).put("tasks", JSONArray(tasks.filterIndexed { i, _ -> i != index }))); editing = null
        }) { changed ->
            // Name and color as they are; the days through setTaskDay, which keeps a milestone's old day.
            var updated = JSONObject(plan.toString()).put("tasks", JSONArray(tasks.mapIndexed { i, t ->
                if (i == index) JSONObject(t.toString()).put("x", changed.optString("x")).put("k", changed.optString("k")) else t }))
            val at = System.currentTimeMillis() / 1000.0
            updated = Plans.setTaskDay(updated, index, "from", changed.optString("from"), userId, at)
            if (!changed.optBoolean("m")) updated = Plans.setTaskDay(updated, index, "to", changed.optString("to"), userId, at)
            save(updated); editing = null
        }
    }
}

@Composable
private fun TaskDialog(task: JSONObject, onDismiss: () -> Unit, onDelete: () -> Unit, onSave: (JSONObject) -> Unit) {
    val colors = palette
    val milestone = task.optBoolean("m")
    var name by remember { mutableStateOf(task.optString("x")) }
    var from by remember { mutableStateOf(Plans.day(task.optString("from"))?.let(::german).orEmpty()) }
    var to by remember { mutableStateOf(Plans.day(task.optString("to"))?.let(::german).orEmpty()) }
    var color by remember { mutableStateOf(task.optString("k").ifEmpty { "blue" }) }
    val fromDate = parseGerman(from)
    val toDate = if (milestone) fromDate else parseGerman(to)
    val valid = fromDate != null && toDate != null && !toDate.isBefore(fromDate)

    @Composable
    fun field(value: String, placeholder: String, onChange: (String) -> Unit, error: Boolean = false) {
        Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(7.dp)).background(colors.surface)
            .border(if (error) 1.dp else 0.dp, if (error) colors.red else Color.Transparent, RoundedCornerShape(7.dp)).padding(10.dp)) {
            if (value.isEmpty()) Text(placeholder, style = Type.body, color = colors.tertiary)
            BasicTextField(value, onChange, singleLine = true, textStyle = Type.body.copy(color = colors.label), cursorBrush = SolidColor(colors.accent),
                modifier = Modifier.fillMaxWidth())
        }
    }
    Dialog(onDismissRequest = onDismiss) {
        Column(Modifier.width(300.dp).clip(RoundedCornerShape(14.dp)).background(if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2))) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (milestone) tr("Meilenstein") else tr("Aufgabe"), style = Type.headline, color = colors.label)
                field(name, if (milestone) tr("Meilenstein") else tr("Aufgabe"), { name = it })
                field(from, if (milestone) tr("Datum (TT.MM.JJJJ)") else tr("Von (TT.MM.JJJJ)"), { from = it }, fromDate == null)
                if (!milestone) field(to, tr("Bis (TT.MM.JJJJ)"), { to = it }, toDate == null || (fromDate != null && toDate.isBefore(fromDate)))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Plans.COLORS.keys.forEach { key ->
                        Box(Modifier.size(28.dp).clip(CircleShape).background(planColor(key))
                            .border(if (color == key) 2.5.dp else 0.5.dp, if (color == key) colors.label else colors.separator, CircleShape)
                            .clickable { color = key })
                    }
                }
                Text(tr("Löschen"), style = Type.body, color = colors.red, modifier = Modifier.clickable(onClick = onDelete).padding(vertical = 6.dp))
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().height(46.dp)) {
                Box(Modifier.weight(1f).fillMaxSize().clickable(onClick = onDismiss), contentAlignment = Alignment.Center) {
                    Text(tr("Abbrechen"), style = Type.body, color = colors.accentText)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(Modifier.weight(1f).fillMaxSize().clickable(enabled = valid) {
                    val changed = JSONObject(task.toString()).put("x", name.trim()).put("from", fromDate.toString()).put("to", toDate.toString()).put("k", color)
                    onSave(changed)
                }, contentAlignment = Alignment.Center) {
                    Text(tr("Sichern"), style = Type.headline, color = if (valid) colors.accentText else colors.tertiary)
                }
            }
        }
    }
}

// ================================================================
// PDF (to hang up), same layout as Ubuntu's report.write_plan_pdf
// ================================================================

object PlanPdf {
    fun write(plan: JSONObject, file: File, userName: ((Int) -> String)? = null) {
        val name = plan.optString("name").ifEmpty { tr("Plan") }
        val pdf = Report.Pdf(true, tr("{name} · Stand {german}", "name" to name, "german" to (german(LocalDate.now()))))
        pdf.text(name, 18f, true, space = 10f)
        val line = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            style = android.graphics.Paint.Style.STROKE; strokeWidth = 0.8f; color = AColor.rgb(217, 217, 222) }
        val fill = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG)
        if (Plans.isTimeline(plan)) {
            val (first, last) = Plans.timelineRange(plan)
            val days = ChronoUnit.DAYS.between(first, last).toInt() + 1
            val labelWidth = 150f
            val scale = (pdf.width - 2 * pdf.margin - labelWidth) / days
            val small = pdf.paint(8f, color = pdf.grey)
            for (i in 0 until days step 7) {
                val d = first.plusDays(i.toLong())
                pdf.canvas.drawText(tr("KW {week} · {date}", "week" to d.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR), "date" to "%02d.%02d.".format(d.dayOfMonth, d.monthValue)),
                    pdf.margin + labelWidth + i * scale + 2, pdf.y + 9, small)
            }
            pdf.y += 16f
            for (task in Plans.tasks(plan)) {
                pdf.need(24f)
                pdf.canvas.drawText(task.optString("x"), pdf.margin, pdf.y + 14, pdf.paint(10f))
                for (i in 0 until days step 7) pdf.canvas.drawRect(pdf.margin + labelWidth + i * scale, pdf.y, pdf.margin + labelWidth + i * scale + 0.6f, pdf.y + 22, fill.apply { color = AColor.rgb(217, 217, 222) })
                Plans.taskSpan(task)?.let { (from, to) ->
                    fill.color = Plans.COLORS[task.optString("k")] ?: Plans.COLORS.getValue("blue")
                    val x = pdf.margin + labelWidth + ChronoUnit.DAYS.between(first, from) * scale
                    if (task.optBoolean("m")) {
                        val cx = x + scale / 2; val cy = pdf.y + 11
                        // Earlier days faded, joined by a dashed line (as in the app).
                        val base = fill.color
                        for (entry in Plans.moved(task)) {
                            val was = Plans.day(entry.optString("was")) ?: continue
                            val ox = pdf.margin + labelWidth + ChronoUnit.DAYS.between(first, was) * scale + scale / 2
                            fill.color = base; fill.alpha = 77
                            pdf.canvas.drawPath(android.graphics.Path().apply { moveTo(ox, cy - 8); lineTo(ox + 8, cy); lineTo(ox, cy + 8); lineTo(ox - 8, cy); close() }, fill)
                            val dash = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
                                style = android.graphics.Paint.Style.STROKE; strokeWidth = 0.9f; color = base; alpha = 128
                                pathEffect = android.graphics.DashPathEffect(floatArrayOf(2.5f, 2.5f), 0f) }
                            val sign = if (cx > ox) 1 else -1
                            pdf.canvas.drawLine(ox + sign * 8, cy, cx - sign * 8, cy, dash)
                        }
                        fill.color = base; fill.alpha = 255
                        pdf.canvas.drawPath(android.graphics.Path().apply { moveTo(cx, cy - 8); lineTo(cx + 8, cy); lineTo(cx, cy + 8); lineTo(cx - 8, cy); close() }, fill)
                    } else pdf.canvas.drawRect(x, pdf.y + 4, x + (ChronoUnit.DAYS.between(from, to) + 1) * scale, pdf.y + 18, fill)
                }
                pdf.y += 24f
            }
            val moves = Plans.shifts(plan)
            if (moves.isNotEmpty()) {
                pdf.y += 14f
                pdf.text(tr("Terminverschiebungen"), 12f, true, space = 6f)
                val stamp = java.text.SimpleDateFormat("dd.MM.yyyy HH:mm", java.util.Locale.GERMANY)
                fun date(text: String) = Plans.day(text)?.let(::german) ?: "–"
                pdf.table(listOf(tr("Meilenstein"), tr("Bisher"), tr("Neu"), tr("Verschiebung"), tr("Geändert am"), tr("Von")), listOf(3f, 1.4f, 1.4f, 1.2f, 1.6f, 1.8f),
                    moves.map { m ->
                        val days = Plans.day(m.was)?.let { was -> Plans.day(m.now)?.let { ChronoUnit.DAYS.between(was, it) } }
                        listOf(m.name, date(m.was), date(m.now), days?.let { "%+d Tage".format(it) } ?: "–",
                            m.at?.let { stamp.format(java.util.Date((it * 1000).toLong())) } ?: "–", m.by?.let { userName?.invoke(it) } ?: "–")
                    }, size = 9f)
            }
        } else {
            val rows = Plans.textRows(plan)
            val firstWidth = 110f
            val width = (pdf.width - 2 * pdf.margin - firstWidth) / maxOf(1, rows[0].size - 1)
            val grid = Plans.cells(plan)
            val today = Plans.todayColumn(plan)
            rows.forEachIndexed { r, row ->
                val layouts = row.mapIndexed { c, text -> pdf.layout(text, pdf.paint(10f, bold = r == 0 || c == 0), (if (c == 0) firstWidth else width) - 10f) }
                val height = layouts.maxOf { it.height } + 12f
                pdf.need(height)
                var x = pdf.margin
                layouts.forEachIndexed { c, layout ->
                    val w = if (c == 0) firstWidth else width
                    val color = if (r > 0 && c > 0) grid[r - 1][c - 1]?.optString("k")?.takeIf { it.isNotEmpty() } else null
                    if (color != null) {
                        fill.color = Plans.COLORS[color] ?: Plans.COLORS.getValue("grey"); fill.alpha = 90
                        pdf.canvas.drawRect(x, pdf.y, x + w, pdf.y + height, fill)
                    } else if (r == 0 && c > 0 && c - 1 == today) {
                        fill.color = Plans.COLORS.getValue("yellow"); fill.alpha = 64
                        pdf.canvas.drawRect(x, pdf.y, x + w, pdf.y + height, fill)
                    }
                    fill.alpha = 255
                    pdf.canvas.drawRect(x, pdf.y, x + w, pdf.y + height, line)
                    pdf.canvas.save(); pdf.canvas.translate(x + 5f, pdf.y + 6f); layout.draw(pdf.canvas); pdf.canvas.restore()
                    x += w
                }
                pdf.y += height
            }
        }
        pdf.finish(file)
    }

    fun share(state: AppState, context: android.content.Context, plan: SyncObject) {
        val name = plan.data.optString("name").ifEmpty { tr("Plan") }
        val folder = File(context.cacheDir, "reports").apply { mkdirs() }
        val file = File(folder, "${name.replace(Regex("[/\\\\:*?\"<>|]"), "_")}.pdf")
        write(JSONObject(plan.data.toString()), file) { state.sync.userName(it) }
        state.shareFile(file, "application/pdf", tr("Plan: {name}", "name" to name))
    }
}
