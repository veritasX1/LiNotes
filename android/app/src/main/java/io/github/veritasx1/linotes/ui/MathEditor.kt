package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import org.json.JSONObject

/** Editing a formula (Profi-Funktion): LaTeX source above, the set formula live below – like the
 *  popover on Ubuntu. Returns the new block, or null to delete it. */
@Composable
fun MathEditor(block: JSONObject, onDone: (JSONObject?) -> Unit, onCancel: () -> Unit) {
    Dialog(onDismissRequest = onCancel) { MathEditorContent(block, onDone, onCancel) }
}

/** The dialog's content (on its own so tests can show it – Robolectric never idles a text field in a Dialog). */
@Composable
fun MathEditorContent(block: JSONObject, onDone: (JSONObject?) -> Unit, onCancel: () -> Unit, picture: Boolean = false) {
    val colors = palette
    var source by remember { mutableStateOf(block.optString("x")) }
    val focus = remember { FocusRequester() }
    val density = LocalDensity.current
    val sizePx = with(density) { 20.dp.toPx() }
    val formula = remember(source) { if (source.isBlank()) null else MathDraw.layout(source, sizePx) }
    run {
        Column(Modifier.width(330.dp).clip(RoundedCornerShape(14.dp)).background(if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2))) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 16.dp)) {
                Text(tr("Formel (LaTeX)"), style = Type.headline, color = colors.label)
                Spacer(Modifier.height(10.dp))
                Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(7.dp)).background(colors.surface).padding(8.dp)) {
                    if (source.isEmpty()) Text("z. B. \\frac{a}{b}", style = Type.subheadline, color = colors.tertiary, fontFamily = FontFamily.Monospace)
                    BasicTextField(
                        source, { source = it }, readOnly = picture,  // picture: for test images (no blinking cursor)
                        textStyle = Type.subheadline.copy(color = colors.label, fontFamily = FontFamily.Monospace),
                        cursorBrush = SolidColor(colors.accent),
                        modifier = Modifier.fillMaxWidth().heightIn(min = 44.dp, max = 140.dp).focusRequester(focus),
                    )
                }
                Spacer(Modifier.height(6.dp))
                Text("x^2   \\sqrt{x}   \\alpha   \\sum_{i=1}^{n}", style = Type.caption, color = colors.secondary, fontFamily = FontFamily.Monospace)
                Spacer(Modifier.height(10.dp))
                // The set formula, made smaller when it is wider than the dialog.
                Box(Modifier.fillMaxWidth().heightIn(min = 48.dp).clip(RoundedCornerShape(7.dp)).background(colors.surface).padding(8.dp),
                    contentAlignment = Alignment.Center) {
                    if (formula != null) {
                        val label = colors.label.toArgb()
                        val room = with(density) { 282.dp.toPx() }
                        val scale = minOf(1f, room / maxOf(1f, formula.width.toFloat()))
                        with(density) {
                            Canvas(Modifier.size((formula.width.toFloat() * scale).toDp(), (formula.height.toFloat() * scale).toDp())) {
                                drawIntoCanvas {
                                    it.nativeCanvas.save()
                                    it.nativeCanvas.scale(scale, scale)
                                    MathDraw.draw(it.nativeCanvas, formula, 0f, 0f, label)
                                    it.nativeCanvas.restore()
                                }
                            }
                        }
                    }
                }
                if (formula?.error == true) {
                    Spacer(Modifier.height(6.dp))
                    Text(tr("Rot markierte Teile kennt LiNotes nicht."), style = Type.caption, color = colors.red)
                }
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().height(46.dp), horizontalArrangement = Arrangement.Center) {
                Box(Modifier.weight(1f).fillMaxSize().clickable { onDone(null) }, contentAlignment = Alignment.Center) {
                    Text(tr("Löschen"), style = Type.body, color = colors.red)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(Modifier.weight(1f).fillMaxSize().clickable(onClick = onCancel), contentAlignment = Alignment.Center) {
                    Text(tr("Abbrechen"), style = Type.body, color = colors.accentText)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(Modifier.weight(1f).fillMaxSize().clickable { onDone(JSONObject(block.toString()).put("x", source)) },
                    contentAlignment = Alignment.Center) {
                    Text(tr("Fertig"), style = Type.headline, color = colors.accentText)
                }
            }
        }
        if (!picture) LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
    }
}
