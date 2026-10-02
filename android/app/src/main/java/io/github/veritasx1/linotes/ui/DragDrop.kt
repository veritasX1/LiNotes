package io.github.veritasx1.linotes.ui

import android.content.ClipData
import android.content.ClipDescription
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.draganddrop.dragAndDropSource
import androidx.compose.foundation.draganddrop.dragAndDropTarget
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.awaitLongPressOrCancellation
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draganddrop.DragAndDropEvent
import androidx.compose.ui.draganddrop.DragAndDropTarget
import androidx.compose.ui.draganddrop.DragAndDropTransferData
import androidx.compose.ui.draganddrop.mimeTypes
import androidx.compose.ui.draganddrop.toAndroidDragEvent
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.unit.dp

/** Like iOS: press and hold, then release = context menu (onLongClick); press, hold and
 *  move = drag `payload` ("<kind>:<id>") somewhere, e.g. onto a folder. Taps stay with
 *  the clickable before this modifier. */
@Suppress("DEPRECATION")
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun Modifier.holdToDrag(payload: String, onLongClick: (() -> Unit)?): Modifier {
    val menu by rememberUpdatedState(onLongClick)
    val shadow = palette.accent.copy(alpha = 0.35f)
    // The drag shadow is drawn here: the default one records the content into a picture
    // that is not redrawn when e.g. a thumbnail inside finishes loading (empty previews).
    return dragAndDropSource(drawDragDecoration = {
        drawRoundRect(shadow, cornerRadius = androidx.compose.ui.geometry.CornerRadius(10.dp.toPx()))
    }) {
        awaitEachGesture {
            val down = awaitFirstDown(requireUnconsumed = false)
            val press = awaitLongPressOrCancellation(down.id) ?: return@awaitEachGesture
            while (true) {
                // Initial pass: after a long press the clickable must not see the release as a tap.
                val change = awaitPointerEvent(PointerEventPass.Initial).changes.firstOrNull { it.id == press.id } ?: break
                if (!change.pressed) {
                    change.consume()
                    menu?.invoke()
                    break
                }
                if ((change.position - press.position).getDistance() > viewConfiguration.touchSlop) {
                    change.consume()
                    startTransfer(DragAndDropTransferData(ClipData.newPlainText("linotes", payload)))
                    break
                }
            }
        }
    }
}

/** Highlights while something acceptable is dragged over it; onDrop(payload) moves it. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun Modifier.dropZone(accept: (String) -> Boolean, onDrop: (String) -> Unit): Modifier {
    val colors = palette
    var hovering by remember { mutableStateOf(false) }
    val currentAccept by rememberUpdatedState(accept)
    val currentDrop by rememberUpdatedState(onDrop)
    val target = remember {
        object : DragAndDropTarget {
            fun payload(event: DragAndDropEvent): String? =
                event.toAndroidDragEvent().clipData?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.text?.toString()

            override fun onEntered(event: DragAndDropEvent) { hovering = true }
            override fun onExited(event: DragAndDropEvent) { hovering = false }
            override fun onEnded(event: DragAndDropEvent) { hovering = false }
            override fun onDrop(event: DragAndDropEvent): Boolean {
                hovering = false
                val value = payload(event) ?: return false
                if (!currentAccept(value)) return false
                currentDrop(value)
                return true
            }
        }
    }
    return dragAndDropTarget(
        shouldStartDragAndDrop = { event -> ClipDescription.MIMETYPE_TEXT_PLAIN in event.mimeTypes() },
        target = target,
    ).then(if (hovering) Modifier.background(colors.accent.copy(alpha = 0.25f)) else Modifier)
}
