package io.github.veritasx1.linotes.ui

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject
import java.io.File
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

/** Board report as PDF – same content as linux/linotes/report.py: a simple list
 *  for ordinary boards, a traceability matrix plus card details for development projects. */
object Report {

    class Row(
        val id: String, val title: String, val notes: String, val status: String, val priority: String,
        val assignee: String, val due: String, val created: String, val done: String, val commits: List<Pair<String, String>>,
        val impact: String, val verification: String, val version: String, val accepted: String,
        val history: List<Triple<String, String, String>>, val columnId: String,
        val files: String = "",
    )

    class Data(val title: String, val dev: Boolean, val generated: String, val columns: List<Pair<String, List<Row>>>, val rows: List<Row>)

    private fun stamp(seconds: Double): String {
        if (seconds <= 0) return ""
        val moment = Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault())
        return "%02d.%02d.%d %02d:%02d".format(moment.dayOfMonth, moment.monthValue, moment.year, moment.hour, moment.minute)
    }

    private fun SyncObject.text(key: String) = data.optString(key).takeIf { it != "null" }.orEmpty()

    fun build(sync: SyncEngine, boardId: String): Data {
        val board = sync.get(boardId)
        val columns = sync.all("column").filter { it.data.optString("board") == boardId }.sortedBy { it.data.optDouble("order", 0.0) }
        val last = columns.lastOrNull()?.id
        val position = columns.mapIndexed { index, column -> column.id to index }.toMap()
        val names = columns.associate { it.id to it.data.optString("name") }
        val cards = sync.all("card").filter { it.data.optString("board") == boardId && !it.data.optBoolean("archived") }
            .sortedWith(compareBy({ position[it.data.optString("column")] ?: 99 }, { it.data.optDouble("order", 0.0) }))
        val rows = cards.map { card ->
            val history = card.data.optJSONArray("history")
            val steps = (0 until (history?.length() ?: 0)).map { history!!.getJSONObject(it) }
            val accepted = if (card.data.optString("column") == last) steps.lastOrNull { it.optString("c") == last } else null
            val commits = card.data.optJSONArray("commits")
            Row(
                id = shortId(card.id), title = card.text("title"), notes = card.text("notes"),
                status = names[card.data.optString("column")].orEmpty(),
                priority = PRIORITIES.firstOrNull { it.first.isNotEmpty() && it.first == card.text("priority") }?.second.orEmpty(),
                assignee = card.data.optInt("assignee").takeIf { it != 0 }?.let { sync.userName(it) }.orEmpty(),
                due = runCatching { LocalDate.parse(card.text("due")) }.getOrNull()?.let { "%02d.%02d.%d".format(it.dayOfMonth, it.monthValue, it.year) }.orEmpty(),
                created = stamp(card.data.optDouble("created", 0.0)), done = stamp(card.data.optDouble("done_at", 0.0)),
                commits = (0 until (commits?.length() ?: 0)).map { commits!!.getJSONObject(it).let { c -> c.optString("h") to c.optString("s") } },
                impact = card.text("impact"), verification = card.text("verification"), version = card.text("version"),
                accepted = accepted?.let { "${sync.userName(it.optInt("by"))}, ${stamp(it.optDouble("at", 0.0))}" }.orEmpty(),
                history = steps.map { Triple(it.optString("n"), stamp(it.optDouble("at", 0.0)), sync.userName(it.optInt("by"))) },
                columnId = card.data.optString("column"),
                files = cardFiles(card.data).joinToString(", ") { it.optString("n") },
            )
        }
        val now = LocalDateTime.now()
        return Data(
            title = board?.data?.optString("name") ?: "Board", dev = isDevBoard(board),
            generated = "%02d.%02d.%d %02d:%02d".format(now.dayOfMonth, now.monthValue, now.year, now.hour, now.minute),
            columns = columns.map { column -> column.data.optString("name") to rows.filter { it.columnId == column.id } },
            rows = rows,
        )
    }

    /** A tiny flowing layout: paragraphs and tables with page breaks (A4, points). */
    class Pdf(landscape: Boolean, private val header: String) {
        val width = if (landscape) 842 else 595
        val height = if (landscape) 595 else 842
        val margin = 48f
        val document = PdfDocument()
        var pageNumber = 0
        lateinit var page: PdfDocument.Page
        val canvas: Canvas get() = page.canvas
        var y = margin
        val accent = Color.rgb(184, 125, 0)
        val grey = Color.rgb(107, 107, 115)
        val line = Color.rgb(217, 217, 222)

        init { newPage(first = true) }

        fun paint(size: Float, bold: Boolean = false, color: Int = Color.BLACK, mono: Boolean = false) = TextPaint().apply {
            isAntiAlias = true; textSize = size; this.color = color
            // Unhinted glyph positions: no odd word spacing at small sizes in the PDF.
            isLinearText = true; isSubpixelText = true
            typeface = when { mono -> Typeface.MONOSPACE; bold -> Typeface.DEFAULT_BOLD; else -> Typeface.DEFAULT }
        }

        fun layout(text: CharSequence, paint: TextPaint, width: Float): StaticLayout =
            StaticLayout.Builder.obtain(text, 0, text.length, paint, width.toInt().coerceAtLeast(10))
                .setAlignment(Layout.Alignment.ALIGN_NORMAL).build()

        fun footer() {
            canvas.drawText("$header · Seite $pageNumber", margin, height - margin + 22, paint(7.5f, color = grey))
        }

        fun newPage(first: Boolean = false) {
            if (!first) { footer(); document.finishPage(page) }
            pageNumber++
            page = document.startPage(PdfDocument.PageInfo.Builder(width, height, pageNumber).create())
            y = margin
        }

        fun need(space: Float) { if (y + space > height - margin) newPage() }

        fun text(text: String, size: Float = 10f, bold: Boolean = false, color: Int = Color.BLACK, space: Float = 4f, mono: Boolean = false) {
            val layout = layout(text, paint(size, bold, color, mono), width - 2 * margin)
            need(layout.height.toFloat())
            canvas.save(); canvas.translate(margin, y); layout.draw(canvas); canvas.restore()
            y += layout.height + space
        }

        /** A note line: styled text, optionally indented with a list mark in front. */
        fun styled(text: CharSequence, size: Float, bold: Boolean, italic: Boolean, color: Int, mono: Boolean,
                   indent: Float, space: Float, mark: String?, markColor: Int, bar: Boolean) {
            val textPaint = paint(size, bold, color, mono)
            if (italic) textPaint.typeface = Typeface.create(textPaint.typeface, if (bold) Typeface.BOLD_ITALIC else Typeface.ITALIC)
            val layout = layout(if (text.isEmpty()) " " else text, textPaint, width - 2 * margin - indent)
            need(layout.height.toFloat())
            val x = margin + indent
            if (mark != null) canvas.drawText(mark, x - 16, y - textPaint.ascent(), paint(size, color = markColor))
            if (bar) canvas.drawRect(x - 10, y, x - 7.5f, y + layout.height, Paint().apply { this.color = line })
            canvas.save(); canvas.translate(x, y); layout.draw(canvas); canvas.restore()
            y += layout.height + space
        }

        fun image(bitmap: android.graphics.Bitmap) {
            val scale = minOf((width - 2 * margin) / bitmap.width, 360f / bitmap.height, 1f)
            val w = bitmap.width * scale
            val h = bitmap.height * scale
            need(h)
            canvas.drawBitmap(bitmap, null, android.graphics.RectF(margin, y, margin + w, y + h), Paint().apply { isFilterBitmap = true })
            y += h + 8
        }

        fun rule(space: Float = 8f) {
            canvas.drawLine(margin, y, width - margin, y, Paint().apply { color = line; strokeWidth = 0.6f })
            y += space
        }

        fun table(headers: List<String>, weights: List<Float>, rows: List<List<String>>, size: Float = 8f, mono: Set<Int> = emptySet()) {
            val total = width - 2 * margin
            val widths = weights.map { it * total / weights.sum() }
            val pad = 3f
            fun layouts(cells: List<String>, bold: Boolean) = cells.mapIndexed { index, cell ->
                layout(cell, paint(size, bold, if (bold) grey else Color.BLACK, mono = index in mono && !bold), widths[index] - 2 * pad)
            }
            fun drawRow(cells: List<StaticLayout>, shade: Boolean) {
                val rowHeight = cells.maxOf { it.height } + 2 * pad
                if (y + rowHeight > height - margin) { newPage(); drawRow(layouts(headers, true), true) }
                if (shade) canvas.drawRect(margin, y, margin + total, y + rowHeight, Paint().apply { color = Color.rgb(242, 242, 245) })
                var x = margin
                cells.forEachIndexed { index, cell ->
                    canvas.save(); canvas.translate(x + pad, y + pad); cell.draw(canvas); canvas.restore()
                    x += widths[index]
                }
                y += rowHeight
                canvas.drawLine(margin, y, margin + total, y, Paint().apply { color = line; strokeWidth = 0.4f })
            }
            drawRow(layouts(headers, true), true)
            rows.forEach { drawRow(layouts(it, false), false) }
            y += 10
        }

        fun finish(file: File) {
            footer(); document.finishPage(page)
            file.outputStream().use { document.writeTo(it) }
            document.close()
        }
    }

    fun writePdf(report: Data, file: File) {
        val pdf = Pdf(report.dev, "${report.title} · Stand ${report.generated}")
        pdf.text((if (report.dev) "Entwicklungsprojekt – Nachverfolgung" else "Aufgaben-Board").uppercase(), 8f, true, pdf.accent, 2f)
        pdf.text(report.title, 20f, true, space = 2f)
        val counts = report.columns.joinToString(" · ") { "${it.first}: ${it.second.size}" }
        pdf.text("Stand ${report.generated} · ${report.rows.size} Karten · $counts", 9f, color = pdf.grey, space = 12f)
        pdf.rule()
        if (report.dev) {
            pdf.text("Traceability-Matrix", 13f, true, space = 6f)
            pdf.table(listOf("ID", "Titel", "Prio", "Status", "Commits", "Verifikation", "Version", "Abnahme"),
                listOf(8f, 29f, 6f, 11f, 11f, 19f, 8f, 13f),
                report.rows.map { listOf(it.id, it.title, it.priority, it.status, it.commits.joinToString(", ") { c -> c.first },
                    it.verification, it.version, it.accepted) }, mono = setOf(0, 4))
            pdf.text("Karten im Einzelnen", 13f, true, space = 6f)
            for (row in report.rows) {
                pdf.need(60f)
                pdf.rule(6f)
                pdf.text("[${row.id}]  ${row.title}", 11f, true, space = 2f)
                val facts = listOf("Status: ${row.status}") + listOf("Priorität" to row.priority, "Zuständig" to row.assignee,
                    "Erstellt" to row.created, "Erledigt" to row.done, "Version" to row.version, "Abnahme" to row.accepted)
                    .filter { it.second.isNotEmpty() }.map { "${it.first}: ${it.second}" }
                pdf.text(facts.joinToString(" · "), 8.5f, color = pdf.grey, space = 6f)
                for ((label, value) in listOf("Beschreibung" to row.notes, "Auswirkungsanalyse" to row.impact, "Verifikation" to row.verification)) {
                    if (value.isNotBlank()) { pdf.text(label, 9f, true, space = 1f); pdf.text(value.trim(), 9f, space = 5f) }
                }
                if (row.files.isNotEmpty()) {
                    pdf.text("Anhänge", 9f, true, space = 1f)
                    pdf.text(row.files, 8.5f, space = 5f)
                }
                if (row.commits.isNotEmpty()) {
                    pdf.text("Commits", 9f, true, space = 1f)
                    row.commits.forEach { pdf.text("${it.first}  ${it.second}", 8.5f, space = 1f) }
                    pdf.y += 4
                }
                if (row.history.isNotEmpty()) {
                    pdf.text("Verlauf", 9f, true, space = 1f)
                    row.history.forEach { pdf.text("${it.second}  ${it.first}  (${it.third})", 8.5f, color = pdf.grey, space = 1f) }
                    pdf.y += 4
                }
            }
        } else {
            for ((name, items) in report.columns) {
                pdf.text("$name (${items.size})", 13f, true, space = 6f)
                if (items.isEmpty()) pdf.text("Keine Karten", 9f, color = pdf.grey, space = 10f)
                else pdf.table(listOf("Titel", "Priorität", "Zuständig", "Fällig", "Erledigt"), listOf(42f, 11f, 15f, 14f, 18f),
                    items.map { listOf(it.title, it.priority, it.assignee, it.due, it.done) })
            }
        }
        pdf.finish(file)
    }

    /** Write the report into the cache and hand it to the share sheet. */
    fun share(state: AppState, context: android.content.Context, boardId: String) {
        val data = build(state.sync, boardId)
        val folder = File(context.cacheDir, "reports").apply { mkdirs() }
        val today = LocalDate.now()
        val file = File(folder, "${data.title.replace(Regex("[/\\\\:*?\"<>|]"), "_")} – Stand %04d-%02d-%02d.pdf".format(today.year, today.monthValue, today.dayOfMonth))
        writePdf(data, file)
        state.shareFile(file, "application/pdf", "Bericht: ${data.title}")
    }
}
