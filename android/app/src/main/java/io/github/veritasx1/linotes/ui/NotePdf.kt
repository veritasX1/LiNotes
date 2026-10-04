package io.github.veritasx1.linotes.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.PrintManager
import android.text.SpannableString
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.StrikethroughSpan
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan
import org.json.JSONObject
import java.io.File

/** A single note as PDF (same look as linux/linotes/report.py write_note_pdf): for sharing and printing. */
object NotePdf {

    private class Style(val size: Float, val bold: Boolean, val italic: Boolean, val space: Float)

    private val styles = mapOf(
        "title" to Style(20f, true, false, 8f), "heading" to Style(15f, true, false, 5f),
        "subheading" to Style(12.5f, true, false, 4f), "body" to Style(10.5f, false, false, 3f),
        "mono" to Style(9.5f, false, false, 3f), "quote" to Style(10.5f, false, true, 3f),
    )
    private val marks = mapOf("bullet" to "•", "dash" to "–", "number" to "", "check" to "○")

    /** The line's text with its bold/italic/underline/strike/highlight spans. */
    private fun alignment(block: JSONObject) = when (block.optString("a")) {
        "center" -> android.text.style.AlignmentSpan.Standard(android.text.Layout.Alignment.ALIGN_CENTER)
        "right" -> android.text.style.AlignmentSpan.Standard(android.text.Layout.Alignment.ALIGN_OPPOSITE)
        else -> null
    }

    fun styledText(block: JSONObject): CharSequence {
        val text = block.optString("x")
        val spans = block.optJSONArray("s")
            ?: return alignment(block)?.let { SpannableString(text).apply { setSpan(it, 0, length, Spanned.SPAN_INCLUSIVE_INCLUSIVE) } } ?: text
        val result = SpannableString(text)
        for (index in 0 until spans.length()) {
            val span = spans.optJSONArray(index) ?: continue
            if (span.length() < 3) continue
            val start = span.optInt(0).coerceIn(0, text.length)
            val end = span.optInt(1).coerceIn(start, text.length)
            if (start == end) continue
            val style: Any = when (span.optString(2)) {
                "b" -> StyleSpan(Typeface.BOLD)
                "i" -> StyleSpan(Typeface.ITALIC)
                "u" -> UnderlineSpan()
                "s" -> StrikethroughSpan()
                "h" -> BackgroundColorSpan(Color.rgb(255, 230, 128))
                "h:orange" -> BackgroundColorSpan(Color.rgb(255, 207, 133))
                "h:pink" -> BackgroundColorSpan(Color.rgb(255, 183, 211))
                "h:purple" -> BackgroundColorSpan(Color.rgb(223, 188, 247))
                "h:mint" -> BackgroundColorSpan(Color.rgb(165, 236, 224))
                "h:blue" -> BackgroundColorSpan(Color.rgb(172, 227, 252))
                in TEXT_COLORS -> ForegroundColorSpan(Color.rgb(TEXT_COLORS.getValue(span.optString(2)) shr 16 and 0xFF,
                    TEXT_COLORS.getValue(span.optString(2)) shr 8 and 0xFF, TEXT_COLORS.getValue(span.optString(2)) and 0xFF))
                in FONTS -> android.text.style.TypefaceSpan(FONTS.getValue(span.optString(2)))
                // Links to other notes look like links (accent color, underlined).
                else -> if (span.optString(2).startsWith("n:")) {
                    result.setSpan(ForegroundColorSpan(Color.rgb(184, 125, 0)), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    UnderlineSpan()
                } else continue
            }
            result.setSpan(style, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        alignment(block)?.let { result.setSpan(it, 0, result.length, Spanned.SPAN_INCLUSIVE_INCLUSIVE) }
        return result
    }

    fun write(blocks: List<JSONObject>, header: String, file: File, image: (String) -> Bitmap?) {
        val pdf = Report.Pdf(false, header)
        val numbers = mutableMapOf<Int, Int>()
        for (block in blocks) {
            val kind = block.optString("t", "body")
            val level = block.optInt("l", 0)
            if (kind == "image") {
                block.optString("f").takeIf { it.isNotEmpty() }?.let(image)?.let { pdf.image(it) }
                numbers.clear()
                continue
            }
            if (kind == "file") {
                // Attachments are listed with name and size (their content is not part of the PDF).
                pdf.styled("📎 ${block.optString("n", "Datei")}  (${fileDetails(block)})", 10.5f, false, false, color = pdf.grey,
                    mono = false, indent = 0f, space = 6f, mark = null, markColor = Color.BLACK, bar = false)
                numbers.clear()
                continue
            }
            if (kind == "link") {
                // A link preview: its title and the address (the address stays readable on paper).
                val title = block.optString("n").ifEmpty { block.optString("dm") }
                pdf.styled("🔗 $title – ${block.optString("u").ifEmpty { block.optString("x") }}", 10.5f, false, false, color = pdf.grey,
                    mono = false, indent = 0f, space = 6f, mark = null, markColor = Color.BLACK, bar = false)
                numbers.clear()
                continue
            }
            if (kind == "table") {
                // Rows with thin lines, each row kept on one page (same as Ubuntu).
                val rows = io.github.veritasx1.linotes.data.Model.tableRows(block)
                val columnWidth = (pdf.width - 2 * pdf.margin) / rows[0].size
                val line = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
                    style = android.graphics.Paint.Style.STROKE; strokeWidth = 0.8f; color = Color.rgb(217, 217, 222) }
                for (row in rows) {
                    val cells = row.map { pdf.layout(it, pdf.paint(10.5f), columnWidth - 10f) }
                    val height = cells.maxOf { it.height } + 10f
                    pdf.need(height)
                    cells.forEachIndexed { index, cell ->
                        val left = pdf.margin + index * columnWidth
                        pdf.canvas.drawRect(left, pdf.y, left + columnWidth, pdf.y + height, line)
                        pdf.canvas.save()
                        pdf.canvas.translate(left + 5f, pdf.y + 5f)
                        cell.draw(pdf.canvas)
                        pdf.canvas.restore()
                    }
                    pdf.y += height
                }
                pdf.y += 8f
                numbers.clear()
                continue
            }
            if (kind == "divider") {
                pdf.need(16f)
                pdf.y += 7f
                pdf.rule(9f)
                numbers.clear()
                continue
            }
            if (kind == "number") {
                numbers[level] = (numbers[level] ?: 0) + 1
                numbers.keys.filter { it > level }.forEach { numbers.remove(it) }
            } else if (kind !in marks) numbers.clear()
            val style = styles[kind] ?: styles.getValue("body")
            val done = kind == "check" && block.optBoolean("c")
            var text = styledText(block)
            if (done) text = SpannableString(text).apply { setSpan(StrikethroughSpan(), 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE) }
            val mark = when {
                kind == "number" -> "${numbers[level] ?: 1}."
                done -> "☑"
                else -> marks[kind]
            }
            pdf.styled(text, style.size, style.bold, style.italic,
                color = if (kind == "quote" || done) pdf.grey else Color.BLACK, mono = kind == "mono",
                indent = 18f * level + (if (kind in marks) 18f else 0f) + (if (kind == "quote") 14f else 0f),
                space = style.space, mark = mark, markColor = if (kind == "check") pdf.accent else Color.BLACK, bar = kind == "quote")
        }
        pdf.finish(file)
    }

    fun fileName(title: String) = title.replace(Regex("[/\\\\:*?\"<>|]"), "_").take(80).ifBlank { "Notiz" } + ".pdf"

    /** The system print dialog for an already written PDF. */
    fun print(context: Context, file: File, title: String) {
        val manager = context.getSystemService(Context.PRINT_SERVICE) as PrintManager
        manager.print(title, object : PrintDocumentAdapter() {
            override fun onLayout(old: PrintAttributes?, new: PrintAttributes, cancel: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?) {
                if (cancel.isCanceled) { callback.onLayoutCancelled(); return }
                callback.onLayoutFinished(PrintDocumentInfo.Builder(file.name).setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).build(), old != new)
            }

            override fun onWrite(pages: Array<out PageRange>, destination: ParcelFileDescriptor, cancel: CancellationSignal, callback: WriteResultCallback) {
                try {
                    file.inputStream().use { input -> java.io.FileOutputStream(destination.fileDescriptor).let { input.copyTo(it); it.flush() } }
                    callback.onWriteFinished(arrayOf(PageRange.ALL_PAGES))
                } catch (error: Exception) {
                    callback.onWriteFailed(error.message)
                }
            }
        }, null)
    }
}
