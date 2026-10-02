package io.github.veritasx1.linotes.ui

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.BitmapDrawable
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.Drawable
import android.text.Editable
import android.text.InputType
import android.text.Layout
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.TextPaint
import android.text.TextWatcher
import android.text.style.BackgroundColorSpan
import android.text.style.ImageSpan
import android.text.style.LeadingMarginSpan
import android.text.style.LineHeightSpan
import android.text.style.MetricAffectingSpan
import android.text.style.StrikethroughSpan
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.widget.EditText
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream

private const val OBJECT = '￼'
val LIST_TYPES = setOf("bullet", "dash", "number", "check")

/** An empty list item holds this invisible character: Android draws no marker for a line
 *  without characters, and a zero-length span at the end also indents the line above. */
const val PLACEHOLDER = '\u200B'

/** Web addresses that become tappable links (trailing punctuation is not part of the address). */
private val LINK = Regex("""(?:https?://|www\.)[^\s<>"']+[^\s<>"'.,;:!?)\]]""")

/** How a web address looks: accent color, underlined. Not saved – found again on every change. */
class LinkSpan(private val color: Int) : android.text.style.CharacterStyle(), android.text.style.UpdateAppearance {
    override fun updateDrawState(paint: TextPaint) {
        paint.color = color
        paint.isUnderlineText = true
    }
}
/** A link to another note (">>"), saved as span "n:<id>". Looks like a web address. */
class NoteLinkSpan(val noteId: String, private val color: Int) : android.text.style.CharacterStyle(), android.text.style.UpdateAppearance {
    override fun updateDrawState(paint: TextPaint) {
        paint.color = color
        paint.isUnderlineText = true
    }
}

const val MAX_INDENT = 4

/** Paragraph style: size/weight of the text plus the list marker in the margin. */
class ParaSpan(
    val type: String,
    val level: Int,
    val checked: Boolean,
    private val density: Float,
    private val colors: EditorColors,
) : MetricAffectingSpan(), LeadingMarginSpan, LineHeightSpan, android.text.style.AlignmentSpan {

    var number = 1
    /** Paragraph alignment like Format → Text in Notes: null (left), "center", "right". */
    var align: String? = null

    override fun getAlignment(): Layout.Alignment = when (align) {
        "center" -> Layout.Alignment.ALIGN_CENTER
        "right" -> Layout.Alignment.ALIGN_OPPOSITE
        else -> Layout.Alignment.ALIGN_NORMAL
    }
    /** Headings with content below: 0 not foldable, 1 open (⌄), 2 collapsed (›). */
    var fold = 0

    /** Headings get some air above them (not at the very top of the note). */
    override fun chooseHeight(text: CharSequence, start: Int, end: Int, spanstartv: Int, lineHeight: Int, fm: Paint.FontMetricsInt) {
        val extra = when (type) { "heading" -> 16; "subheading" -> 10; else -> return }
        if (start == 0 || text !is Spanned || start != text.getSpanStart(this)) return
        val add = (extra * density).toInt()
        fm.ascent -= add
        fm.top -= add
    }

    private fun apply(paint: TextPaint) {
        when (type) {
            "title" -> { paint.textSize *= 1.75f; paint.typeface = Typeface.create(paint.typeface, Typeface.BOLD) }
            "heading" -> { paint.textSize *= 1.35f; paint.typeface = Typeface.create(paint.typeface, Typeface.BOLD) }
            "subheading" -> { paint.textSize *= 1.12f; paint.typeface = Typeface.create(paint.typeface, Typeface.BOLD) }
            "mono" -> { paint.textSize *= 0.92f; paint.typeface = Typeface.MONOSPACE }
            "quote" -> { paint.typeface = Typeface.create(paint.typeface, Typeface.ITALIC); paint.color = colors.secondary }
        }
        if (type == "check" && checked) paint.color = colors.secondary
    }

    override fun updateMeasureState(paint: TextPaint) = apply(paint)
    override fun updateDrawState(paint: TextPaint) = apply(paint)

    override fun getLeadingMargin(first: Boolean): Int = when {
        fold != 0 -> (20 * density).toInt()
        type in LIST_TYPES -> ((30 + 24 * level) * density).toInt()
        type == "quote" -> (16 * density).toInt()
        else -> 0
    }

    override fun drawLeadingMargin(
        canvas: Canvas, paint: Paint, x: Int, dir: Int, top: Int, baseline: Int, bottom: Int,
        text: CharSequence, start: Int, end: Int, first: Boolean, layout: Layout,
    ) {
        if (!first || (text is Spanned && text.getSpanStart(this) != start)) {
            if (type == "quote" && text is Spanned) drawQuoteBar(canvas, x, top, bottom)
            return
        }
        val center = x + ((24 * level + 13) * density)
        val saved = paint.color
        val style = paint.style
        val middle = (top + baseline) / 2f + density
        when (type) {
            "check" -> {
                val radius = 9.5f * density
                if (checked) {
                    paint.color = colors.accent
                    paint.style = Paint.Style.FILL
                    canvas.drawCircle(center, middle, radius, paint)
                    paint.color = 0xFFFFFFFF.toInt()
                    paint.style = Paint.Style.STROKE
                    paint.strokeWidth = 2f * density
                    paint.strokeCap = Paint.Cap.ROUND
                    val path = android.graphics.Path().apply {
                        moveTo(center - 4.3f * density, middle + 0.2f * density)
                        lineTo(center - 1.2f * density, middle + 3.3f * density)
                        lineTo(center + 4.6f * density, middle - 3.4f * density)
                    }
                    canvas.drawPath(path, paint)
                } else {
                    paint.color = colors.tertiary
                    paint.style = Paint.Style.STROKE
                    paint.strokeWidth = 1.5f * density
                    canvas.drawCircle(center, middle, radius, paint)
                }
            }
            "bullet" -> {
                paint.color = colors.label
                paint.style = Paint.Style.FILL
                canvas.drawCircle(center, middle, 3f * density, paint)
            }
            "dash" -> {
                paint.color = colors.label
                paint.style = Paint.Style.FILL
                canvas.drawRect(center - 5 * density, middle - 0.8f * density, center + 4 * density, middle + 0.8f * density, paint)
            }
            "number" -> {
                paint.color = colors.label
                paint.style = Paint.Style.FILL
                val label = "$number."
                canvas.drawText(label, center + 6 * density - paint.measureText(label), baseline.toFloat(), paint)
            }
            "quote" -> drawQuoteBar(canvas, x, top, bottom)
        }
        if (fold != 0) {
            // Like Apple: a chevron before headings that can be collapsed.
            paint.color = colors.accent
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 2f * density
            paint.strokeCap = Paint.Cap.ROUND
            val cx = x + 8 * density
            val cy = (top + bottom) / 2f
            val path = android.graphics.Path().apply {
                if (fold == 2) { moveTo(cx - 2.5f * density, cy - 5 * density); lineTo(cx + 2.5f * density, cy); lineTo(cx - 2.5f * density, cy + 5 * density) }
                else { moveTo(cx - 5 * density, cy - 2.5f * density); lineTo(cx, cy + 2.5f * density); lineTo(cx + 5 * density, cy - 2.5f * density) }
            }
            canvas.drawPath(path, paint)
        }
        paint.color = saved
        paint.style = style
    }

    private fun drawQuoteBar(canvas: Canvas, x: Int, top: Int, bottom: Int) {
        val paint = Paint().apply { color = colors.tertiary }
        canvas.drawRect(x + 2 * density, top.toFloat(), x + 5 * density, bottom.toFloat(), paint)
    }
}

/** Highlight marking in one of the colors of Apple's Notes ("h" = yellow, "h:pink", …). */
class HighlightSpan(val name: String, color: Int) : BackgroundColorSpan(color)

/** Highlight colors (RGB) like in Apple's Notes; "h" (yellow) is the original one and uses the theme color. */
val HIGHLIGHTS = linkedMapOf(
    "h" to 0xFFD83D, "h:orange" to 0xFF9F0A, "h:pink" to 0xFF70A8,
    "h:purple" to 0xBF7AF0, "h:mint" to 0x4CD9C0, "h:blue" to 0x5AC8FA,
)

/** A divider: an object character on a line of its own, drawn as a thin line across the editor. */
class DividerSpan(private val density: Float, private val color: Int, private val width: () -> Int) : android.text.style.ReplacementSpan() {
    override fun getSize(paint: Paint, text: CharSequence, start: Int, end: Int, fm: Paint.FontMetricsInt?): Int {
        fm?.let {
            val half = (8 * density).toInt()
            it.ascent = -half; it.top = -half; it.descent = half; it.bottom = half
        }
        return width().coerceAtLeast(1)
    }

    override fun draw(canvas: Canvas, text: CharSequence, start: Int, end: Int, x: Float, top: Int, y: Int, bottom: Int, paint: Paint) {
        val line = Paint().apply { color = this@DividerSpan.color; strokeWidth = density }
        val middle = (top + bottom) / 2f
        canvas.drawLine(x, middle, x + width(), middle, line)
    }
}

/** The content of a collapsed section, taken out of the text while it is folded (EditText
 *  cannot hide text); sits on the heading and is put back by toBlocks/expanding. */
class FoldSpan(val hidden: List<JSONObject>)

private val FOLDABLE = mapOf("heading" to 1, "subheading" to 2)
private val RANKS = mapOf("title" to 0, "heading" to 1, "subheading" to 2)

/** Index of the last block in the section of the heading at [index] (index itself if empty).
 *  Trailing empty lines stay outside, as on Ubuntu. */
fun sectionEnd(types: List<String>, texts: List<String>, index: Int): Int {
    val rank = FOLDABLE[types[index]] ?: return index
    var last = index
    for (other in index + 1 until types.size) {
        val otherRank = RANKS[types[other]]
        if (otherRank != null && otherRank <= rank) break
        last = other
    }
    while (last > index && types[last] !in setOf("image", "divider") && texts[last].isBlank()) last--
    return last
}

/** Text colors like in Apple's Notes and a choice of fonts (same names as on Ubuntu). */
val TEXT_COLORS = linkedMapOf("c:purple" to 0x9B51E0, "c:pink" to 0xE0457F, "c:orange" to 0xE07A00, "c:mint" to 0x12A594, "c:blue" to 0x1C8CE0)
val FONTS = linkedMapOf("f:serif" to "serif", "f:mono" to "monospace")
class TextColorSpan(val name: String, color: Int) : android.text.style.ForegroundColorSpan(color)
class FontSpan(val name: String, family: String) : android.text.style.TypefaceSpan(family)

/** A result filled in after "=" (accent color until the note is opened again). */
class CalcSpan(color: Int) : android.text.style.ForegroundColorSpan(color)

/** An attached file (block {"t": "file", "f", "n", "m", "b"}) drawn as a card like in Notes. */
class FileBlockSpan(val block: JSONObject, drawable: Drawable) : ImageSpan(drawable, ALIGN_BOTTOM)

/** "PDF-Dokument · 1,2 MB" – the same wording as on Ubuntu where possible. */
fun fileDetails(block: JSONObject): String {
    val size = block.optLong("b")
    val amount = when {
        size >= 1024 * 1024 -> String.format(java.util.Locale.GERMANY, "%.1f MB", size / 1024.0 / 1024.0)
        size >= 1024 -> "${Math.round(size / 1024.0)} KB"
        else -> "$size Bytes"
    }
    val mime = block.optString("m")
    val name = block.optString("n")
    val kind = when {
        mime == "application/pdf" -> "PDF-Dokument"
        mime.startsWith("image/") -> "Bild"
        mime.startsWith("audio/") -> "Audio"
        mime.startsWith("video/") -> "Video"
        mime.startsWith("text/") -> "Textdokument"
        "wordprocessing" in mime || "msword" in mime || "opendocument.text" in mime -> "Textdokument"
        "spreadsheet" in mime || "ms-excel" in mime -> "Tabelle"
        "presentation" in mime || "powerpoint" in mime -> "Präsentation"
        "zip" in mime -> "ZIP-Archiv"
        '.' in name -> name.substringAfterLast('.').uppercase() + "-Datei"
        else -> "Datei"
    }
    return "$kind · $amount"
}

class ImageBlockSpan(val fileId: String, drawable: Drawable) : ImageSpan(drawable, ALIGN_BOTTOM)

data class EditorColors(val label: Int, val secondary: Int, val tertiary: Int, val accent: Int, val highlight: Int)

/**
 * Note editor on top of EditText. Mirrors linux/linotes/editor.py: the text is
 * plain, paragraph styles are [ParaSpan]s (one per paragraph), inline styles
 * are standard spans, images are [ImageBlockSpan]s on an object character.
 */
@SuppressLint("ViewConstructor")
class RichEditor(context: Context, private var colors: EditorColors, private val loadImage: (String, (Bitmap?) -> Unit) -> Unit) :
    EditText(context) {

    private val density = resources.displayMetrics.density
    private var busy = false
    private var enterAt = -1
    private var enterStyle: ParaSpan? = null
    private var deletedBreakAt = -1
    private var deletedPlaceholderAt = -1
    private var deletedBreakStyle: ParaSpan? = null
    var pendingInline: MutableSet<String>? = null
    var onEdited: (() -> Unit)? = null
    var onStyleChanged: (() -> Unit)? = null
    /** The cursor moved (typing, tapping, new line) – the screen keeps it above the keyboard. */
    var onCaretMoved: (() -> Unit)? = null
    var autoSortChecked = false
    /** Title of a note by id (null if it is gone) – note links show the current title. */
    var noteTitle: (String) -> String? = { null }
    /** ">>" was typed: the screen offers notes to link to. */
    var onLinkRequested: (() -> Unit)? = null
    var onOpenNote: ((String) -> Unit)? = null
    var onOpenFile: ((JSONObject) -> Unit)? = null
    /** First page of an attached PDF for its card (null: no preview). */
    var loadFilePreview: ((JSONObject, (Bitmap?) -> Unit) -> Unit)? = null
    /** Where the pending ">>" starts, or -1. */
    private var linkStart = -1

    init {
        background = ColorDrawable(0)
        gravity = Gravity.TOP or Gravity.START
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
        setTextColor(colors.label)
        setLineSpacing(3 * density, 1f)
        inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or
            InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        isSingleLine = false
        setHorizontallyScrolling(false)
        setPadding((16 * density).toInt(), (4 * density).toInt(), (16 * density).toInt(), (160 * density).toInt())
        addTextChangedListener(object : TextWatcher {
            private var insertStart = 0
            private var insertCount = 0
            override fun beforeTextChanged(s: CharSequence, start: Int, count: Int, after: Int) {
                if (busy) return
                enterAt = -1
                deletedBreakAt = -1
                deletedPlaceholderAt = -1
                if (count == 1 && after == 0 && s[start] == PLACEHOLDER) {
                    // Backspace on an empty list item: remove the marker (like Notes).
                    deletedPlaceholderAt = start
                    deletedBreakStyle = paraAt(s as Spanned, start)
                }
                if (count == 1 && after == 0 && s[start] == '\n') {
                    // A line break is about to be deleted (backspace at a paragraph start).
                    deletedBreakAt = start
                    deletedBreakStyle = paraAt(s as Spanned, start + 1)
                }
            }

            override fun onTextChanged(s: CharSequence, start: Int, before: Int, count: Int) {
                if (busy) return
                insertStart = start
                insertCount = count
                // Enter – also when the keyboard commits the word being typed
                // together with the line break in one edit.
                val inserted = s.subSequence(start, start + count)
                if (count > before && inserted.count { it == '\n' } == 1) {
                    enterAt = start + inserted.indexOf('\n')
                    enterStyle = paraAt(s as Spanned, enterAt)
                }
            }

            override fun afterTextChanged(s: Editable) {
                if (busy) return
                busy = true
                try {
                    handleEdit(s, insertStart, insertCount)
                } finally {
                    busy = false
                }
                onEdited?.invoke()
            }
        })
        setOnTouchListener { _, event -> handleTouch(event) }
    }

    fun setColors(newColors: EditorColors) {
        colors = newColors
        setTextColor(colors.label)
        load(toBlocks())
    }

    // --- paragraphs ------------------------------------------------

    private fun paragraphStarts(text: CharSequence): List<Int> {
        val starts = mutableListOf(0)
        text.forEachIndexed { index, char -> if (char == '\n') starts.add(index + 1) }
        return starts
    }

    private fun paragraphEnd(text: CharSequence, start: Int): Int {
        val next = text.indexOf('\n', start)
        return if (next < 0) text.length else next
    }

    private fun paraAt(text: Spanned, offset: Int): ParaSpan? {
        val start = if (offset <= 0) 0 else text.lastIndexOf('\n', offset - 1).let { if (it < 0) 0 else it + 1 }
        return spanStartingAt(text, start)
    }

    /** The paragraph span of the paragraph beginning at [start]. Android also
     *  reports spans that merely touch the position, so check the start. */
    private fun spanStartingAt(text: Spanned, start: Int): ParaSpan? {
        val candidates = text.getSpans(start, (start + 1).coerceAtMost(text.length), ParaSpan::class.java)
        return candidates.firstOrNull { text.getSpanStart(it) == start }
            ?: candidates.firstOrNull { text.getSpanStart(it) < start && text.getSpanEnd(it) > start }
    }

    private fun makeSpan(type: String, level: Int = 0, checked: Boolean = false) =
        ParaSpan(type, if (type in LIST_TYPES) level.coerceIn(0, MAX_INDENT) else 0, checked && type == "check", density, colors)

    /** One ParaSpan per paragraph; applies the Enter/Backspace rules of Notes. */
    private fun handleEdit(text: Editable, insertStart: Int, insertCount: Int) {
        if (deletedPlaceholderAt >= 0) {
            val style = deletedBreakStyle
            val paragraphStart = text.lastIndexOf('\n', deletedPlaceholderAt - 1).let { if (it < 0) 0 else it + 1 }
            if (style != null && style.type in LIST_TYPES) {
                setPara(text, paragraphStart, if (style.level > 0) makeSpan(style.type, style.level - 1) else makeSpan("body"))
                normalize(text)
                return
            }
        }
        // Enter on a collapsed heading opens the section first (like Apple), then adds the line.
        if (enterAt >= 0 && enterStyle?.type in FOLDABLE) {
            val headingStart = text.lastIndexOf('\n', enterAt - 1).let { if (it < 0) 0 else it + 1 }
            if (foldAt(text, headingStart) != null) {
                text.delete(enterAt, enterAt + 1)
                normalize(text)
                post {
                    toggleFold(headingStart)
                    val current = this.text ?: return@post
                    current.insert(paragraphEnd(current, headingStart), "\n")
                }
                return
            }
        }
        // Enter on an empty list item ends the list instead of adding one.
        if (enterAt >= 0) {
            val style = enterStyle
            val paragraphStart = text.lastIndexOf('\n', enterAt - 1).let { if (it < 0) 0 else it + 1 }
            val content = text.substring(paragraphStart, enterAt).replace(OBJECT.toString(), "").replace(PLACEHOLDER.toString(), "")
            if ((style == null || style.type == "body") && content.trim() in setOf("---", "—-", "–-", "—", "___")) {
                // "---" and Enter becomes a divider (keyboards may turn "--" into a dash).
                text.replace(paragraphStart, enterAt, OBJECT.toString())
                text.setSpan(dividerSpan(), paragraphStart, paragraphStart + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                setSelection((paragraphStart + 2).coerceAtMost(text.length))
                normalize(text)
                return
            }
            if (style != null && style.type in LIST_TYPES && content.isBlank()) {
                text.delete(enterAt, enterAt + 1)
                setPara(text, paragraphStart, if (style.level > 0) makeSpan(style.type, style.level - 1) else makeSpan("body"))
                normalize(text)
                return
            }
        }
        // Backspace right after a divider removes the divider; after a photo it does nothing –
        // text joined into an object line would get lost.
        if (deletedBreakAt > 0 && text[deletedBreakAt - 1] == OBJECT) {
            val divider = text.getSpans(deletedBreakAt - 1, deletedBreakAt, DividerSpan::class.java).isNotEmpty()
            text.insert(deletedBreakAt, "\n")
            if (divider) {
                text.delete(deletedBreakAt - 1, deletedBreakAt + 1)
                setSelection(deletedBreakAt - 1)
            } else {
                setSelection(deletedBreakAt + 1)
            }
            normalize(text)
            return
        }
        // Backspace at the start of a list item removes the marker first.
        if (deletedBreakAt >= 0) {
            val style = deletedBreakStyle
            if (style != null && (style.type in LIST_TYPES || style.type == "quote")) {
                text.insert(deletedBreakAt, "\n")
                setSelection(deletedBreakAt + 1)
                setPara(text, deletedBreakAt + 1, if (style.level > 0) makeSpan(style.type, style.level - 1) else makeSpan("body"))
                normalize(text)
                return
            }
        }
        // Like Apple's Math Notes: "=" at the end of a line gets the result of the calculation.
        if (insertCount == 1 && insertStart < text.length && text[insertStart] == '=' &&
            (insertStart + 1 == text.length || text[insertStart + 1] == '\n')) {
            val at = insertStart + 1
            android.os.Handler(android.os.Looper.getMainLooper()).post { insertCalculation(at) }
        }
        // ">>" links to another note, like in Apple's Notes.
        val insertEnd = insertStart + insertCount
        if (linkStart < 0 && insertCount > 0 && insertEnd >= 2 && insertEnd <= text.length &&
            text[insertEnd - 1] == '>' && text[insertEnd - 2] == '>') {
            linkStart = insertEnd - 2
            post { onLinkRequested?.invoke() }
        }
        // New text takes the style that was switched on for typing.
        pendingInline?.let { styles ->
            if (insertCount > 0) {
                val end = (insertStart + insertCount).coerceAtMost(text.length)
                for (name in INLINE) removeInline(text, name, insertStart, end)
                for (name in styles) text.setSpan(inlineSpan(name), insertStart, end, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
            }
        }
        // Enter ends bold, highlight, …: the new line starts plain (like on Ubuntu); text that
        // was already behind the cursor keeps its style.
        if (enterAt >= 0) {
            for (name in INLINE) {
                if (hasInline(text, name, enterAt) || (enterAt > 0 && hasInline(text, name, enterAt - 1))) {
                    val after = (enterAt + 1 until text.length).takeWhile { hasInline(text, name, it) && text[it] != '\n' }
                    val keep = after.drop(insertStart + insertCount - enterAt - 1)
                    removeInline(text, name, enterAt, (enterAt + 1 + after.size).coerceAtMost(text.length))
                    if (keep.isNotEmpty()) text.setSpan(inlineSpan(name), keep.first(), keep.last() + 1, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
                }
            }
        }
        normalize(text)
    }

    private fun setPara(text: Editable, paragraphStart: Int, span: ParaSpan) {
        spanStartingAt(text, paragraphStart)?.let { old ->
            if (span.align == null) span.align = old.align
            text.removeSpan(old)
        }
        val end = paragraphEnd(text, paragraphStart)
        text.setSpan(span, paragraphStart, (end + 1).coerceAtMost(text.length), Spanned.SPAN_PARAGRAPH)
    }

    private fun normalize(text: Editable) {
        val starts = paragraphStarts(text)
        val styles = starts.mapIndexed { index, start ->
            val existing = spanStartingAt(text, start)
            when {
                enterAt >= 0 && start == enterAt + 1 -> {
                    // The paragraph created by Enter.
                    val previous = enterStyle
                    when (previous?.type) {
                        null -> makeSpan("body")
                        in LIST_TYPES -> makeSpan(previous.type, previous.level)
                        "title", "heading", "subheading" -> makeSpan("body")
                        else -> makeSpan(previous.type)
                    }
                }
                existing != null && text.getSpanStart(existing) == start -> makeSpan(existing.type, existing.level, existing.checked)
                // Only covered by the span of the paragraph above (text typed into
                // a new empty last line): follow the Enter rule of Notes.
                existing != null && index > 0 -> when (existing.type) {
                    in LIST_TYPES -> makeSpan(existing.type, existing.level)
                    "title", "heading", "subheading" -> makeSpan("body")
                    else -> makeSpan(existing.type)
                }
                existing != null -> makeSpan(existing.type, existing.level, existing.checked)
                index == 0 -> makeSpan("title")
                else -> makeSpan("body")
            }
        }
        // Alignment stays with its paragraph and carries on to the one created by Enter.
        starts.forEachIndexed { index, start ->
            styles[index].align = if (enterAt >= 0 && start == enterAt + 1) enterStyle?.align else spanStartingAt(text, start)?.align
        }
        // Empty list items get the placeholder, everything else loses it (back to front: offsets stay valid).
        for (index in starts.indices.reversed()) {
            val start = starts[index]
            val end = paragraphEnd(text, start)
            val content = text.substring(start, end)
            val bare = content.replace(PLACEHOLDER.toString(), "")
            if (styles[index].type in LIST_TYPES && bare.isEmpty()) {
                if (content.isEmpty()) {
                    val cursorHere = selectionStart == start
                    text.insert(start, PLACEHOLDER.toString())
                    // The cursor belongs behind the invisible character, so typing and backspace act on this item.
                    if (cursorHere) setSelection(start + 1)
                }
            } else if (bare.length != content.length) {
                for (offset in end - 1 downTo start) if (text[offset] == PLACEHOLDER) text.delete(offset, offset + 1)
            }
        }
        val fixedStarts = paragraphStarts(text)
        val types = fixedStarts.mapIndexed { index, start ->
            when {
                text.getSpans(start, paragraphEnd(text, start), DividerSpan::class.java).isNotEmpty() -> "divider"
                text.getSpans(start, paragraphEnd(text, start), ImageBlockSpan::class.java).isNotEmpty() -> "image"
                text.getSpans(start, paragraphEnd(text, start), FileBlockSpan::class.java).isNotEmpty() -> "image"
                else -> styles[index].type
            }
        }
        val texts = fixedStarts.map { text.substring(it, paragraphEnd(text, it)).replace(PLACEHOLDER.toString(), "") }
        fixedStarts.forEachIndexed { index, start ->
            styles[index].fold = when {
                styles[index].type !in FOLDABLE -> 0
                foldAt(text, start) != null -> 2
                sectionEnd(types, texts, index) > index -> 1
                else -> 0
            }
        }
        for (old in text.getSpans(0, text.length, ParaSpan::class.java)) text.removeSpan(old)
        var number = 0
        var previousWasNumber = false
        fixedStarts.forEachIndexed { index, start ->
            val span = styles[index]
            if (span.type == "number") {
                number = if (previousWasNumber) number + 1 else 1
                span.number = number
            }
            previousWasNumber = span.type == "number"
            val end = if (index + 1 < fixedStarts.size) fixedStarts[index + 1] else text.length
            text.setSpan(span, start, end, Spanned.SPAN_PARAGRAPH)
        }
        enterAt = -1
        deletedBreakAt = -1
        deletedPlaceholderAt = -1
        markLinks(text)
        invalidate()
    }

    // --- formatting API ----------------------------------------

    private fun selectedParagraphs(): List<Int> {
        val text = text ?: return emptyList()
        val from = selectionStart.coerceAtLeast(0)
        val to = selectionEnd.coerceAtLeast(from)
        return paragraphStarts(text).filter { start -> paragraphEnd(text, start) >= from && start <= to }
            .ifEmpty { listOf(0) }
    }

    fun currentStyle(): String = text?.let { paraAt(it, selectionStart.coerceAtLeast(0))?.type } ?: "body"

    fun applyParagraph(type: String) {
        val text = text ?: return
        val paragraphs = selectedParagraphs()
        val allSame = paragraphs.all { paraAt(text, it)?.type == type }
        val target = if (type in LIST_TYPES && allSame) "body" else type
        busy = true
        for (start in paragraphs) {
            val old = paraAt(text, start)
            setPara(text, start, makeSpan(target, if (target in LIST_TYPES) old?.level ?: 0 else 0, false))
        }
        normalize(text)
        busy = false
        onEdited?.invoke()
        onStyleChanged?.invoke()
    }

    fun indent(direction: Int) {
        val text = text ?: return
        busy = true
        for (start in selectedParagraphs()) {
            val old = paraAt(text, start) ?: continue
            val type = if (old.type in LIST_TYPES) old.type else if (direction > 0) "bullet" else continue
            setPara(text, start, makeSpan(type, old.level + direction, old.checked))
        }
        normalize(text)
        busy = false
        onEdited?.invoke()
    }

    private fun toggleChecked(paragraphStart: Int) {
        val text = text ?: return
        val old = paraAt(text, paragraphStart) ?: return
        if (old.type != "check") return
        busy = true
        setPara(text, paragraphStart, makeSpan("check", old.level, !old.checked))
        normalize(text)
        busy = false
        if (!old.checked && autoSortChecked) {
            val blocks = toBlocks()
            val index = paragraphStarts(text).indexOf(paragraphStart)
            var first = index
            while (first > 0 && blocks[first - 1].optString("t") == "check") first--
            var last = index
            while (last + 1 < blocks.size && blocks[last + 1].optString("t") == "check") last++
            val run = blocks.subList(first, last + 1).sortedBy { it.optBoolean("c") }
            load(blocks.subList(0, first) + run + blocks.subList(last + 1, blocks.size))
        }
        onEdited?.invoke()
    }

    private fun markLinks(text: Editable) {
        for (old in text.getSpans(0, text.length, LinkSpan::class.java)) text.removeSpan(old)
        for (match in LINK.findAll(text)) {
            text.setSpan(LinkSpan(colors.accent), match.range.first, match.range.last + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
    }

    /** The text typed after ">>" while the note choice is open (null: the cursor left it). */
    fun pendingLinkQuery(): String? {
        val text = text ?: return null
        val start = linkStart
        val cursor = selectionStart
        if (start < 0 || start + 2 > text.length || text[start] != '>' || text[start + 1] != '>' || cursor < start + 2) return null
        val query = text.substring(start + 2, cursor)
        return if ('\n' in query || query.length > 60) null else query
    }

    /** Replace ">>" (and what was typed after it) with a link to the note, or just
     *  forget the pending ">>" when [noteId] is null. */
    fun finishLink(noteId: String?, title: String?) {
        val text = text ?: return
        val start = linkStart
        val query = pendingLinkQuery()
        linkStart = -1
        if (noteId == null || title == null || start < 0) return
        val end = start + 2 + (query?.length ?: 0)
        busy = true
        text.replace(start, end, title)
        text.setSpan(NoteLinkSpan(noteId, colors.accent), start, start + title.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        val after = start + title.length
        if (after < text.length && text[after] == ' ') setSelection(after + 1)
        else { text.insert(after, " "); setSelection(after + 1) }
        normalize(text)
        busy = false
        // The keyboard may still hold ">>" as the word being typed – let it start over.
        (context.getSystemService(Context.INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager).restartInput(this)
        onEdited?.invoke()
    }

    /** A short tap on a web address opens it in the browser, on a note link the note (like Notes). */
    private fun openLinkAt(event: MotionEvent): Boolean {
        val text = text ?: return false
        if (event.eventTime - event.downTime > android.view.ViewConfiguration.getLongPressTimeout()) return false
        val offset = getOffsetForPosition(event.x, event.y)
        text.getSpans((offset - 1).coerceAtLeast(0), offset + 1, FileBlockSpan::class.java).firstOrNull {
            val start = text.getSpanStart(it)
            val line = layout?.getLineForOffset(start)
            line != null && line == layout?.getLineForVertical(event.y.toInt() - totalPaddingTop + scrollY)
        }?.let { onOpenFile?.invoke(JSONObject(it.block.toString())); return true }
        text.getSpans(offset, offset, NoteLinkSpan::class.java).firstOrNull {
            offset in text.getSpanStart(it) until text.getSpanEnd(it)
        }?.let { onOpenNote?.invoke(it.noteId); return true }
        val link = text.getSpans(offset, offset, LinkSpan::class.java).firstOrNull() ?: return false
        val start = text.getSpanStart(link)
        val end = text.getSpanEnd(link)
        if (offset !in start until end) return false
        val address = text.substring(start, end).let { if (it.startsWith("http://") || it.startsWith("https://")) it else "https://$it" }
        return try {
            context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(address))
                .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
            true
        } catch (error: android.content.ActivityNotFoundException) {
            false
        }
    }

    private fun handleTouch(event: MotionEvent): Boolean {
        if (event.action != MotionEvent.ACTION_UP) return false
        if (openLinkAt(event)) return true
        val layout = layout ?: return false
        val text = text ?: return false
        val y = event.y.toInt() - totalPaddingTop + scrollY
        val line = layout.getLineForVertical(y)
        val offset = layout.getLineStart(line)
        val span = paraAt(text, offset) ?: return false
        if (span.fold != 0 && event.x <= totalPaddingLeft + 24 * density) {
            val start = text.lastIndexOf('\n', (offset - 1).coerceAtLeast(0)).let { if (offset == 0 || it < 0) 0 else it + 1 }
            if (layout.getLineForOffset(start) == line) {
                toggleFold(start)
                return true
            }
        }
        if (span.type != "check") return false
        val paragraphStart = text.lastIndexOf('\n', (offset - 1).coerceAtLeast(0)).let { if (offset == 0 || it < 0) 0 else it + 1 }
        if (layout.getLineForOffset(paragraphStart) != line) return false
        val markerEnd = totalPaddingLeft + ((24 * span.level + 26) * density)
        if (event.x <= markerEnd) {
            toggleChecked(paragraphStart)
            return true
        }
        return false
    }

    /** Mark the selection (or the next typed text) in one color; null removes the marking.
     *  One color per character – a new one replaces the old, the same one again removes it. */
    fun setHighlight(name: String?, group: Collection<String> = groupOf(name) ?: HIGHLIGHTS.keys) {
        val text = text ?: return
        val start = selectionStart
        val end = selectionEnd
        if (start < 0) return
        if (start == end) {
            val current = (pendingInline ?: activeInline()).toMutableSet()
            val same = name != null && name in current
            current.removeAll(group.toSet())
            if (name != null && !same) current.add(name)
            pendingInline = current
            onStyleChanged?.invoke()
            return
        }
        busy = true
        val everything = name != null && (start until end).all { index ->
            text[index] == '\n' || text[index] == OBJECT || hasInline(text, name, index)
        }
        for (other in group) removeInline(text, other, start, end)
        if (name != null && !everything) text.setSpan(inlineSpan(name), start, end, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
        busy = false
        onEdited?.invoke()
        onStyleChanged?.invoke()
    }

    fun setTextColorStyle(name: String?) = setHighlight(name, TEXT_COLORS.keys)
    fun setFont(name: String?) = setHighlight(name, FONTS.keys)

    private fun groupOf(name: String?): Collection<String>? =
        listOf(HIGHLIGHTS.keys, TEXT_COLORS.keys, FONTS.keys).firstOrNull { name in it }

    /** Align the selected paragraphs: null (left), "center", "right". */
    fun setAlignment(name: String?) {
        val text = text ?: return
        busy = true
        for (start in selectedParagraphs()) {
            val span = spanStartingAt(text, start) ?: continue
            val from = text.getSpanStart(span)
            val to = text.getSpanEnd(span)
            text.removeSpan(span)
            span.align = name
            text.setSpan(span, from, to, Spanned.SPAN_PARAGRAPH)
        }
        busy = false
        onEdited?.invoke()
        onStyleChanged?.invoke()
    }

    fun currentAlignment(): String? = text?.let { paraAt(it, selectionStart.coerceAtLeast(0))?.align }

    fun toggleInline(name: String) {
        if (groupOf(name) != null) return setHighlight(name)
        val text = text ?: return
        val start = selectionStart
        val end = selectionEnd
        if (start < 0) return
        if (start == end) {
            val current = pendingInline ?: activeInline().toMutableSet()
            if (!current.add(name)) current.remove(name)
            pendingInline = current
            onStyleChanged?.invoke()
            return
        }
        busy = true
        val everything = (start until end).all { index ->
            text[index] == '\n' || text[index] == OBJECT || hasInline(text, name, index)
        }
        removeInline(text, name, start, end)
        if (!everything) text.setSpan(inlineSpan(name), start, end, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
        busy = false
        onEdited?.invoke()
        onStyleChanged?.invoke()
    }

    fun activeInline(): Set<String> {
        pendingInline?.let { return it }
        val text = text ?: return emptySet()
        val probe = (selectionStart - 1).coerceAtLeast(0)
        if (text.isEmpty()) return emptySet()
        return INLINE.filter { hasInline(text, it, probe) }.toSet()
    }

    override fun onSelectionChanged(selStart: Int, selEnd: Int) {
        super.onSelectionChanged(selStart, selEnd)
        pendingInline = null
        onStyleChanged?.invoke()
        // After the next layout pass, so the line positions are up to date.
        post { onCaretMoved?.invoke() }
    }

    // --- loading and saving ------------------------------------

    fun load(blocks: List<JSONObject>) {
        busy = true
        val builder = SpannableStringBuilder()
        val all = blocks.ifEmpty { listOf(JSONObject().put("t", "title").put("x", "")) }
        // Collapsed headings keep their section in a FoldSpan instead of the text.
        val list = mutableListOf<JSONObject>()
        val folds = mutableMapOf<Int, List<JSONObject>>()
        run {
            val types = all.map { it.optString("t", "body") }
            val texts = all.map { it.optString("x") }
            var index = 0
            while (index < all.size) {
                val block = all[index]
                list.add(block)
                if (block.optString("t") in FOLDABLE && block.optBoolean("z")) {
                    val end = sectionEnd(types, texts, index)
                    if (end > index) folds[list.lastIndex] = all.subList(index + 1, end + 1).toList()
                    index = end + 1
                    continue
                }
                index++
            }
        }
        var number = 0
        var previousNumber = false
        val paragraphs = mutableListOf<Triple<ParaSpan, Int, Int>>()
        val foldSpans = mutableListOf<Triple<FoldSpan, Int, Int>>()
        list.forEachIndexed { index, block ->
            val start = builder.length
            val type = block.optString("t", "body")
            if (type == "divider") {
                builder.append(OBJECT)
                builder.setSpan(dividerSpan(), start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            } else if (type == "file") {
                builder.append(OBJECT)
                val span = FileBlockSpan(JSONObject(block.toString()), fileCard(block, null))
                builder.setSpan(span, start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                loadPreview(span)
            } else if (type == "image") {
                builder.append(OBJECT)
                val fileId = block.optString("f")
                val placeholder = ColorDrawable(colors.tertiary).apply { setBounds(0, 0, (240 * density).toInt(), (160 * density).toInt()) }
                val span = ImageBlockSpan(fileId, placeholder)
                builder.setSpan(span, start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                loadImage(fileId) { bitmap -> if (bitmap != null) showImage(span, bitmap) }
            } else {
                val fresh = io.github.veritasx1.linotes.data.Model.refreshNoteLinks(block, noteTitle)
                val text = fresh.optString("x")
                builder.append(text)
                val spans = fresh.optJSONArray("s") ?: JSONArray()
                for (spanIndex in 0 until spans.length()) {
                    val item = spans.optJSONArray(spanIndex) ?: continue
                    val name = item.optString(2)
                    val target = io.github.veritasx1.linotes.data.Model.linkTarget(name)
                    if (name !in INLINE && target == null) continue
                    val from = (start + item.optInt(0)).coerceIn(start, start + text.length)
                    val to = (start + item.optInt(1)).coerceIn(from, start + text.length)
                    if (to <= from) continue
                    if (target != null) builder.setSpan(NoteLinkSpan(target, colors.accent), from, to, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    else builder.setSpan(inlineSpan(name), from, to, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
                }
            }
            if (index < list.size - 1) builder.append('\n')
            val paraType = if (type == "image" || type == "divider" || type == "file") "body" else type
            val span = makeSpan(paraType, block.optInt("l"), block.optBoolean("c"))
            span.align = block.optString("a").takeIf { it == "center" || it == "right" }
            folds[index]?.let { hidden ->
                foldSpans.add(Triple(FoldSpan(hidden), start, builder.length))
                span.fold = 2
            }
            if (paraType == "number") {
                number = if (previousNumber) number + 1 else 1
                span.number = number
            }
            previousNumber = paraType == "number"
            paragraphs.add(Triple(span, start, builder.length))
        }
        // Paragraph spans grow with text appended at their end, so they are
        // set only once the whole text exists.
        // Open headings with content below get their chevron.
        val types = list.map { it.optString("t", "body") }
        val texts = list.map { it.optString("x") }
        paragraphs.forEachIndexed { index, (span, _, _) ->
            if (span.fold == 0 && span.type in FOLDABLE && sectionEnd(types, texts, index) > index) span.fold = 1
        }
        for ((span, start, end) in paragraphs) builder.setSpan(span, start, end, Spanned.SPAN_PARAGRAPH)
        for ((span, start, end) in foldSpans) builder.setSpan(span, start, end, Spanned.SPAN_INCLUSIVE_INCLUSIVE)
        setText(builder, BufferType.EDITABLE)
        text?.let { markLinks(it) }
        busy = false
    }

    fun toBlocks(): List<JSONObject> {
        val text = text ?: return emptyList()
        val result = mutableListOf<JSONObject>()
        for (start in paragraphStarts(text)) {
            val end = paragraphEnd(text, start)
            // Text that ended up next to a divider or photo is kept as a line of its own.
            val extra = text.substring(start, end).replace(OBJECT.toString(), "").replace(PLACEHOLDER.toString(), "")
            val file = text.getSpans(start, end, FileBlockSpan::class.java).firstOrNull()
            if (file != null) {
                result.add(JSONObject(file.block.toString()))
                if (extra.isNotBlank()) result.add(JSONObject().put("t", "body").put("x", extra))
                continue
            }
            if (text.getSpans(start, end, DividerSpan::class.java).isNotEmpty()) {
                result.add(JSONObject().put("t", "divider"))
                if (extra.isNotBlank()) result.add(JSONObject().put("t", "body").put("x", extra))
                continue
            }
            val image = text.getSpans(start, end, ImageBlockSpan::class.java).firstOrNull()
            if (image != null) {
                result.add(JSONObject().put("t", "image").put("f", image.fileId))
                if (extra.isNotBlank()) result.add(JSONObject().put("t", "body").put("x", extra))
                continue
            }
            val span = paraAt(text, start)
            val block = JSONObject().put("t", span?.type ?: "body")
                .put("x", text.substring(start, end).replace(OBJECT.toString(), "").replace(PLACEHOLDER.toString(), ""))
            if (span != null && span.level > 0) block.put("l", span.level)
            if (span?.type == "check") block.put("c", span.checked)
            span?.align?.let { block.put("a", it) }
            val fold = foldAt(text, start)?.takeIf { span?.type in FOLDABLE }
            val spans = JSONArray()
            for (name in INLINE) {
                var index = start
                while (index < end) {
                    if (hasInline(text, name, index)) {
                        val from = index
                        while (index < end && hasInline(text, name, index)) index++
                        spans.put(JSONArray().put(from - start).put(index - start).put(name))
                    } else {
                        index++
                    }
                }
            }
            for (link in text.getSpans(start, end, NoteLinkSpan::class.java).sortedBy { text.getSpanStart(it) }) {
                val from = text.getSpanStart(link).coerceAtLeast(start)
                val to = text.getSpanEnd(link).coerceAtMost(end)
                if (to > from) spans.put(JSONArray().put(from - start).put(to - start).put(io.github.veritasx1.linotes.data.Model.NOTE_LINK + link.noteId))
            }
            if (spans.length() > 0) block.put("s", spans)
            result.add(block)
            if (fold != null) {
                block.put("z", true)
                result.addAll(fold.hidden)
            }
        }
        while (result.size > 1 && result.last().optString("t") == "body" && result.last().optString("x").isEmpty()) {
            result.removeAt(result.size - 1)
        }
        return result
    }

    // --- math ------------------------------------------------

    private fun insertCalculation(at: Int) {
        val text = text ?: return
        if (selectionStart != at || at > text.length || text[at - 1] != '=') return  // typing went on meanwhile
        val lineStart = text.lastIndexOf('\n', at - 1).let { if (it < 0) 0 else it + 1 }
        val line = text.substring(lineStart, at).replace(PLACEHOLDER.toString(), "")
        val earlier = if (lineStart == 0) emptyList() else text.substring(0, lineStart - 1).split('\n')
        var result = io.github.veritasx1.linotes.data.Calc.resultFor(line, earlier) ?: return
        if (line.dropLast(1).endsWith(" ")) result = " $result"
        text.insert(at, result)
        text.setSpan(CalcSpan(colors.accent), at, at + result.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
    }

    // --- collapsible sections ----------------------------------

    private fun foldAt(text: Spanned, paragraphStart: Int): FoldSpan? {
        val end = paragraphEnd(text, paragraphStart)
        return text.getSpans(paragraphStart, end, FoldSpan::class.java).firstOrNull { text.getSpanStart(it) in paragraphStart..end }
    }

    /** Collapse or expand the section of the heading starting at [paragraphStart] (like Apple). */
    fun toggleFold(paragraphStart: Int) {
        val text = text ?: return
        val index = paragraphStarts(text).indexOf(paragraphStart).takeIf { it >= 0 } ?: return
        val blocks = toBlocks().toMutableList()
        if (index >= blocks.size) return
        val heading = JSONObject(blocks[index].toString())
        if (heading.optBoolean("z")) heading.remove("z") else heading.put("z", true)
        blocks[index] = heading
        load(blocks)
        val start = paragraphStarts(this.text ?: return).getOrNull(index) ?: return
        setSelection(paragraphEnd(this.text!!, start))
        onEdited?.invoke()
    }

    // --- dividers ----------------------------------------------

    private fun dividerSpan() = DividerSpan(density, colors.tertiary) {
        (width - totalPaddingLeft - totalPaddingRight).takeIf { it > 0 } ?: (300 * density).toInt()
    }

    /** A divider on a line of its own at the cursor; typing goes on below it. */
    fun insertDivider() {
        val text = text ?: return
        var at = selectionStart.coerceAtLeast(0)
        busy = true
        if (at > 0 && text[at - 1] != '\n') {
            at = paragraphEnd(text, at)
            text.insert(at, "\n")
            at += 1
        }
        text.insert(at, "$OBJECT\n")
        text.setSpan(dividerSpan(), at, at + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        normalize(text)
        busy = false
        setSelection((at + 2).coerceAtMost(text.length))
        onEdited?.invoke()
    }

    // --- attachments -------------------------------------------

    /** Attach a file on a line of its own at the cursor; typing goes on below it. */
    fun insertFile(block: JSONObject) {
        val text = text ?: return
        var at = selectionStart.coerceAtLeast(0)
        busy = true
        if (at > 0 && text[at - 1] != '\n') {
            at = paragraphEnd(text, at)
            text.insert(at, "\n")
            at += 1
        }
        text.insert(at, "$OBJECT\n")
        val span = FileBlockSpan(block, fileCard(block, null))
        text.setSpan(span, at, at + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        normalize(text)
        busy = false
        setSelection((at + 2).coerceAtMost(text.length))
        loadPreview(span)
        onEdited?.invoke()
    }

    private fun loadPreview(span: FileBlockSpan) {
        if (span.block.optString("m") != "application/pdf") return
        val loader = loadFilePreview ?: return
        loader(span.block) { bitmap ->
            if (bitmap == null) return@loader
            post {
                val text = text ?: return@post
                val start = text.getSpanStart(span)
                if (start < 0) return@post
                busy = true
                text.removeSpan(span)
                text.setSpan(FileBlockSpan(span.block, fileCard(span.block, bitmap)), start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                busy = false
                invalidate()
            }
        }
    }

    /** The card: rounded box, preview or document symbol, name and details. */
    private fun fileCard(block: JSONObject, preview: Bitmap?): Drawable {
        val width = (width - totalPaddingLeft - totalPaddingRight).takeIf { it > 0 }?.coerceAtMost((420 * density).toInt()) ?: (320 * density).toInt()
        val height = (76 * density).toInt()
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val radius = 10 * density
        val box = android.graphics.RectF(density, density, width - density, height - density)
        canvas.drawRoundRect(box, radius, radius, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = (colors.label and 0x00FFFFFF) or 0x10000000 })
        canvas.drawRoundRect(box, radius, radius, Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeWidth = density; color = (colors.label and 0x00FFFFFF) or 0x26000000 })
        val iconBox = android.graphics.RectF(12 * density, 10 * density, 56 * density, height - 10 * density)
        if (preview != null) {
            val scale = minOf(iconBox.width() / preview.width, iconBox.height() / preview.height)
            val w = preview.width * scale
            val h = preview.height * scale
            val target = android.graphics.RectF(iconBox.centerX() - w / 2, iconBox.centerY() - h / 2, iconBox.centerX() + w / 2, iconBox.centerY() + h / 2)
            canvas.drawRect(target, Paint().apply { color = 0xFFFFFFFF.toInt() })
            canvas.drawBitmap(preview, null, target, Paint(Paint.FILTER_BITMAP_FLAG))
        } else {
            // A sheet with a folded corner, the extension on it.
            val sheet = android.graphics.RectF(iconBox.left + 6 * density, iconBox.top, iconBox.right - 6 * density, iconBox.bottom)
            val paper = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.accent }
            canvas.drawRoundRect(sheet, 4 * density, 4 * density, paper)
            val ext = block.optString("n").substringAfterLast('.', "").uppercase().take(4)
            val label = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt(); textSize = 10 * density; typeface = Typeface.DEFAULT_BOLD; textAlign = Paint.Align.CENTER }
            canvas.drawText(ext, sheet.centerX(), sheet.centerY() + 4 * density, label)
        }
        val textLeft = 68 * density
        val maxText = width - textLeft - 12 * density
        val title = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.label; textSize = 16 * resources.displayMetrics.scaledDensity; typeface = Typeface.DEFAULT_BOLD }
        val sub = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.secondary; textSize = 13 * resources.displayMetrics.scaledDensity }
        val name = android.text.TextUtils.ellipsize(block.optString("n", "Datei"), title, maxText, android.text.TextUtils.TruncateAt.MIDDLE).toString()
        canvas.drawText(name, textLeft, height / 2f - 3 * density, title)
        canvas.drawText(fileDetails(block), textLeft, height / 2f + 17 * density, sub)
        return BitmapDrawable(resources, bitmap).apply { setBounds(0, 0, width, height) }
    }

    // --- images ------------------------------------------------

    fun insertImage(fileId: String) {
        val text = text ?: return
        var at = selectionStart.coerceAtLeast(0)
        busy = true
        if (at > 0 && text[at - 1] != '\n') {
            at = paragraphEnd(text, at)
            text.insert(at, "\n")
            at += 1
        }
        text.insert(at, "$OBJECT\n")
        val placeholder = ColorDrawable(colors.tertiary).apply { setBounds(0, 0, (240 * density).toInt(), (160 * density).toInt()) }
        val span = ImageBlockSpan(fileId, placeholder)
        text.setSpan(span, at, at + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        normalize(text)
        busy = false
        loadImage(fileId) { bitmap -> if (bitmap != null) showImage(span, bitmap) }
        setSelection((at + 2).coerceAtMost(text.length))
        onEdited?.invoke()
    }

    private fun showImage(span: ImageBlockSpan, bitmap: Bitmap) {
        post {
            val available = (width - totalPaddingLeft - totalPaddingRight).takeIf { it > 0 } ?: (320 * density).toInt()
            val targetWidth = minOf(available, bitmap.width)
            val targetHeight = (bitmap.height * targetWidth.toFloat() / bitmap.width).toInt()
            val drawable = BitmapDrawable(resources, bitmap).apply { setBounds(0, 0, targetWidth, targetHeight) }
            val text = text ?: return@post
            val start = text.getSpanStart(span)
            if (start >= 0) {
                // ImageSpan caches the drawable it drew first (the placeholder),
                // so the picture needs a span of its own.
                busy = true
                text.removeSpan(span)
                text.setSpan(ImageBlockSpan(span.fileId, drawable), start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                busy = false
            }
            requestLayout()
            invalidate()
        }
    }

    companion object {
        val INLINE = listOf("b", "i", "u", "s") + HIGHLIGHTS.keys + TEXT_COLORS.keys + FONTS.keys

        fun decodeImage(bytes: ByteArray, maxSize: Int = 1600): Bitmap? {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            var sample = 1
            while (bounds.outWidth / sample > maxSize || bounds.outHeight / sample > maxSize) sample *= 2
            val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
                ?: return null
            return applyExifOrientation(bytes, bitmap)
        }

        /** Handyfotos sind oft quer gespeichert, die Drehung steht im EXIF. */
        fun applyExifOrientation(bytes: ByteArray, bitmap: Bitmap): Bitmap {
            val orientation = try {
                ExifInterface(ByteArrayInputStream(bytes))
                    .getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
            } catch (error: Exception) {
                ExifInterface.ORIENTATION_NORMAL
            }
            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
                ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
                ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
                ExifInterface.ORIENTATION_TRANSPOSE -> { matrix.postRotate(90f); matrix.postScale(-1f, 1f) }
                ExifInterface.ORIENTATION_TRANSVERSE -> { matrix.postRotate(270f); matrix.postScale(-1f, 1f) }
                else -> return bitmap
            }
            return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        }
    }

    private fun inlineSpan(name: String): Any = when (name) {
        "b" -> StyleSpan(Typeface.BOLD)
        "i" -> StyleSpan(Typeface.ITALIC)
        "u" -> UnderlineSpan()
        "s" -> StrikethroughSpan()
        "h" -> HighlightSpan(name, colors.highlight)
        in TEXT_COLORS -> TextColorSpan(name, (0xFF shl 24) or TEXT_COLORS.getValue(name))
        in FONTS -> FontSpan(name, FONTS.getValue(name))
        else -> HighlightSpan(name, (0x73 shl 24) or (HIGHLIGHTS[name] ?: 0xFFD83D))
    }

    private fun matches(span: Any, name: String) = when (name) {
        "b" -> span is StyleSpan && span.style == Typeface.BOLD
        "i" -> span is StyleSpan && span.style == Typeface.ITALIC
        "u" -> span is UnderlineSpan
        "s" -> span is StrikethroughSpan
        in TEXT_COLORS -> span is TextColorSpan && span.name == name
        in FONTS -> span is FontSpan && span.name == name
        else -> span is HighlightSpan && span.name == name
    }

    private fun hasInline(text: Spanned, name: String, index: Int): Boolean =
        text.getSpans(index, index + 1, Any::class.java).any { matches(it, name) && text.getSpanStart(it) <= index && text.getSpanEnd(it) > index }

    private fun removeInline(text: Spannable, name: String, start: Int, end: Int) {
        for (span in text.getSpans(start, end, Any::class.java)) {
            if (!matches(span, name)) continue
            val spanStart = text.getSpanStart(span)
            val spanEnd = text.getSpanEnd(span)
            text.removeSpan(span)
            if (spanStart < start) text.setSpan(inlineSpan(name), spanStart, start, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
            if (spanEnd > end) text.setSpan(inlineSpan(name), end, spanEnd, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
        }
    }
}
