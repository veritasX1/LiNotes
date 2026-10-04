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
import kotlin.math.abs
import android.util.TypedValue
import android.view.ActionMode
import android.view.Gravity
import android.view.MotionEvent
import android.widget.EditText
import io.github.veritasx1.linotes.data.LinkPreview
import io.github.veritasx1.linotes.data.Syntax
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
/** An @-mention of someone the note is shared with (span "m:<user id>"): accent, bold. */
class MentionSpan(val userId: Int, private val color: Int) : android.text.style.CharacterStyle(), android.text.style.UpdateAppearance {
    override fun updateDrawState(paint: TextPaint) {
        paint.color = color
        paint.isFakeBoldText = true
    }
}

/** A footnote number (Profi-Funktion): small, raised, in the accent color; the text rides along. */
class FootnoteSpan(val note: String, private val color: Int) : MetricAffectingSpan() {
    override fun updateMeasureState(paint: TextPaint) { paint.textSize *= 0.72f; paint.baselineShift += (paint.ascent() * 0.45f).toInt() }
    override fun updateDrawState(paint: TextPaint) {
        paint.textSize *= 0.72f; paint.baselineShift += (paint.ascent() * 0.45f).toInt()
        paint.color = color; paint.isFakeBoldText = true
    }
}

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
) : MetricAffectingSpan(), LeadingMarginSpan, LineHeightSpan, android.text.style.AlignmentSpan, android.text.style.LineBackgroundSpan {

    var number = 1
    /** Code blocks (Profi-Funktion): the language whose colors the lines get, e.g. "python". */
    var lang: String? = null

    override fun drawBackground(canvas: Canvas, paint: Paint, left: Int, right: Int, top: Int, baseline: Int, bottom: Int,
                                text: CharSequence, start: Int, end: Int, lineNumber: Int) {
        if (type != "code") return
        val saved = paint.color
        paint.color = (colors.label and 0x00FFFFFF) or 0x14000000
        canvas.drawRect(left.toFloat(), top.toFloat(), right.toFloat(), bottom.toFloat(), paint)
        paint.color = saved
    }
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
            "mono", "code" -> { paint.textSize *= 0.92f; paint.typeface = Typeface.MONOSPACE }
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
        type == "code" -> (8 * density).toInt()
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
/** Background of a line someone else changed since my last view (not saved). */
class ChangedSpan(private val color: Int) : android.text.style.LineBackgroundSpan {
    override fun drawBackground(canvas: Canvas, paint: Paint, left: Int, right: Int, top: Int, baseline: Int, bottom: Int,
                                text: CharSequence, start: Int, end: Int, lineNumber: Int) {
        val previous = paint.color
        paint.color = color
        canvas.drawRect(left.toFloat(), top.toFloat(), right.toFloat(), bottom.toFloat(), paint)
        paint.color = previous
    }
}

/** A space that keeps its width: with justified text, titles and headings must not be stretched
 *  (Android justifies the whole field, not single paragraphs). Justification only widens plain
 *  text runs, not replaced ones; the line can still break at the space. */
class FixedSpaceSpan : android.text.style.ReplacementSpan() {
    override fun getSize(paint: Paint, text: CharSequence?, start: Int, end: Int, fm: Paint.FontMetricsInt?): Int {
        if (fm != null) paint.getFontMetricsInt(fm)
        return Math.round(paint.measureText(" "))
    }
    override fun draw(canvas: Canvas, text: CharSequence?, start: Int, end: Int, x: Float, top: Int, y: Int, bottom: Int, paint: Paint) {}
}

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
    if (mime.startsWith("audio/") && block.has("d")) return "${AudioNotes.durationText(block.optDouble("d"))} · $amount"
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
/** A code color (display only – toBlocks ignores it, so it is never stored). */
class SyntaxSpan(val kind: String, private val dark: Boolean) : android.text.style.CharacterStyle() {
    override fun updateDrawState(paint: TextPaint) {
        paint.color = when (kind) {
            "keyword" -> if (dark) 0xFFC79BFF.toInt() else 0xFF9C52E0.toInt()
            "string" -> if (dark) 0xFF6FD39A.toInt() else 0xFF1A9452.toInt()
            "comment" -> if (dark) 0xFF9A9AA2.toInt() else 0xFF85858C.toInt()
            else -> if (dark) 0xFFFFB45C.toInt() else 0xFFE07A00.toInt()
        }
        if (kind == "comment") paint.textSkewX = -0.2f
    }
}

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
    /** A picture was tapped: the screen shows it in the quick look (900036dc). */
    var onOpenImage: ((String) -> Unit)? = null
    /** A control on a recording's player card: "toggle", "back", "forward", or "seek" (with 0…1). */
    var onAudio: ((JSONObject, String, Float) -> Unit)? = null
    /** What the player cards show (file id → state); see [showAudio]. */
    data class AudioView(val running: Boolean, val position: Long, val length: Long)
    private val audioViews = HashMap<String, AudioView>()
    private var objectTouch: Any? = null
    private var downX = 0f
    private var downY = 0f
    /** A footnote number was tapped (edit or remove it). */
    var onFootnote: ((FootnoteSpan) -> Unit)? = null
    /** The footnote texts changed (reading order) – the screen lists them under the note. */
    var onFootnotesChanged: ((List<String>) -> Unit)? = null
    private var shownFootnotes: List<String>? = null

    /** A web address was finished alone on a line (Enter or pasted): the screen may make a preview. */
    var onLinkLine: ((String) -> Unit)? = null
    /** First page of an attached PDF for its card (null: no preview). */
    var loadFilePreview: ((JSONObject, (Bitmap?) -> Unit) -> Unit)? = null
    /** Where the pending ">>" starts, or -1. */
    private var linkStart = -1
    /** "note" after ">>", "mention" after "@". */
    var linkKind = "note"
        private set
    /** People who can be @-mentioned here (user id, name) – only in shared notes, like Apple. */
    var mentionPeople: () -> List<Pair<Int, String>> = { emptyList() }
    var userName: (Int) -> String? = { null }

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
                    keepFootnotesClean(s, insertStart, insertCount)
                    renumberFootnotes(s)
                    highlightCode(s)
                } finally {
                    busy = false
                }
                checkLinkLines(s, insertStart, insertCount)
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

    // --- link previews (web address alone on a line → card) ------------

    /** After Enter (or pasting a lone address): every finished line that is just a web address. */
    private fun checkLinkLines(text: Editable, start: Int, count: Int) {
        val callback = onLinkLine ?: return
        val end = (start + count).coerceAtMost(text.length)
        val inserted = text.subSequence(start.coerceAtMost(end), end).toString()
        val lines = mutableListOf<IntRange>()
        if ('\n' in inserted) {
            // Each line that a line break of this edit finished.
            var at = start
            while (true) {
                val brk = text.indexOf('\n', at)
                if (brk < 0 || brk >= end) break
                val lineStart = text.lastIndexOf('\n', brk - 1).let { if (it < 0) 0 else it + 1 }
                lines.add(lineStart until brk)
                at = brk + 1
            }
        } else if (LinkPreview.loneUrl(inserted) != null) {
            val lineStart = text.lastIndexOf('\n', (start - 1).coerceAtLeast(0)).let { if (it < 0 || start == 0) 0 else it + 1 }
            lines.add(lineStart until paragraphEnd(text, start))
        }
        for (range in lines) {
            if (range.isEmpty() || text.getSpans(range.first, range.last + 1, FileBlockSpan::class.java).isNotEmpty()) continue
            LinkPreview.loneUrl(text.substring(range.first, range.last + 1))?.let { url -> post { callback(url) } }
        }
    }

    /** The line that still holds only [url] becomes the preview card; the cursor stays where it is. */
    fun replaceUrlLine(url: String, block: JSONObject): Boolean {
        val text = text ?: return false
        var lineStart = 0
        while (lineStart <= text.length) {
            val lineEnd = paragraphEnd(text, lineStart)
            if (text.substring(lineStart, lineEnd).trim() == url && text.getSpans(lineStart, lineEnd, FileBlockSpan::class.java).isEmpty()) {
                val cursor = selectionStart
                busy = true
                text.replace(lineStart, lineEnd, OBJECT.toString())
                text.setSpan(FileBlockSpan(block, fileCard(block, null)), lineStart, lineStart + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                normalize(text)
                busy = false
                val shift = lineEnd - lineStart - 1
                setSelection((if (cursor > lineStart) cursor - shift else cursor).coerceIn(0, text.length))
                text.getSpans(lineStart, lineStart + 1, FileBlockSpan::class.java).firstOrNull()?.let { loadPreview(it) }
                onEdited?.invoke()
                return true
            }
            lineStart = lineEnd + 1
        }
        return false
    }

    /** Back to the plain address ("Nur als Adresse zeigen"). */
    fun unlinkPreview(block: JSONObject) {
        val text = text ?: return
        val span = text.getSpans(0, text.length, FileBlockSpan::class.java).firstOrNull {
            it.block.optString("t") == "link" && it.block.optString("u") == block.optString("u")
        } ?: return
        val start = text.getSpanStart(span)
        busy = true
        text.removeSpan(span)
        text.replace(start, start + 1, block.optString("u"))
        normalize(text)
        busy = false
        onEdited?.invoke()
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
            if (style != null && style.type == "code" && content.isBlank()) {
                // An empty code line ends the code block (like an empty list item ends a list).
                text.delete(enterAt, enterAt + 1)
                setPara(text, paragraphStart, makeSpan("body"))
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
            linkKind = "note"
            post { onLinkRequested?.invoke() }
        }
        // "@" at a word start mentions someone the note is shared with (not in e-mail addresses).
        if (linkStart < 0 && insertCount > 0 && insertEnd <= text.length && text[insertEnd - 1] == '@' &&
            (insertEnd == 1 || text[insertEnd - 2] in " \n\t(" || text[insertEnd - 2] == OBJECT || text[insertEnd - 2] == PLACEHOLDER) &&
            mentionPeople().isNotEmpty()) {
            linkStart = insertEnd - 1
            linkKind = "mention"
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
            if (span.lang == null && span.type == "code") span.lang = old.lang
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
            // Code blocks keep their language, also on the line created by Enter.
            if (styles[index].type == "code") styles[index].lang =
                if (enterAt >= 0 && start == enterAt + 1) enterStyle?.lang else spanStartingAt(text, start)?.lang
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
        markFixedSpaces(text)
        invalidate()
    }

    /** Justified text (settings): keep titles and headings unstretched. */
    var justified = false

    private fun markFixedSpaces(text: Editable) {
        for (old in text.getSpans(0, text.length, FixedSpaceSpan::class.java)) text.removeSpan(old)
        if (!justified) return
        for (para in text.getSpans(0, text.length, ParaSpan::class.java)) {
            if (para.type != "title" && para.type != "heading" && para.type != "subheading") continue
            val start = text.getSpanStart(para)
            val end = text.getSpanEnd(para)
            for (index in start until end) {
                if (text[index] == ' ') text.setSpan(FixedSpaceSpan(), index, index + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
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

    // --- footnotes (Profi-Funktion) ---

    /** Typed text never becomes part of a footnote number. */
    private fun keepFootnotesClean(text: Editable, start: Int, count: Int) {
        if (count <= 0) return
        for (span in text.getSpans(start, start + count, FootnoteSpan::class.java)) {
            val from = text.getSpanStart(span)
            val to = text.getSpanEnd(span)
            if (start <= from && start + count >= to) continue
            text.removeSpan(span)
            val number = (from until to).firstOrNull { it !in start until start + count && text[it].isDigit() } ?: continue
            text.setSpan(span, number, number + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
    }

    /** Footnote numbers follow the reading order (1, 2, 3 …). */
    fun renumberFootnotes(text: Editable) {
        val spans = text.getSpans(0, text.length, FootnoteSpan::class.java).sortedBy { text.getSpanStart(it) }
        for ((index, span) in spans.withIndex().reversed()) {
            val from = text.getSpanStart(span)
            val to = text.getSpanEnd(span)
            val number = (index + 1).toString()
            if (text.substring(from, to) == number) continue
            text.replace(from, to, number)
            text.removeSpan(span)
            text.setSpan(span, from, from + number.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        val notes = spans.map { it.note }
        if (notes != shownFootnotes) {
            shownFootnotes = notes
            post { onFootnotesChanged?.invoke(notes) }
        }
    }

    fun insertFootnote(note: String) {
        val text = text ?: return
        val at = selectionStart.coerceAtLeast(0)
        busy = true
        text.insert(at, "0")
        text.setSpan(FootnoteSpan(note.trim(), colors.accent), at, at + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        renumberFootnotes(text)
        busy = false
        onEdited?.invoke()
    }

    /** Change the footnote's text (null: remove it). */
    fun editFootnote(span: FootnoteSpan, note: String?) {
        val text = text ?: return
        val from = text.getSpanStart(span)
        val to = text.getSpanEnd(span)
        if (from < 0) return
        busy = true
        text.removeSpan(span)
        if (note == null) text.delete(from, to) else text.setSpan(FootnoteSpan(note.trim(), colors.accent), from, to, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        renumberFootnotes(text)
        busy = false
        onEdited?.invoke()
    }

    /** Format → Code (language), a Profi-Funktion: the selected paragraphs become a code block. */
    fun makeCode(lang: String) {
        val text = text ?: return
        busy = true
        for (start in selectedParagraphs()) setPara(text, start, makeSpan("code").also { it.lang = lang })
        normalize(text)
        highlightCode(text)
        busy = false
        onEdited?.invoke()
        onStyleChanged?.invoke()
    }

    /** Colors keywords, strings, comments, numbers in code paragraphs – display only (SyntaxSpan is never saved). */
    fun highlightCode(text: Editable) {
        for (old in text.getSpans(0, text.length, SyntaxSpan::class.java)) text.removeSpan(old)
        for (start in paragraphStarts(text)) {
            val span = spanStartingAt(text, start) ?: continue
            if (span.type != "code") continue
            val end = paragraphEnd(text, start)
            for (token in Syntax.tokens(text.substring(start, end), span.lang)) {
                text.setSpan(SyntaxSpan(token.kind, android.graphics.Color.luminance(colors.label) > 0.5f), start + token.start, start + token.end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
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
        val prefix = if (linkKind == "note") 2 else 1
        if (start < 0 || start + prefix > text.length || cursor < start + prefix) return null
        if (linkKind == "note" && (text[start] != '>' || text[start + 1] != '>')) return null
        if (linkKind == "mention" && text[start] != '@') return null
        val query = text.substring(start + prefix, cursor)
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
        val mention = linkKind == "mention"
        val end = start + (if (mention) 1 else 2) + (query?.length ?: 0)
        val shown = if (mention) "@$title" else title
        busy = true
        text.replace(start, end, shown)
        text.setSpan(if (mention) MentionSpan(noteId.toInt(), colors.accent) else NoteLinkSpan(noteId, colors.accent),
            start, start + shown.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        val after = start + shown.length
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
        text.getSpans((offset - 1).coerceAtLeast(0), offset + 1, FootnoteSpan::class.java).firstOrNull()
            ?.let { onFootnote?.invoke(it); return true }
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

    /** The picture or file card under the finger (and where it is drawn, in text coordinates). */
    private fun objectAt(event: MotionEvent): Pair<ImageSpan, android.graphics.RectF>? {
        val text = text ?: return null
        val layout = layout ?: return null
        val x = event.x - totalPaddingLeft + scrollX
        val y = event.y - totalPaddingTop + scrollY
        val line = layout.getLineForVertical(y.toInt())
        val spans = text.getSpans(layout.getLineStart(line), layout.getLineEnd(line), ImageSpan::class.java)
            .filter { it is FileBlockSpan || it is ImageBlockSpan }
        for (span in spans) {
            val start = text.getSpanStart(span)
            if (layout.getLineForOffset(start) != line) continue
            val bounds = span.drawable.bounds
            val left = layout.getPrimaryHorizontal(start)
            val bottom = layout.getLineBottom(line).toFloat()
            val rect = android.graphics.RectF(left, bottom - bounds.height(), left + bounds.width(), bottom)
            if (rect.contains(x, y)) return span to rect
        }
        return null
    }

    /** Pictures and recordings react to the finger like buttons: a tap opens/plays them, also when
     *  pressed a little longer – the cursor does not jump in front of them (900036dc). */
    private fun handleObjectTouch(event: MotionEvent): Boolean? {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                objectTouch = objectAt(event)?.first
                downX = event.x
                downY = event.y
                // EditText gets the touch (scrolling keeps working), but no long press: that would
                // put the cursor (and the selection handles) in front of the object.
                if (objectTouch != null) post { cancelLongPress() }
                return null
            }
            MotionEvent.ACTION_MOVE -> {
                val slop = android.view.ViewConfiguration.get(context).scaledTouchSlop
                if (objectTouch != null && (abs(event.x - downX) > slop || abs(event.y - downY) > slop)) objectTouch = null
                else if (objectTouch != null) cancelLongPress()
                return null
            }
            MotionEvent.ACTION_CANCEL -> { objectTouch = null; return null }
            MotionEvent.ACTION_UP -> {
                val target = objectTouch ?: return null
                objectTouch = null
                val (span, rect) = objectAt(event)?.takeIf { it.first === target } ?: return null
                // Let EditText end its touch without placing the cursor.
                onTouchEvent(MotionEvent.obtain(event).apply { action = MotionEvent.ACTION_CANCEL })
                val x = event.x - totalPaddingLeft + scrollX - rect.left
                val y = event.y - totalPaddingTop + scrollY - rect.top
                when (span) {
                    is ImageBlockSpan -> onOpenImage?.invoke(span.fileId)
                    is FileBlockSpan -> if (AudioNotes.isAudio(span.block)) {
                        val (action, fraction) = audioHit(span.block, x, y, rect.width())
                        onAudio?.invoke(JSONObject(span.block.toString()), action, fraction)
                    } else onOpenFile?.invoke(JSONObject(span.block.toString()))
                }
                return true
            }
        }
        return null
    }

    private fun handleTouch(event: MotionEvent): Boolean {
        handleObjectTouch(event)?.let { return it }
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

    // --- system selection menu ----------------------------------

    private var floatingMode: ActionMode? = null

    /** While the format panel is open, Android's floating "Cut / Copy / Share" bar would sit on top
     *  of its buttons. Like Apple's edit menu it stays away then; the selection itself is kept,
     *  because the panel's styles apply to it. */
    var selectionMenuSuppressed = false
        set(value) {
            field = value
            if (value) floatingMode?.let { mode ->
                val start = selectionStart
                val end = selectionEnd
                floatingMode = null
                mode.finish()
                if (selectionStart != start || selectionEnd != end) setSelection(start, end)
            }
        }

    override fun startActionMode(callback: ActionMode.Callback?, type: Int): ActionMode? {
        if (type == ActionMode.TYPE_FLOATING && selectionMenuSuppressed) return null
        return super.startActionMode(callback, type).also { if (type == ActionMode.TYPE_FLOATING) floatingMode = it }
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
        val origins = mutableListOf<Int>()
        val folds = mutableMapOf<Int, List<JSONObject>>()
        run {
            val types = all.map { it.optString("t", "body") }
            val texts = all.map { it.optString("x") }
            var index = 0
            while (index < all.size) {
                val block = all[index]
                list.add(block)
                origins.add(index)
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
            } else if (type == "table" || type == "math") {
                builder.append(OBJECT)
                builder.setSpan(FileBlockSpan(JSONObject(block.toString()), blockCard(block)), start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            } else if (type == "file" || type == "link") {
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
                val fresh = io.github.veritasx1.linotes.data.Model.refreshNoteLinks(block, noteTitle, userName)
                val text = fresh.optString("x")
                builder.append(text)
                val spans = fresh.optJSONArray("s") ?: JSONArray()
                for (spanIndex in 0 until spans.length()) {
                    val item = spans.optJSONArray(spanIndex) ?: continue
                    val name = item.optString(2)
                    val target = io.github.veritasx1.linotes.data.Model.linkTarget(name)
                    val person = io.github.veritasx1.linotes.data.Model.mentionTarget(name)
                    val footnote = io.github.veritasx1.linotes.data.Model.footnoteText(name)
                    if (name !in INLINE && target == null && person == null && footnote == null) continue
                    val from = (start + item.optInt(0)).coerceIn(start, start + text.length)
                    val to = (start + item.optInt(1)).coerceIn(from, start + text.length)
                    if (to <= from) continue
                    if (footnote != null) builder.setSpan(FootnoteSpan(footnote, colors.accent), from, to, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    else if (target != null) builder.setSpan(NoteLinkSpan(target, colors.accent), from, to, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    else if (person != null) builder.setSpan(MentionSpan(person, colors.accent), from, to, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    else builder.setSpan(inlineSpan(name), from, to, Spanned.SPAN_EXCLUSIVE_INCLUSIVE)
                }
            }
            if (index < list.size - 1) builder.append('\n')
            val paraType = if (type == "image" || type == "divider" || type == "file" || type == "link" || type == "table" || type == "math") "body" else type
            val span = makeSpan(paraType, block.optInt("l"), block.optBoolean("c"))
            span.align = block.optString("a").takeIf { it == "center" || it == "right" }
            if (paraType == "code") span.lang = block.optString("lang").takeIf { it in Syntax.LANGUAGES }
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
        text?.let { markLinks(it); markFixedSpaces(it); highlightCode(it); renumberFootnotes(it) }
        lineBlocks = origins
        busy = false
    }

    /** Index of the loaded block shown in each line (folded blocks have no line). */
    private var lineBlocks: List<Int> = emptyList()

    /** Highlight the lines of the given blocks (changes by someone else) until the next load. */
    fun markChanged(blockIndices: Collection<Int>) {
        val editable = text ?: return
        val color = (colors.accent and 0x00FFFFFF) or (0x29 shl 24)
        var start = 0
        lineBlocks.forEachIndexed { line, block ->
            // A paragraph span runs up to and including the line break.
            val end = editable.indexOf('\n', start).let { if (it < 0) editable.length else it + 1 }
            if (block in blockIndices) editable.setSpan(ChangedSpan(color), start, end, Spanned.SPAN_PARAGRAPH)
            if (end >= editable.length) return
            start = end
        }
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
            if (span?.type == "code") span.lang?.let { block.put("lang", it) }
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
            for (mention in text.getSpans(start, end, MentionSpan::class.java).sortedBy { text.getSpanStart(it) }) {
                val from = text.getSpanStart(mention).coerceAtLeast(start)
                val to = text.getSpanEnd(mention).coerceAtMost(end)
                if (to > from) spans.put(JSONArray().put(from - start).put(to - start).put(io.github.veritasx1.linotes.data.Model.MENTION + mention.userId))
            }
            for (note in text.getSpans(start, end, FootnoteSpan::class.java).sortedBy { text.getSpanStart(it) }) {
                val from = text.getSpanStart(note).coerceAtLeast(start)
                val to = text.getSpanEnd(note).coerceAtMost(end)
                if (to > from) spans.put(JSONArray().put(from - start).put(to - start).put(io.github.veritasx1.linotes.data.Model.FOOTNOTE + note.note))
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

    /** A formula (Profi-Funktion) on a line of its own; tapping it opens its source. */
    fun insertMath(block: JSONObject) = insertTable(block)

    /** A table (like Apple's): shown as a grid, tapping opens the table editor. */
    fun insertTable(block: JSONObject) {
        val text = text ?: return
        var at = selectionStart.coerceAtLeast(0)
        busy = true
        if (at > 0 && text[at - 1] != '\n') {
            at = paragraphEnd(text, at)
            text.insert(at, "\n")
            at += 1
        }
        text.insert(at, "$OBJECT\n")
        text.setSpan(FileBlockSpan(block, blockCard(block)), at, at + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        normalize(text)
        busy = false
        setSelection((at + 2).coerceAtMost(text.length))
        onEdited?.invoke()
    }

    /** Replace a table or formula after editing it (null: delete it with its line). */
    fun replaceTable(old: JSONObject, new: JSONObject?) = replaceBlock(old, new)

    fun replaceBlock(old: JSONObject, new: JSONObject?) {
        val text = text ?: return
        val span = text.getSpans(0, text.length, FileBlockSpan::class.java).firstOrNull { it.block.toString() == old.toString() } ?: return
        val start = text.getSpanStart(span)
        busy = true
        text.removeSpan(span)
        if (new == null) {
            text.delete(start, (start + 2).coerceAtMost(text.length))
        } else {
            text.setSpan(FileBlockSpan(new, blockCard(new)), start, start + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        normalize(text)
        busy = false
        onEdited?.invoke()
    }

    private fun blockCard(block: JSONObject): Drawable = if (block.optString("t") == "math") mathCard(block) else tableCard(block)

    /** A formula set by MathTex, a little larger than the text, centered in the line. */
    private fun mathCard(block: JSONObject): Drawable {
        val width = (width - totalPaddingLeft - totalPaddingRight).takeIf { it > 0 } ?: (320 * density).toInt()
        return MathDraw.FormulaDrawable(block.optString("x"), textSize * 1.15f, colors.label, 6 * density, width)
    }

    private fun tableCard(block: JSONObject): Drawable {
        val rows = io.github.veritasx1.linotes.data.Model.tableRows(block)
        val width = (width - totalPaddingLeft - totalPaddingRight).takeIf { it > 0 } ?: (320 * density).toInt()
        val cell = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.label; textSize = 15 * resources.displayMetrics.scaledDensity }
        val rowHeight = (cell.textSize * 1.9f).toInt()
        val shown = rows.take(20)
        val height = rowHeight * shown.size + (if (rows.size > shown.size) rowHeight else 0) + (2 * density).toInt()
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val line = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = density; color = (colors.label and 0x00FFFFFF) or 0x33000000 }
        val columnWidth = (width - 2 * density) / rows[0].size
        shown.forEachIndexed { r, row ->
            row.forEachIndexed { c, value ->
                val left = density + c * columnWidth
                val top = density + r * rowHeight
                canvas.drawRect(left, top, left + columnWidth, top + rowHeight, line)
                val clipped = android.text.TextUtils.ellipsize(value, cell, columnWidth - 12 * density, android.text.TextUtils.TruncateAt.END).toString()
                canvas.drawText(clipped, left + 6 * density, top + rowHeight / 2f + cell.textSize / 3f, cell)
            }
        }
        if (rows.size > shown.size) {
            val more = TextPaint(cell).apply { color = colors.secondary }
            canvas.drawText("… ${rows.size - shown.size} weitere Zeilen", 6 * density, height - rowHeight / 2f + cell.textSize / 3f, more)
        }
        return BitmapDrawable(resources, bitmap).apply { setBounds(0, 0, width, height) }
    }

    private fun loadPreview(span: FileBlockSpan) {
        val link = span.block.optString("t") == "link"
        if (link && span.block.optString("f").isEmpty()) return
        if (!link && span.block.optString("m") != "application/pdf") return
        val loader: (JSONObject, (Bitmap?) -> Unit) -> Unit =
            if (link) { block, done -> loadImage(block.optString("f"), done) } else loadFilePreview ?: return
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
        if (AudioNotes.isAudio(block)) return audioCard(block, audioViews[block.optString("f")])
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
        val link = block.optString("t") == "link"
        if (link && preview != null) {
            // The page's picture, cropped to fill the square (like Apple's previews).
            val side = minOf(preview.width, preview.height)
            val source = android.graphics.Rect((preview.width - side) / 2, (preview.height - side) / 2, (preview.width + side) / 2, (preview.height + side) / 2)
            canvas.save()
            val clip = android.graphics.Path().apply { addRoundRect(iconBox, 6 * density, 6 * density, android.graphics.Path.Direction.CW) }
            canvas.clipPath(clip)
            canvas.drawBitmap(preview, source, iconBox, Paint(Paint.FILTER_BITMAP_FLAG))
            canvas.restore()
        } else if (link) {
            // No picture: a globe in the accent color.
            val globe = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = 2 * density; color = colors.accent }
            val r = minOf(iconBox.width(), iconBox.height()) / 2 - 2 * density
            canvas.drawCircle(iconBox.centerX(), iconBox.centerY(), r, globe)
            canvas.drawOval(android.graphics.RectF(iconBox.centerX() - r / 2.2f, iconBox.centerY() - r, iconBox.centerX() + r / 2.2f, iconBox.centerY() + r), globe)
            canvas.drawLine(iconBox.centerX() - r, iconBox.centerY(), iconBox.centerX() + r, iconBox.centerY(), globe)
        } else if (preview != null) {
            val scale = minOf(iconBox.width() / preview.width, iconBox.height() / preview.height)
            val w = preview.width * scale
            val h = preview.height * scale
            val target = android.graphics.RectF(iconBox.centerX() - w / 2, iconBox.centerY() - h / 2, iconBox.centerX() + w / 2, iconBox.centerY() + h / 2)
            canvas.drawRect(target, Paint().apply { color = 0xFFFFFFFF.toInt() })
            canvas.drawBitmap(preview, null, target, Paint(Paint.FILTER_BITMAP_FLAG))
        } else if (AudioNotes.isAudio(block)) {
            // A recording: a round play button like in Notes.
            val circle = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.accent }
            val radius = minOf(iconBox.width(), iconBox.height()) / 2
            canvas.drawCircle(iconBox.centerX(), iconBox.centerY(), radius, circle)
            val triangle = android.graphics.Path().apply {
                moveTo(iconBox.centerX() - radius * 0.3f, iconBox.centerY() - radius * 0.45f)
                lineTo(iconBox.centerX() + radius * 0.5f, iconBox.centerY())
                lineTo(iconBox.centerX() - radius * 0.3f, iconBox.centerY() + radius * 0.45f)
                close()
            }
            canvas.drawPath(triangle, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() })
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
        val label = when {
            link -> block.optString("n").ifEmpty { block.optString("dm") }
            AudioNotes.isAudio(block) -> "Audioaufnahme"
            else -> block.optString("n", "Datei")
        }
        val name = android.text.TextUtils.ellipsize(label, title, maxText,
            if (link) android.text.TextUtils.TruncateAt.END else android.text.TextUtils.TruncateAt.MIDDLE).toString()
        canvas.drawText(name, textLeft, height / 2f - 3 * density, title)
        val details = if (link) android.text.TextUtils.ellipsize(block.optString("dm"), sub, maxText, android.text.TextUtils.TruncateAt.END).toString()
            else fileDetails(block)
        canvas.drawText(details, textLeft, height / 2f + 17 * density, sub)
        return BitmapDrawable(resources, bitmap).apply { setBounds(0, 0, width, height) }
    }

    // --- recordings: a player card like Apple's (HIG: filled play/pause, ±15 s, scrubber,
    //     elapsed and remaining time with even digits, targets of at least 44 dp) ----------

    private val audioIdleHeight get() = 76 * density
    private val audioOpenHeight get() = 124 * density

    /** Which control of a recording's card is at (x, y) (card coordinates): the action and, for
     *  "seek", the place on the bar (0…1). Anything else on the card plays/pauses. */
    private fun audioHit(block: JSONObject, x: Float, y: Float, width: Float): Pair<String, Float> {
        val open = audioViews.containsKey(block.optString("f"))
        val d = density
        if (!open) return "toggle" to 0f
        if (abs(y - 38 * d) <= 24 * d && abs(x - (width - 92 * d)) <= 22 * d) return "back" to 0f
        if (abs(y - 38 * d) <= 24 * d && abs(x - (width - 42 * d)) <= 22 * d) return "forward" to 0f
        if (y >= 66 * d) return "seek" to ((x - 16 * d) / (width - 32 * d)).coerceIn(0f, 1f)
        return "toggle" to 0f
    }

    private fun audioCard(block: JSONObject, view: AudioView?): Drawable {
        val d = density
        val width = (width - totalPaddingLeft - totalPaddingRight).takeIf { it > 0 }?.coerceAtMost((420 * d).toInt()) ?: (320 * d).toInt()
        val height = (if (view != null) audioOpenHeight else audioIdleHeight).toInt()
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val box = android.graphics.RectF(d, d, width - d, height - d)
        canvas.drawRoundRect(box, 12 * d, 12 * d, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = (colors.label and 0x00FFFFFF) or 0x10000000 })
        canvas.drawRoundRect(box, 12 * d, 12 * d, Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeWidth = d; color = (colors.label and 0x00FFFFFF) or 0x26000000 })
        // Round play/pause button in the accent color.
        val cx = 34 * d
        val cy = 38 * d
        val radius = 22 * d
        canvas.drawCircle(cx, cy, radius, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.accent })
        val white = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
        if (view?.running == true) {
            canvas.drawRoundRect(cx - 7 * d, cy - 8 * d, cx - 2.5f * d, cy + 8 * d, 1.5f * d, 1.5f * d, white)
            canvas.drawRoundRect(cx + 2.5f * d, cy - 8 * d, cx + 7 * d, cy + 8 * d, 1.5f * d, 1.5f * d, white)
        } else {
            canvas.drawPath(android.graphics.Path().apply {
                moveTo(cx - 6 * d, cy - 9 * d); lineTo(cx + 10 * d, cy); lineTo(cx - 6 * d, cy + 9 * d); close()
            }, white)
        }
        val (title, subtitle) = AudioNotes.label(block)
        val textLeft = 68 * d
        val textRight = if (view != null) width - 118 * d else width - 12 * d
        val titlePaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.label; textSize = 16 * resources.displayMetrics.scaledDensity; typeface = Typeface.DEFAULT_BOLD }
        val sub = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.secondary; textSize = 13 * resources.displayMetrics.scaledDensity }
        canvas.drawText(android.text.TextUtils.ellipsize(title, titlePaint, textRight - textLeft, android.text.TextUtils.TruncateAt.END).toString(),
            textLeft, cy - 3 * d, titlePaint)
        canvas.drawText(android.text.TextUtils.ellipsize(subtitle.ifEmpty { fileDetails(block) }, sub, textRight - textLeft,
            android.text.TextUtils.TruncateAt.END).toString(), textLeft, cy + 17 * d, sub)
        if (view != null) {
            // ±15 s as circular arrows with "15" inside (Apple's gobackward.15 / goforward.15).
            val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = 1.8f * d; color = colors.accent; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND }
            val label = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.accent; textSize = 9 * d; typeface = Typeface.DEFAULT_BOLD; textAlign = Paint.Align.CENTER }
            for ((centerX, forward) in listOf(width - 92 * d to false, width - 42 * d to true)) {
                val r = 12 * d
                val oval = android.graphics.RectF(centerX - r, cy - r, centerX + r, cy + r)
                if (forward) canvas.drawArc(oval, -90f + 34f, 326f, false, stroke) else canvas.drawArc(oval, -90f - 34f, -326f, false, stroke)
                val side = if (forward) -1 else 1
                canvas.drawPath(android.graphics.Path().apply {
                    moveTo(centerX + side * 4 * d, cy - r - 4 * d); lineTo(centerX, cy - r); lineTo(centerX + side * 4 * d, cy - r + 4 * d)
                }, stroke)
                canvas.drawText("15", centerX, cy + 3.5f * d, label)
            }
            // Scrubber with elapsed and remaining time (tabular digits).
            val fraction = if (view.length > 0) (view.position.toFloat() / view.length).coerceIn(0f, 1f) else 0f
            val barLeft = 16 * d
            val barRight = width - 16 * d
            val barY = 86 * d
            val track = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = (colors.label and 0x00FFFFFF) or 0x30000000 }
            canvas.drawRoundRect(barLeft, barY - 2 * d, barRight, barY + 2 * d, 2 * d, 2 * d, track)
            val knobX = barLeft + (barRight - barLeft) * fraction
            canvas.drawRoundRect(barLeft, barY - 2 * d, knobX, barY + 2 * d, 2 * d, 2 * d, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.accent })
            canvas.drawCircle(knobX, barY, 7 * d, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.accent })
            val time = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = colors.secondary; textSize = 12 * resources.displayMetrics.scaledDensity; fontFeatureSettings = "tnum" }
            canvas.drawText(AudioNotes.durationText(view.position / 1000.0), barLeft, 110 * d, time)
            time.textAlign = Paint.Align.RIGHT
            canvas.drawText("−" + AudioNotes.durationText(maxOf(0L, view.length - view.position) / 1000.0), barRight, 110 * d, time)
        }
        return BitmapDrawable(resources, bitmap).apply { setBounds(0, 0, width, height) }
    }

    /** Show a recording's player state on its card (null: back to the plain card). */
    fun showAudio(fileId: String, view: AudioView?) {
        val text = text ?: return
        if (view == null) audioViews.remove(fileId) else audioViews[fileId] = view
        val span = text.getSpans(0, text.length, FileBlockSpan::class.java).firstOrNull { it.block.optString("f") == fileId } ?: return
        val start = text.getSpanStart(span)
        val end = text.getSpanEnd(span)
        val wasBusy = busy
        busy = true
        text.removeSpan(span)
        text.setSpan(FileBlockSpan(span.block, audioCard(span.block, view)), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        busy = wasBusy
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
