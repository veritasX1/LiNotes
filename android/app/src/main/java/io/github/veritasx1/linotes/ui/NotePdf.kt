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
    fun styledText(block: JSONObject): CharSequence {
        val text = block.optString("x")
        val spans = block.optJSONArray("s") ?: return text
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
                // Links to other notes look like links (accent color, underlined).
                else -> if (span.optString(2).startsWith("n:")) {
                    result.setSpan(ForegroundColorSpan(Color.rgb(184, 125, 0)), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    UnderlineSpan()
                } else continue
            }
            result.setSpan(style, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
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
