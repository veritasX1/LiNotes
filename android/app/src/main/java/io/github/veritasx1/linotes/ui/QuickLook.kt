package io.github.veritasx1.linotes.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color as AndroidColor
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import android.widget.MediaController
import android.widget.VideoView
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

/** An attachment shown inside LiNotes (like Quick Look on the iPhone, a small Prevux):
 *  pictures, PDFs, text, audio and video without switching apps; "Teilen" hands it on. */
data class LookFile(val file: File, val mime: String)

private const val TEXT_LIMIT = 1024 * 1024
private const val PDF_PAGE_LIMIT = 300
private val TEXT_TYPES = setOf("application/json", "application/xml", "application/x-yaml", "application/javascript",
    "application/x-sh", "application/sql", "application/csv")

internal fun lookKind(file: File, mime: String): String = when {
    mime.startsWith("image/") -> "image"
    mime == "application/pdf" || file.extension.equals("pdf", ignoreCase = true) -> "pdf"
    mime.startsWith("audio/") || mime.startsWith("video/") -> "media"
    mime.startsWith("text/") || mime in TEXT_TYPES -> "text"
    else -> "other"
}

internal fun sizeText(bytes: Long): String {
    var size = bytes.toDouble()
    for (unit in listOf("Bytes", "KB", "MB")) {
        if (size < 1024) return if (unit == "Bytes") "${size.toLong()} $unit" else String.format(java.util.Locale.GERMANY, "%.1f %s", size, unit)
        size /= 1024
    }
    return String.format(java.util.Locale.GERMANY, "%.1f GB", size)
}

@Composable
fun QuickLookOverlay(state: AppState) {
    val look = state.quickLook ?: return
    val colors = palette
    var shareMenu by remember { mutableStateOf(false) }
    // A window of its own: attachments are also opened from the card sheet, itself a dialog window.
    Dialog(onDismissRequest = { state.quickLook = null },
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        UseWholeScreen()
        // The dialog window has its own system bars: dark symbols on the light page (and the other way round).
        val view = androidx.compose.ui.platform.LocalView.current
        androidx.compose.runtime.SideEffect {
            (view.parent as? androidx.compose.ui.window.DialogWindowProvider)?.window?.let { window ->
                androidx.core.view.WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = !colors.dark
                    isAppearanceLightNavigationBars = !colors.dark
                }
            }
        }
        Column(
            Modifier.fillMaxSize().background(colors.plain)
                // Swallow touches, so nothing below reacts.
                .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {}
                .statusBarsPadding().navigationBarsPadding(),
        ) {
            Row(Modifier.fillMaxWidth().height(52.dp).padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f)) { TextButton("Fertig", bold = true) { state.quickLook = null } }
                Column(Modifier.weight(2f), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(look.file.name, style = Type.headline, color = colors.label, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(sizeText(look.file.length()), style = Type.caption, color = colors.secondary)
                }
                Box(Modifier.weight(1f), contentAlignment = Alignment.CenterEnd) {
                    BarButton(Glyph.Export, "Teilen") { shareMenu = true }
                }
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when (lookKind(look.file, look.mime)) {
                    "image" -> ImageLook(look.file) { OtherLook(state, look) }
                    "pdf" -> PdfLook(look.file) { OtherLook(state, look) }
                    "media" -> MediaLook(look.file)
                    "text" -> TextLook(look.file)
                    else -> OtherLook(state, look)
                }
            }
        }
    }
    if (shareMenu) ActionSheet(look.file.name, listOf(
        SheetAction("Teilen …") { state.shareFile(look.file, look.mime, look.file.name) },
        SheetAction("Mit anderer App öffnen …") { state.openFile(look.file, look.mime) },
    )) { shareMenu = false }
}

@Composable
private fun ImageLook(file: File, failed: @Composable () -> Unit) {
    val bitmap by produceState<Bitmap?>(null, file) {
        value = withContext(Dispatchers.IO) { decodeSampled(file, 2560) }
    }
    var loaded by remember(file) { mutableStateOf(false) }
    LaunchedEffect(bitmap) { if (bitmap != null) loaded = true }
    val image = bitmap
    if (image == null) {
        // decodeSampled returns null for broken files; give it a moment before saying so.
        var gaveUp by remember(file) { mutableStateOf(false) }
        LaunchedEffect(file) { kotlinx.coroutines.delay(1500); gaveUp = true }
        if (gaveUp && !loaded) failed()
        return
    }
    ZoomBox { Image(image.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Fit) }
}

/** Two fingers zoom and move, a double tap goes back (or zooms in). */
@Composable
private fun ZoomBox(content: @Composable () -> Unit) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    Box(
        // Clipped, so a zoomed picture stays below the bar with "Fertig".
        Modifier.fillMaxSize().clipToBounds()
            .pointerInput(Unit) {
                detectTransformGestures { _, pan, zoom, _ ->
                    scale = (scale * zoom).coerceIn(1f, 8f)
                    offset = if (scale == 1f) Offset.Zero else offset + pan
                }
            }
            .pointerInput(Unit) {
                detectTapGestures(onDoubleTap = {
                    if (scale > 1f) { scale = 1f; offset = Offset.Zero } else scale = 2.5f
                })
            }
    ) {
        Box(Modifier.fillMaxSize().graphicsLayer { scaleX = scale; scaleY = scale; translationX = offset.x; translationY = offset.y }) {
            content()
        }
    }
}

private fun decodeSampled(file: File, max: Int): Bitmap? = try {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.path, bounds)
    var sample = 1
    while (bounds.outWidth / (sample * 2) >= max || bounds.outHeight / (sample * 2) >= max) sample *= 2
    BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample })
} catch (error: Exception) {
    null
}

@Composable
private fun PdfLook(file: File, failed: @Composable () -> Unit) {
    // PdfRenderer is not thread-safe: one page at a time.
    val lock = remember { Mutex() }
    val renderer by produceState<PdfRenderer?>(null, file) {
        value = withContext(Dispatchers.IO) {
            try { PdfRenderer(ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)) } catch (error: Exception) { null }
        }
    }
    var openFailed by remember(file) { mutableStateOf(false) }
    LaunchedEffect(file) { kotlinx.coroutines.delay(2000); if (renderer == null) openFailed = true }
    val pdf = renderer
    // Close exactly the renderer this effect was started for (reading `renderer` here would close the new one).
    DisposableEffect(pdf) { onDispose { pdf?.let { kotlinx.coroutines.runBlocking { lock.withLock { it.close() } } } } }
    if (pdf == null) {
        if (openFailed) failed()
        return
    }
    val count = pdf.pageCount
    val sizes = remember(pdf) { List(count.coerceAtMost(PDF_PAGE_LIMIT)) { index -> pdf.openPage(index).use { it.width to it.height } } }
    BoxWithConstraints(Modifier.fillMaxSize().background(palette.background)) {
        val widthPx = with(LocalDensity.current) { (maxWidth - 24.dp).toPx() }.toInt().coerceIn(200, 1600)
        ZoomBox {
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(sizes.size) { index ->
                    val (pageWidth, pageHeight) = sizes[index]
                    val page by produceState<Bitmap?>(null, pdf, index, widthPx) {
                        value = withContext(Dispatchers.IO) {
                            lock.withLock {
                                try {
                                    pdf.openPage(index).use { source ->
                                        val height = (widthPx.toLong() * pageHeight / pageWidth).toInt().coerceAtLeast(1)
                                        Bitmap.createBitmap(widthPx, height, Bitmap.Config.ARGB_8888).also { bitmap ->
                                            bitmap.eraseColor(AndroidColor.WHITE)
                                            source.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                                        }
                                    }
                                } catch (error: Exception) { null }
                            }
                        }
                    }
                    Box(Modifier.fillMaxWidth().aspectRatio(pageWidth.toFloat() / pageHeight).background(Color.White)) {
                        page?.let { Image(it.asImageBitmap(), "Seite ${index + 1}", Modifier.fillMaxSize()) }
                    }
                }
                if (count > PDF_PAGE_LIMIT) item {
                    Text("Die ersten $PDF_PAGE_LIMIT von $count Seiten – alle über „Teilen“ in einer anderen App.",
                        style = Type.footnote, color = palette.secondary, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                }
            }
        }
    }
}

@Composable
private fun TextLook(file: File) {
    val text by produceState("", file) {
        value = withContext(Dispatchers.IO) {
            file.inputStream().use { input -> String(input.readNBytesCompat(TEXT_LIMIT), Charsets.UTF_8) }
        }
    }
    SelectionContainer {
        Text(text, style = Type.body.copy(fontFamily = FontFamily.Monospace), color = palette.label,
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp))
    }
}

private fun java.io.InputStream.readNBytesCompat(limit: Int): ByteArray {
    val buffer = ByteArray(limit)
    var read = 0
    while (read < limit) {
        val count = read(buffer, read, limit - read)
        if (count < 0) break
        read += count
    }
    return buffer.copyOf(read)
}

@Composable
private fun MediaLook(file: File) {
    AndroidView(
        factory = { context ->
            VideoView(context).apply {
                setVideoPath(file.path)
                val controller = MediaController(context)
                controller.setAnchorView(this)
                setMediaController(controller)
                setOnPreparedListener { controller.show(0) }
            }
        },
        onRelease = { it.stopPlayback() },
        modifier = Modifier.fillMaxSize(),
    )
}

@Composable
private fun OtherLook(state: AppState, look: LookFile) {
    val colors = palette
    Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        GlyphIcon(Glyph.Notes, colors.tertiary, 64.dp)
        Spacer(Modifier.height(14.dp))
        Text(look.file.name, style = Type.title3, color = colors.label, textAlign = TextAlign.Center)
        Spacer(Modifier.height(6.dp))
        Text("Für diese Datei gibt es keine Vorschau.", style = Type.subheadline, color = colors.secondary, textAlign = TextAlign.Center)
        Spacer(Modifier.height(20.dp))
        Box(Modifier.clip(RoundedCornerShape(22.dp)).background(colors.accent).clickable { state.openFile(look.file, look.mime) }
            .padding(horizontal = 22.dp, vertical = 12.dp)) {
            Text("Mit anderer App öffnen …", style = Type.headline.copy(fontWeight = FontWeight.SemiBold), color = Color.White)
        }
    }
}
