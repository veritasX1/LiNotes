package io.github.veritasx1.linotes.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** LiNotes' own symbols (same shapes as on Linux), drawn on a 16×16 grid. */
enum class Glyph { Folder, FolderShared, Notes, Lock, LockOpen, Trash, Compose, Checklist, Format, Photo, Share, Cart,
    Board, Tag, Pin, Plus, More, Back, Chevron, Search, Person, Cloud, CloudOff, Close, Gear, Grid, ListLines,
    FolderPlus, Key, Fingerprint, Password, UpDown, Mic, Table, Export, Globe }

@Composable
fun GlyphIcon(glyph: Glyph, tint: Color, size: Dp = 22.dp, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size)) {
        val scale = this.size.minDimension / 16f
        drawGlyph(glyph, tint, scale)
    }
}

private fun DrawScope.drawGlyph(glyph: Glyph, color: Color, s: Float) {
    fun p(x: Float, y: Float) = Offset(x * s, y * s)
    fun line(width: Float = 1.35f) = Stroke(width * s, cap = StrokeCap.Round, join = StrokeJoin.Round)
    fun path(block: Path.() -> Unit) = Path().apply(block)
    fun Path.m(x: Float, y: Float) = moveTo(x * s, y * s)
    fun Path.l(x: Float, y: Float) = lineTo(x * s, y * s)
    fun Path.c(a: Float, b: Float, c: Float, d: Float, e: Float, f: Float) = cubicTo(a * s, b * s, c * s, d * s, e * s, f * s)
    fun rrect(x: Float, y: Float, w: Float, h: Float, r: Float, width: Float = 1.35f) =
        drawRoundRect(color, p(x, y), Size(w * s, h * s), CornerRadius(r * s), style = line(width))

    when (glyph) {
        Glyph.Folder, Glyph.FolderShared, Glyph.FolderPlus -> {
            drawPath(path {
                m(1.5f, 4f); c(1.5f, 3f, 2f, 2.5f, 3f, 2.5f); l(6f, 2.5f); l(7.5f, 4.5f); l(13f, 4.5f)
                c(14f, 4.5f, 14.5f, 5f, 14.5f, 6f); l(14.5f, 12.5f); c(14.5f, 13.5f, 14f, 14f, 13f, 14f)
                l(3f, 14f); c(2f, 14f, 1.5f, 13.5f, 1.5f, 12.5f); close()
            }, color, style = line())
            drawLine(color, p(1.5f, 6.5f), p(14.5f, 6.5f), 1f * s)
            if (glyph == Glyph.FolderShared) {
                drawCircle(color, 1.3f * s, p(8f, 9f))
                drawPath(path { m(5.5f, 12.8f); c(5.5f, 10.6f, 10.5f, 10.6f, 10.5f, 12.8f) }, color, style = line(1f))
            }
            if (glyph == Glyph.FolderPlus) {
                drawLine(color, p(8f, 8.3f), p(8f, 12.2f), 1.2f * s, StrokeCap.Round)
                drawLine(color, p(6.05f, 10.25f), p(9.95f, 10.25f), 1.2f * s, StrokeCap.Round)
            }
        }
        Glyph.Key -> {
            drawCircle(color, 2.8f * s, p(4.8f, 8f), style = line())
            drawLine(color, p(7.6f, 8f), p(14.5f, 8f), 1.35f * s, StrokeCap.Round)
            drawLine(color, p(12.2f, 8f), p(12.2f, 10.6f), 1.35f * s, StrokeCap.Round)
            drawLine(color, p(14.3f, 8f), p(14.3f, 10f), 1.35f * s, StrokeCap.Round)
        }
        Glyph.Fingerprint -> {
            fun arc(r: Float, start: Float, sweep: Float) =
                drawArc(color, start, sweep, false, p(8f - r, 8.5f - r), Size(2 * r * s, 2 * r * s), style = line(1.1f))
            arc(6.3f, 200f, 140f)
            arc(4.2f, 180f, 180f)
            arc(2.1f, 180f, 180f)
            drawLine(color, p(3.8f, 8.5f), p(3.8f, 11.5f), 1.1f * s, StrokeCap.Round)
            drawLine(color, p(12.2f, 8.5f), p(12.2f, 13f), 1.1f * s, StrokeCap.Round)
            drawLine(color, p(5.9f, 8.5f), p(5.9f, 14f), 1.1f * s, StrokeCap.Round)
            drawLine(color, p(10.1f, 8.5f), p(10.1f, 12f), 1.1f * s, StrokeCap.Round)
            drawLine(color, p(8f, 8.5f), p(8f, 14.5f), 1.1f * s, StrokeCap.Round)
        }
        Glyph.Password -> {
            rrect(1.5f, 4.5f, 13f, 7f, 2f)
            for (x in listOf(5f, 8f, 11f)) drawCircle(color, 1f * s, p(x, 8f))
        }
        Glyph.UpDown -> {
            drawPath(path { m(5f, 6.5f); l(8f, 3.5f); l(11f, 6.5f) }, color, style = line(1.6f))
            drawPath(path { m(5f, 9.5f); l(8f, 12.5f); l(11f, 9.5f) }, color, style = line(1.6f))
        }
        Glyph.Notes -> {
            rrect(2f, 1.5f, 12f, 13f, 2f)
            drawLine(color, p(2f, 5f), p(14f, 5f), 1f * s)
            drawLine(color, p(4.5f, 8f), p(11.5f, 8f), 1f * s, StrokeCap.Round)
            drawLine(color, p(4.5f, 10.5f), p(11.5f, 10.5f), 1f * s, StrokeCap.Round)
        }
        Glyph.Lock, Glyph.LockOpen -> {
            rrect(3f, 7f, 10f, 7.5f, 1.6f)
            drawPath(path {
                m(5f, 7f); l(5f, 5f)
                if (glyph == Glyph.Lock) { c(5f, 1.5f, 11f, 1.5f, 11f, 5f); l(11f, 7f) } else c(5f, 1.5f, 11f, 1.5f, 11f, 4f)
            }, color, style = line())
        }
        Glyph.Trash -> {
            drawLine(color, p(2f, 4f), p(14f, 4f), 1.35f * s, StrokeCap.Round)
            drawPath(path { m(6f, 4f); l(6.5f, 2f); l(9.5f, 2f); l(10f, 4f) }, color, style = line(1.1f))
            drawPath(path { m(3.5f, 4f); l(4.5f, 14.5f); l(11.5f, 14.5f); l(12.5f, 4f) }, color, style = line())
            drawLine(color, p(6.5f, 6.5f), p(6.5f, 12f), 1f * s, StrokeCap.Round)
            drawLine(color, p(9.5f, 6.5f), p(9.5f, 12f), 1f * s, StrokeCap.Round)
        }
        Glyph.Compose -> {
            drawPath(path {
                m(8.5f, 2.5f); l(3.5f, 2.5f); c(2.4f, 2.5f, 1.5f, 3.4f, 1.5f, 4.5f); l(1.5f, 12.5f)
                c(1.5f, 13.6f, 2.4f, 14.5f, 3.5f, 14.5f); l(11.5f, 14.5f); c(12.6f, 14.5f, 13.5f, 13.6f, 13.5f, 12.5f); l(13.5f, 7.5f)
            }, color, style = line())
            drawPath(path { m(6.5f, 9.5f); l(7f, 7.4f); l(12.6f, 1.8f); l(14.2f, 3.4f); l(8.6f, 9f); close() }, color, style = line(1.15f))
        }
        Glyph.Checklist -> for (y in listOf(4f, 8f, 12f)) {
            drawCircle(color, 1.7f * s, p(3f, y), style = line(1.1f))
            drawLine(color, p(6.5f, y), p(14.5f, y), 1.3f * s, StrokeCap.Round)
        }
        Glyph.Format -> {
            drawPath(path { m(1f, 13f); l(5f, 3f); l(9f, 13f); m(2.4f, 9.6f); l(7.6f, 9.6f) }, color, style = line(1.3f))
            drawCircle(color, 2.3f * s, p(12.2f, 10.6f), style = line(1.2f))
            drawLine(color, p(14.5f, 7.8f), p(14.5f, 13f), 1.2f * s, StrokeCap.Round)
        }
        Glyph.Table -> {
            rrect(1.5f, 2.5f, 13f, 11f, 1.5f)
            for (y in listOf(6.2f, 9.8f)) drawLine(color, p(1.5f, y), p(14.5f, y), 1.1f * s)
            for (x in listOf(5.8f, 10.2f)) drawLine(color, p(x, 2.5f), p(x, 13.5f), 1.1f * s)
        }
        Glyph.Mic -> {
            rrect(5.5f, 1.5f, 5f, 8.5f, 2.5f)
            drawPath(path { m(3f, 7.5f); c(3f, 13f, 13f, 13f, 13f, 7.5f) }, color, style = line())
            drawLine(color, p(8f, 11.8f), p(8f, 14.5f), 1.35f * s, StrokeCap.Round)
        }
        Glyph.Photo -> {
            rrect(1.5f, 2.5f, 13f, 11f, 2f)
            drawCircle(color, 1.3f * s, p(10.5f, 6f))
            drawPath(path { m(1.5f, 12f); l(5.5f, 7.5f); l(9f, 11f); l(10.8f, 9.3f); l(14.5f, 12.5f) }, color, style = line(1.2f))
        }
        Glyph.Share, Glyph.Person -> {
            drawCircle(color, 2.6f * s, p(if (glyph == Glyph.Share) 6f else 8f, 5f), style = line())
            drawPath(path {
                if (glyph == Glyph.Share) { m(1.5f, 14f); c(1.5f, 10f, 10.5f, 10f, 10.5f, 14f) } else { m(2.5f, 14.5f); c(2.5f, 9.5f, 13.5f, 9.5f, 13.5f, 14.5f) }
            }, color, style = line())
            if (glyph == Glyph.Share) {
                drawLine(color, p(13f, 4f), p(13f, 9f), 1.35f * s, StrokeCap.Round)
                drawLine(color, p(10.5f, 6.5f), p(15.5f, 6.5f), 1.35f * s, StrokeCap.Round)
            }
        }
        Glyph.Globe -> {
            // A globe (web pages): circle, a meridian and the equator.
            drawCircle(color, 6.5f * s, p(8f, 8f), style = line())
            drawOval(color, p(5.2f, 1.5f), androidx.compose.ui.geometry.Size(5.6f * s, 13f * s), style = line())
            drawLine(color, p(1.5f, 8f), p(14.5f, 8f), 1.35f * s, StrokeCap.Round)
        }
        Glyph.Export -> {
            // Apple's export symbol: a tray with an arrow leaving upwards.
            drawPath(path { m(5.5f, 6.5f); l(3.5f, 6.5f); l(3.5f, 14.5f); l(12.5f, 14.5f); l(12.5f, 6.5f); l(10.5f, 6.5f) }, color, style = line())
            drawPath(path { m(8f, 10f); l(8f, 1.8f); m(5.3f, 4.3f); l(8f, 1.6f); l(10.7f, 4.3f) }, color, style = line())
        }
        Glyph.Cart -> {
            // A receipt (Kassenzettel) – a cart would suggest buying in the app.
            drawPath(path { m(3f, 14.5f); l(3f, 1.5f); l(13f, 1.5f); l(13f, 14.5f); l(11.33f, 13f); l(9.67f, 14.5f); l(8f, 13f)
                l(6.33f, 14.5f); l(4.67f, 13f); l(3f, 14.5f) }, color, style = line())
            drawPath(path { m(5.5f, 4.5f); l(10.5f, 4.5f); m(5.5f, 7f); l(10.5f, 7f); m(5.5f, 9.5f); l(8.5f, 9.5f) }, color, style = line(1f))
        }
        Glyph.Board -> {
            rrect(1.5f, 2.5f, 3.6f, 11f, 1f, 1.2f)
            rrect(6.2f, 2.5f, 3.6f, 7f, 1f, 1.2f)
            rrect(10.9f, 2.5f, 3.6f, 9f, 1f, 1.2f)
        }
        Glyph.Tag -> drawPath(path { m(3f, 6f); l(14f, 6f); m(2f, 10.5f); l(13f, 10.5f); m(6.5f, 2f); l(5f, 14.5f); m(11f, 2f); l(9.5f, 14.5f) }, color, style = line(1.3f))
        Glyph.Pin -> {
            drawPath(path { m(5.5f, 1.5f); l(10.5f, 1.5f); m(6.5f, 1.5f); l(6f, 6.5f); l(3.5f, 9f); l(12.5f, 9f); l(10f, 6.5f); l(9.5f, 1.5f) }, color, style = line())
            drawLine(color, p(8f, 9f), p(8f, 15f), 1.35f * s, StrokeCap.Round)
        }
        Glyph.Plus -> {
            drawLine(color, p(8f, 2f), p(8f, 14f), 1.8f * s, StrokeCap.Round)
            drawLine(color, p(2f, 8f), p(14f, 8f), 1.8f * s, StrokeCap.Round)
        }
        Glyph.More -> {
            drawCircle(color, 6.7f * s, p(8f, 8f), style = line())
            for (x in listOf(5f, 8f, 11f)) drawCircle(color, 0.95f * s, p(x, 8f))
        }
        Glyph.Back -> drawPath(path { m(10.5f, 2f); l(4.5f, 8f); l(10.5f, 14f) }, color, style = line(2.1f))
        Glyph.Chevron -> drawPath(path { m(6f, 3f); l(11f, 8f); l(6f, 13f) }, color, style = line(1.8f))
        Glyph.Search -> {
            drawCircle(color, 4.6f * s, p(6.8f, 6.8f), style = line())
            drawLine(color, p(10.2f, 10.2f), p(14.2f, 14.2f), 1.8f * s, StrokeCap.Round)
        }
        Glyph.Cloud, Glyph.CloudOff -> {
            drawPath(path { m(4.5f, 12.5f); c(1.5f, 12.5f, 1f, 8.5f, 4f, 8f); c(4.2f, 4f, 10f, 3.5f, 11f, 7f); c(15f, 7f, 15.2f, 12.5f, 11.5f, 12.5f); close() }, color, style = line(1.3f))
            if (glyph == Glyph.CloudOff) drawLine(color, p(2f, 2f), p(14f, 14f), 1.3f * s, StrokeCap.Round)
        }
        Glyph.Close -> {
            drawLine(color, p(3.5f, 3.5f), p(12.5f, 12.5f), 1.8f * s, StrokeCap.Round)
            drawLine(color, p(12.5f, 3.5f), p(3.5f, 12.5f), 1.8f * s, StrokeCap.Round)
        }
        Glyph.Gear -> {
            drawCircle(color, 2.4f * s, p(8f, 8f), style = line())
            for (i in 0 until 8) {
                val a = Math.toRadians(i * 45.0)
                drawLine(color, p(8f + 4.2f * Math.cos(a).toFloat(), 8f + 4.2f * Math.sin(a).toFloat()),
                    p(8f + 6.4f * Math.cos(a).toFloat(), 8f + 6.4f * Math.sin(a).toFloat()), 1.8f * s, StrokeCap.Round)
            }
            drawCircle(color, 4.3f * s, p(8f, 8f), style = line(1.2f))
        }
        Glyph.Grid -> for (x in listOf(1.5f, 8.8f)) for (y in listOf(1.5f, 8.8f)) rrect(x, y, 5.7f, 5.7f, 1.2f, 1.2f)
        Glyph.ListLines -> for (y in listOf(3.5f, 8f, 12.5f)) drawLine(color, p(1.5f, y), p(14.5f, y), 1.4f * s, StrokeCap.Round)
    }
}

/** The round check button of Reminders / Notes checklists. */
@Composable
fun CheckCircleIcon(checked: Boolean, accent: Color, ring: Color, size: Dp = 24.dp, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size)) {
        val radius = this.size.minDimension / 2 - 1.5f
        val center = Offset(this.size.width / 2, this.size.height / 2)
        if (checked) {
            drawCircle(accent, radius, center, style = Fill)
            val path = Path().apply {
                moveTo(center.x - radius * 0.45f, center.y + radius * 0.02f)
                lineTo(center.x - radius * 0.1f, center.y + radius * 0.38f)
                lineTo(center.x + radius * 0.5f, center.y - radius * 0.35f)
            }
            drawPath(path, Color.White, style = Stroke(2.2f * density, cap = StrokeCap.Round, join = StrokeJoin.Round))
        } else {
            drawCircle(ring, radius, center, style = Stroke(1.6f * density))
        }
    }
}
