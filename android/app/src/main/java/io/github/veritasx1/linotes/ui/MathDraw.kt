package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import io.github.veritasx1.linotes.data.MathTex

/** Draws formulas set by [MathTex] (editor card, PDF). Ubuntu: mathtex.draw with Cairo. */
object MathDraw {
    private const val ERROR_COLOR = 0xFFD93333.toInt()
    private val widths = HashMap<String, Float>()
    private val paints = HashMap<String, Paint>()

    private fun paint(style: String): Paint = paints.getOrPut(style) {
        Paint(Paint.ANTI_ALIAS_FLAG or Paint.SUBPIXEL_TEXT_FLAG).apply {
            typeface = Typeface.create(Typeface.SERIF, when (style) {
                "it" -> Typeface.ITALIC
                "bf" -> Typeface.BOLD
                else -> Typeface.NORMAL
            })
        }
    }

    /** Width as the sum of the characters (cached) – like Ubuntu, TeX does not kern math either. */
    fun measure(text: String, size: Double, style: String): Double {
        var total = 0.0
        var index = 0
        while (index < text.length) {
            val code = text.codePointAt(index)
            val char = String(Character.toChars(code))
            index += Character.charCount(code)
            val key = "$style|${"%.2f".format(java.util.Locale.ROOT, size)}|$char"
            total += widths.getOrPut(key) {
                if (widths.size > 4000) widths.clear()
                val paint = paint(style)
                paint.textSize = size.toFloat()
                paint.measureText(char)
            }
        }
        return total
    }

    fun layout(source: String, size: Float) = MathTex.layout(source, size.toDouble(), ::measure)

    /** Draw with the top left corner at (x, y). */
    fun draw(canvas: Canvas, formula: MathTex.Formula, x: Float, y: Float, color: Int) {
        val fill = Paint(Paint.ANTI_ALIAS_FLAG)
        val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND
            strokeJoin = Paint.Join.ROUND
        }
        for (op in formula.ops) when (op) {
            is MathTex.Text -> {
                val paint = paint(op.style)
                paint.textSize = op.size.toFloat()
                paint.color = if (op.style == "err") ERROR_COLOR else color
                canvas.drawText(op.text, x + op.x.toFloat(), y + op.y.toFloat(), paint)
            }
            is MathTex.Rule -> {
                fill.color = color
                canvas.drawRect(x + op.x.toFloat(), y + op.y.toFloat(), x + (op.x + op.w).toFloat(), y + (op.y + op.h).toFloat(), fill)
            }
            is MathTex.Path -> {
                stroke.color = color
                stroke.strokeWidth = op.thick.toFloat()
                val path = android.graphics.Path()
                op.points.forEachIndexed { index, (px, py) ->
                    if (index == 0) path.moveTo(x + px.toFloat(), y + py.toFloat()) else path.lineTo(x + px.toFloat(), y + py.toFloat())
                }
                canvas.drawPath(path, stroke)
            }
        }
    }

    /** A formula as an editor object: set once, drawn on every frame without setting it again.
     *  An empty formula shows a faint "Formel" to tap on. */
    class FormulaDrawable(source: String, size: Float, private val color: Int, private val pad: Float, lineWidth: Int) : Drawable() {
        private val empty = source.isBlank()
        private val formula = layout(if (empty) tr("\\text{Formel}") else source, size)

        init {
            // As wide as the line, the formula centered in it (wider ones stick out to the right like a table).
            setBounds(0, 0, maxOf(lineWidth, (formula.width + 2 * pad).toInt() + 1), (formula.height + 2 * pad).toInt() + 1)
        }

        override fun draw(canvas: Canvas) {
            val shown = if (empty) (color and 0x00FFFFFF) or 0x66000000 else color
            val left = bounds.left + maxOf(pad, (bounds.width() - formula.width.toFloat()) / 2)
            draw(canvas, formula, left, bounds.top + pad, shown)
        }

        override fun setAlpha(alpha: Int) {}
        override fun setColorFilter(colorFilter: ColorFilter?) {}
        @Deprecated("Deprecated in Java")
        override fun getOpacity() = PixelFormat.TRANSLUCENT
    }
}
