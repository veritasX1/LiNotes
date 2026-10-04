package io.github.veritasx1.linotes.data

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import java.time.temporal.IsoFields

/** Plans (timetable, shift plan, cleaning rota, room plan, project plan): the data model.
 *  Same rules and format as Ubuntu's plans.py (see there; PlanTest has the same cases as test_plans.py). */
object Plans {
    val WEEKDAYS = listOf("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
    /** name -> ARGB, the same colors as the highlights in notes. */
    val COLORS = linkedMapOf(
        "yellow" to 0xFFFFD93D.toInt(), "orange" to 0xFFFF9E0A.toInt(), "pink" to 0xFFFF70A8.toInt(),
        "purple" to 0xFFBF85F2.toInt(), "mint" to 0xFF4DD9BF.toInt(), "blue" to 0xFF59B3FF.toInt(), "grey" to 0xFF999AA1.toInt(),
    )
    val COLOR_NAMES = linkedMapOf("yellow" to "Gelb", "orange" to "Orange", "pink" to "Rosa", "purple" to "Lila",
        "mint" to "Mint", "blue" to "Blau", "grey" to "Grau")
    val TEMPLATES = listOf(
        Triple("leer", "Leerer Plan", "Raster mit freien Zeilen und Spalten"),
        Triple("stundenplan", "Stundenplan", "Mo–Fr × Schulstunden"),
        Triple("schichtplan", "Schichtplan", "Mo–So × Personen, Schichten farbig"),
        Triple("putzplan", "Putzplan", "Aufgaben × Wochen, Namen rotieren wöchentlich"),
        Triple("raumplan", "OP- / Raumplan", "Uhrzeit × Säle oder Räume"),
        Triple("projektplan", "Projektplan", "Zeitstrahl mit Aufgaben und Meilensteinen"),
    )

    fun day(text: String?): LocalDate? = try { if (text.isNullOrEmpty()) null else LocalDate.parse(text) } catch (error: Exception) { null }
    fun monday(date: LocalDate): LocalDate = date.minusDays((date.dayOfWeek.value - 1).toLong())
    private fun short(date: LocalDate) = "%02d.%02d.".format(date.dayOfMonth, date.monthValue)
    private fun cols(plan: JSONObject) = plan.optJSONObject("cols") ?: JSONObject()
    fun columnType(plan: JSONObject): String = cols(plan).optString("type", "free").ifEmpty { "free" }
    fun isTimeline(plan: JSONObject) = plan.optString("mode") == "timeline"

    // --- grid ---

    fun columnCount(plan: JSONObject): Int =
        if (columnType(plan) == "free") maxOf(1, cols(plan).optJSONArray("labels")?.length() ?: 0)
        else maxOf(1, cols(plan).optInt("count", 1))

    fun columnLabels(plan: JSONObject, today: LocalDate = LocalDate.now()): List<String> {
        val count = columnCount(plan)
        return when (columnType(plan)) {
            "weekdays" -> WEEKDAYS.take(count)
            "dates" -> {
                val start = day(cols(plan).optString("start")) ?: today
                (0 until count).map { start.plusDays(it.toLong()) }.map { "${WEEKDAYS[it.dayOfWeek.value - 1]} ${short(it)}" }
            }
            "weeks" -> (0 until count).map { monday(today).plusWeeks(it.toLong()) }.map { "KW ${it.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR)} · ${short(it)}" }
            else -> {
                val labels = cols(plan).optJSONArray("labels") ?: JSONArray()
                (0 until count).map { labels.optString(it) }
            }
        }
    }

    fun todayColumn(plan: JSONObject, today: LocalDate = LocalDate.now()): Int? {
        val count = columnCount(plan)
        return when (columnType(plan)) {
            "weekdays" -> (today.dayOfWeek.value - 1).takeIf { it < count }
            "dates" -> day(cols(plan).optString("start"))?.let { ChronoUnit.DAYS.between(it, today).toInt() }?.takeIf { it in 0 until count }
            "weeks" -> 0
            else -> null
        }
    }

    fun rows(plan: JSONObject): List<String> {
        val rows = plan.optJSONArray("rows") ?: JSONArray()
        return (0 until rows.length()).map { rows.optString(it) }.ifEmpty { listOf("") }
    }

    /** Cells as a rectangle rows × columns (missing ones null). */
    fun cells(plan: JSONObject): MutableList<MutableList<JSONObject?>> {
        val count = columnCount(plan)
        val source = plan.optJSONArray("cells") ?: JSONArray()
        return rows(plan).indices.map { r ->
            val row = source.optJSONArray(r) ?: JSONArray()
            (0 until count).map { c -> row.optJSONObject(c) }.toMutableList()
        }.toMutableList()
    }

    private fun cellsJson(grid: List<List<JSONObject?>>) =
        JSONArray(grid.map { row -> JSONArray().also { array -> row.forEach { array.put(it ?: JSONObject.NULL) } } })

    fun rotationName(plan: JSONObject, row: Int, column: Int, today: LocalDate = LocalDate.now()): String? {
        val rot = plan.optJSONObject("rot") ?: return null
        val list = rot.optJSONArray("people") ?: return null
        val people = (0 until list.length()).map { list.optString(it) }.filter { it.isNotBlank() }
        if (people.isEmpty() || columnType(plan) != "weeks") return null
        val start = monday(day(rot.optString("start")) ?: today)
        val week = (ChronoUnit.DAYS.between(start, monday(today)) / 7).toInt() + column
        return people[Math.floorMod(row + week, people.size)]
    }

    fun cellText(plan: JSONObject, row: Int, column: Int, today: LocalDate = LocalDate.now()): String {
        val own = cells(plan)[row][column]?.optString("x").orEmpty()
        return own.ifEmpty { rotationName(plan, row, column, today).orEmpty() }
    }

    private fun copy(plan: JSONObject) = JSONObject(plan.toString())

    fun setCell(plan: JSONObject, row: Int, column: Int, text: String? = null, color: String? = null): JSONObject {
        val grid = cells(plan)
        val cell = JSONObject(grid[row][column]?.toString() ?: "{}")
        if (text != null) cell.put("x", text)
        if (color != null) cell.put("k", color)
        for (key in listOf("x", "k")) if (cell.optString(key).isEmpty()) cell.remove(key)
        grid[row][column] = if (cell.length() == 0) null else cell
        return copy(plan).put("cells", cellsJson(grid))
    }

    fun setRow(plan: JSONObject, row: Int, label: String): JSONObject =
        copy(plan).put("rows", JSONArray(rows(plan).toMutableList().also { it[row] = label }))

    fun setColumnLabel(plan: JSONObject, column: Int, label: String): JSONObject {
        val labels = columnLabels(plan).toMutableList().also { it[column] = label }
        return copy(plan).put("cols", JSONObject(cols(plan).toString()).put("labels", JSONArray(labels)))
    }

    fun insertRow(plan: JSONObject, at: Int, label: String = ""): JSONObject {
        val rows = rows(plan).toMutableList().also { it.add(at, label) }
        val grid = cells(plan).also { it.add(at, MutableList(columnCount(plan)) { null }) }
        return copy(plan).put("rows", JSONArray(rows)).put("cells", cellsJson(grid))
    }

    fun removeRow(plan: JSONObject, at: Int): JSONObject {
        val rows = rows(plan).toMutableList()
        if (rows.size <= 1) return plan
        val grid = cells(plan)
        rows.removeAt(at); grid.removeAt(at)
        return copy(plan).put("rows", JSONArray(rows)).put("cells", cellsJson(grid))
    }

    fun insertColumn(plan: JSONObject, at: Int, label: String = ""): JSONObject {
        val cols = JSONObject(cols(plan).toString())
        val grid = cells(plan)
        var index = at
        if (columnType(plan) == "free") {
            cols.put("labels", JSONArray(columnLabels(plan).toMutableList().also { it.add(at, label) }))
        } else {
            cols.put("count", columnCount(plan) + 1)
            index = columnCount(plan)
        }
        grid.forEach { it.add(index, null) }
        return copy(plan).put("cols", cols).put("cells", cellsJson(grid))
    }

    fun removeColumn(plan: JSONObject, at: Int): JSONObject {
        val count = columnCount(plan)
        if (count <= 1) return plan
        val cols = JSONObject(cols(plan).toString())
        val grid = cells(plan)
        var index = at
        if (columnType(plan) == "free") {
            cols.put("labels", JSONArray(columnLabels(plan).toMutableList().also { it.removeAt(at) }))
        } else {
            // Weekdays, dates and weeks follow their count: the last one goes.
            cols.put("count", count - 1)
            index = count - 1
        }
        grid.forEach { it.removeAt(index) }
        return copy(plan).put("cols", cols).put("cells", cellsJson(grid))
    }

    fun setColumnType(plan: JSONObject, kind: String, today: LocalDate = LocalDate.now()): JSONObject {
        if (columnType(plan) == kind) return plan
        val count = columnCount(plan)
        val cols = JSONObject().put("type", kind)
        when (kind) {
            "free" -> cols.put("labels", JSONArray(columnLabels(plan, today)))
            "weekdays" -> cols.put("count", if (count > 5) 7 else 5)
            "dates" -> cols.put("count", maxOf(count, 7)).put("start", today.toString())
            else -> cols.put("count", maxOf(count, 4))
        }
        val changed = copy(plan).put("cols", cols)
        return changed.put("cells", cellsJson(cells(changed)))
    }

    // --- timeline ---

    fun tasks(plan: JSONObject): List<JSONObject> {
        val array = plan.optJSONArray("tasks") ?: JSONArray()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
    }

    fun taskSpan(task: JSONObject): Pair<LocalDate, LocalDate>? {
        val start = day(task.optString("from")) ?: return null
        val end = if (task.optBoolean("m")) start else day(task.optString("to")) ?: start
        return start to maxOf(start, end)
    }

    fun timelineRange(plan: JSONObject, today: LocalDate = LocalDate.now()): Pair<LocalDate, LocalDate> {
        val days = tasks(plan).flatMap { listOfNotNull(day(it.optString("from")), day(it.optString("to")) ?: day(it.optString("from"))) } +
            tasks(plan).flatMap { task -> moved(task).mapNotNull { day(it.optString("was")) } }  // faded earlier days
        val first = monday(days.minOrNull() ?: today)
        val last = maxOf(days.maxOrNull() ?: today, first.plusDays(13))
        return first to monday(last).plusDays(6)
    }

    // --- order and shifts ---

    private fun <T> movedList(items: List<T>, at: Int, to: Int): List<T> {
        if (at !in items.indices) return items
        val list = items.toMutableList()
        val item = list.removeAt(at)
        list.add(to.coerceIn(0, list.size), item)
        return list
    }

    /** A grid row with its cells to another place. */
    fun moveRow(plan: JSONObject, at: Int, to: Int): JSONObject {
        val rows = rows(plan)
        if (at !in rows.indices) return plan
        return copy(plan).put("rows", JSONArray(movedList(rows, at, to))).put("cells", cellsJson(movedList(cells(plan), at, to)))
    }

    fun moveTask(plan: JSONObject, at: Int, to: Int): JSONObject =
        copy(plan).put("tasks", JSONArray(movedList(tasks(plan), at, to).map { JSONObject(it.toString()) }))

    /** All tasks by start day (tasks without a day at the end); equal days keep their order. */
    fun sortTasks(plan: JSONObject): JSONObject =
        copy(plan).put("tasks", JSONArray(tasks(plan).sortedBy { day(it.optString("from")) ?: LocalDate.MAX }.map { JSONObject(it.toString()) }))

    fun moved(task: JSONObject): List<JSONObject> {
        val array = task.optJSONArray("moved") ?: return emptyList()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
    }

    /** Set "from" or "to" of a task (ISO day). A milestone keeps the day it had in "moved", so the
     *  old date stays visible (faded) and the report lists the shift. */
    fun setTaskDay(plan: JSONObject, index: Int, key: String, value: String, by: Int? = null, at: Double? = null): JSONObject {
        val list = tasks(plan).map { JSONObject(it.toString()) }
        if (index !in list.indices) return plan
        val task = list[index]
        if (task.optString(key) == value) return plan
        if (task.optBoolean("m")) {
            val old = task.optString("from")
            if (old.isNotEmpty()) {
                val entry = JSONObject().put("was", old).put("at", at ?: JSONObject.NULL).put("by", by ?: JSONObject.NULL)
                task.put("moved", (task.optJSONArray("moved") ?: JSONArray()).put(entry))
            }
            task.put("from", value).put("to", value)
        } else task.put(key, value)
        return copy(plan).put("tasks", JSONArray(list))
    }

    data class Shift(val name: String, val was: String, val now: String, val at: Double?, val by: Int?)

    /** Every milestone shift, oldest first per milestone. */
    fun shifts(plan: JSONObject): List<Shift> = tasks(plan).flatMap { task ->
        val moved = moved(task)
        val days = moved.map { it.optString("was") } + task.optString("from")
        moved.mapIndexed { i, entry ->
            Shift(task.optString("x").ifEmpty { "Meilenstein" }, entry.optString("was"), days[i + 1],
                if (entry.isNull("at")) null else entry.optDouble("at"), if (entry.isNull("by")) null else entry.optInt("by"))
        }
    }

    // --- templates ---

    fun template(key: String, today: LocalDate = LocalDate.now()): JSONObject {
        fun weekCols(type: String, count: Int) = JSONObject().put("type", type).put("count", count)
        return when (key) {
            "stundenplan" -> JSONObject().put("mode", "grid").put("cols", weekCols("weekdays", 5))
                .put("rows", JSONArray(listOf("1. 8:00", "2. 8:50", "3. 9:55", "4. 10:45", "5. 11:50", "6. 12:40")))
            "schichtplan" -> JSONObject().put("mode", "grid").put("cols", weekCols("weekdays", 7))
                .put("rows", JSONArray(listOf("Person 1", "Person 2", "Person 3")))
                .put("cells", JSONArray().put(JSONArray().put(JSONObject().put("x", "Früh").put("k", "yellow")).put(JSONObject().put("x", "Früh").put("k", "yellow"))
                    .put(JSONObject().put("x", "Spät").put("k", "blue")).put(JSONObject().put("x", "Spät").put("k", "blue"))
                    .put(JSONObject().put("x", "Nacht").put("k", "purple")).put(JSONObject.NULL).put(JSONObject.NULL)))
            "putzplan" -> JSONObject().put("mode", "grid").put("cols", weekCols("weeks", 4))
                .put("rows", JSONArray(listOf("Bad", "Küche", "Staubsaugen", "Müll")))
                .put("rot", JSONObject().put("people", JSONArray(listOf("Person 1", "Person 2"))).put("start", monday(today).toString()))
            "raumplan" -> JSONObject().put("mode", "grid").put("cols", JSONObject().put("type", "free").put("labels", JSONArray(listOf("Saal 1", "Saal 2", "Saal 3"))))
                .put("rows", JSONArray((7..16).map { "%02d:00".format(it) }))
            "projektplan" -> {
                val start = monday(today)
                fun task(name: String, from: Long, to: Long, color: String, milestone: Boolean = false) = JSONObject().put("x", name)
                    .put("from", start.plusDays(from).toString()).put("to", start.plusDays(to).toString()).put("k", color)
                    .also { if (milestone) it.put("m", true) }
                JSONObject().put("mode", "timeline").put("tasks", JSONArray(listOf(task("Konzept", 0, 4, "blue"),
                    task("Umsetzung", 7, 18, "orange"), task("Test", 14, 20, "mint"), task("Abnahme", 21, 21, "pink", true))))
            }
            else -> JSONObject().put("mode", "grid").put("cols", JSONObject().put("type", "free").put("labels", JSONArray(listOf("", "", ""))))
                .put("rows", JSONArray(listOf("", "", "")))
        }
    }

    /** The plan as rows of text (PDF, search). */
    fun textRows(plan: JSONObject, today: LocalDate = LocalDate.now()): List<List<String>> {
        if (isTimeline(plan)) {
            fun german(date: LocalDate) = "%02d.%02d.%d".format(date.dayOfMonth, date.monthValue, date.year)
            return listOf(listOf("Aufgabe", "Von", "Bis")) + tasks(plan).mapNotNull { task ->
                taskSpan(task)?.let { (from, to) -> listOf(task.optString("x") + if (task.optBoolean("m")) " ◆" else "", german(from), german(to)) }
            }
        }
        return listOf(listOf("") + columnLabels(plan, today)) + rows(plan).mapIndexed { r, label ->
            listOf(label) + (0 until columnCount(plan)).map { cellText(plan, r, it, today) }
        }
    }
}
