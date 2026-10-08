package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Plans
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.time.LocalDate

/** Karte a947f688: same cases as linux/tests/test_plans.py. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PlanTest {
    private val today = LocalDate.of(2026, 10, 7)  // a Wednesday, KW 41

    @Test
    fun sameAsUbuntu() {
        val week = JSONObject("""{"cols":{"type":"weekdays","count":5},"rows":["1","2"]}""")
        assertEquals(listOf("Mo", "Di", "Mi", "Do", "Fr"), Plans.columnLabels(week, today))
        assertEquals(2, Plans.todayColumn(week, today))
        assertNull(Plans.todayColumn(week, LocalDate.of(2026, 10, 11)))

        val dates = JSONObject("""{"cols":{"type":"dates","count":3,"start":"2026-10-06"},"rows":["a"]}""")
        assertEquals(listOf("Di 06.10.", "Mi 07.10.", "Do 08.10."), Plans.columnLabels(dates, today))
        assertEquals(1, Plans.todayColumn(dates, today))

        val weeks = JSONObject("""{"cols":{"type":"weeks","count":3},"rows":["Bad","Küche","Müll"],"rot":{"people":["Olaf","Anna"],"start":"2026-09-28"}}""")
        assertEquals(listOf("KW 41 · 05.10.", "KW 42 · 12.10.", "KW 43 · 19.10."), Plans.columnLabels(weeks, today))
        assertEquals(listOf("Anna", "Olaf", "Anna"), (0..2).map { Plans.cellText(weeks, it, 0, today) })
        assertEquals(listOf("Anna", "Olaf", "Anna"), (0..2).map { Plans.cellText(weeks, 0, it, today) })
        val changed = Plans.setCell(weeks, 0, 0, "Gast")
        assertEquals("Gast", Plans.cellText(changed, 0, 0, today))
        assertEquals("Olaf", Plans.cellText(changed, 1, 0, today))

        var free = JSONObject("""{"cols":{"type":"free","labels":["A","B"]},"rows":["x","y"]}""")
        free = Plans.setCell(free, 1, 1, "z", "blue")
        assertEquals("""[[null,null],[null,{"x":"z","k":"blue"}]]""", cellsJson(free))
        free = Plans.insertColumn(free, 1, "neu")
        assertEquals(listOf("A", "neu", "B"), Plans.columnLabels(free))
        assertEquals("""[null,null,{"x":"z","k":"blue"}]""", rowJson(free, 1))
        free = Plans.insertRow(free, 0, "oben")
        assertEquals(listOf("oben", "x", "y"), Plans.rows(free))
        free = Plans.removeColumn(Plans.removeRow(free, 0), 1)
        assertEquals("""[[null,null],[null,{"x":"z","k":"blue"}]]""", cellsJson(free))
        assertNull(Plans.cells(Plans.setCell(free, 1, 1, "", ""))[1][1])

        val timeline = Plans.template("projektplan", today)
        assertEquals(LocalDate.of(2026, 10, 5) to LocalDate.of(2026, 11, 1), Plans.timelineRange(timeline, today))
        assertEquals(LocalDate.of(2026, 10, 26) to LocalDate.of(2026, 10, 26), Plans.taskSpan(Plans.tasks(timeline)[3]))
        assertEquals(LocalDate.of(2026, 10, 5) to LocalDate.of(2026, 10, 18), Plans.timelineRange(JSONObject("""{"tasks":[]}"""), today))
        assertEquals(listOf("", "Mo", "Di", "Mi", "Do", "Fr"), Plans.textRows(week, today)[0])
        for ((key, _, _) in Plans.TEMPLATES) assertTrue(Plans.template(key, today).optString("mode") in setOf("grid", "timeline"))

        // order: grid rows with their cells, tasks one by one and by date (same cases as test_plans.py)
        val grid = JSONObject("""{"rows":["a","b","c"],"cols":{"type":"free","labels":["x"]},"cells":[[{"x":"1"}],[null],[{"x":"3"}]]}""")
        val movedRow = Plans.moveRow(grid, 2, 0)
        assertEquals(listOf("c", "a", "b"), Plans.rows(movedRow))
        assertEquals("""[[{"x":"3"}],[{"x":"1"}],[null]]""", cellsJson(movedRow))
        assertEquals(movedRow.toString(), Plans.moveRow(movedRow, 5, 0).toString())
        assertEquals(listOf("Umsetzung", "Test", "Abnahme", "Konzept"), Plans.tasks(Plans.moveTask(timeline, 0, 9)).map { it.optString("x") })
        val mixed = JSONObject("""{"tasks":[{"x":"c","from":"2026-10-20"},{"x":"ohne"},{"x":"a","from":"2026-10-01"},{"x":"b","from":"2026-10-20"}]}""")
        assertEquals(listOf("a", "c", "b", "ohne"), Plans.tasks(Plans.sortTasks(mixed)).map { it.optString("x") })

        // a milestone remembers where it was; ordinary tasks just change
        var shifted = Plans.setTaskDay(timeline, 3, "from", "2026-11-02", by = 1, at = 100.0)
        shifted = Plans.setTaskDay(shifted, 3, "from", "2026-11-09", by = 3, at = 200.0)
        val stone = Plans.tasks(shifted)[3]
        assertEquals("2026-11-09", stone.optString("from"))
        assertEquals("2026-11-09", stone.optString("to"))
        assertEquals(listOf("2026-10-26", "2026-11-02"), Plans.moved(stone).map { it.optString("was") })
        assertEquals(shifted.toString(), Plans.setTaskDay(shifted, 3, "from", "2026-11-09", by = 1, at = 300.0).toString())
        assertEquals(listOf(Plans.Shift("Abnahme", "2026-10-26", "2026-11-02", 100.0, 1), Plans.Shift("Abnahme", "2026-11-02", "2026-11-09", 200.0, 3)),
            Plans.shifts(shifted))
        val task = Plans.tasks(Plans.setTaskDay(timeline, 0, "to", "2026-10-12", by = 1, at = 1.0))[0]
        assertEquals("2026-10-12", task.optString("to"))
        assertTrue(!task.has("moved"))
        assertTrue(Plans.timelineRange(shifted, today).second >= LocalDate.of(2026, 11, 9))
        val back = Plans.setTaskDay(JSONObject("""{"tasks":[{"x":"M","from":"2026-09-14","to":"2026-09-14","m":true}]}"""), 0, "from", "2026-10-12", by = 1, at = 1.0)
        assertEquals(LocalDate.of(2026, 9, 14), Plans.timelineRange(back, today).first)
    }

    private fun cellsJson(plan: JSONObject) = "[" + Plans.cells(plan).joinToString(",") { row -> "[" + row.joinToString(",") { it?.toString() ?: "null" } + "]" } + "]"
    private fun rowJson(plan: JSONObject, r: Int) = "[" + Plans.cells(plan)[r].joinToString(",") { it?.toString() ?: "null" } + "]"
}
