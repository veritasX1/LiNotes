package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/** One running upload: name, percent and a bar – so nobody attaches the same photo twice. */
@Composable
fun UploadRow(upload: AppState.Upload, modifier: Modifier = Modifier) {
    val colors = palette
    Column(modifier) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            GlyphIcon(Glyph.Export, colors.accentText, 18.dp)
            Spacer(Modifier.width(8.dp))
            Text(tr("„{name}“ wird hochgeladen", "name" to upload.name), style = Type.subheadline, color = colors.label,
                maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            Spacer(Modifier.width(8.dp))
            Text("${(upload.progress * 100).toInt()} %", style = Type.subheadline, color = colors.secondary)
        }
        Spacer(Modifier.height(6.dp))
        LinearProgressIndicator(
            progress = { upload.progress },
            modifier = Modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(2.dp)),
            color = colors.accent, trackColor = colors.fill, strokeCap = StrokeCap.Round, gapSize = 0.dp,
            drawStopIndicator = {},
        )
    }
}

/** Floating above everything of the main window while uploads run (the app stays usable). */
@Composable
fun UploadBanner(state: AppState, modifier: Modifier = Modifier) {
    if (state.uploads.isEmpty()) return
    val colors = palette
    Column(
        modifier.padding(horizontal = 16.dp).fillMaxWidth()
            .shadow(8.dp, RoundedCornerShape(14.dp)).clip(RoundedCornerShape(14.dp)).background(colors.surface)
            .padding(horizontal = 14.dp, vertical = 12.dp),
    ) {
        state.uploads.forEachIndexed { index, upload ->
            if (index > 0) Spacer(Modifier.height(10.dp))
            UploadRow(upload)
        }
    }
}

/** The uploads going to one place (e.g. a card's attachments), as rows of a form section. */
@Composable
fun UploadRows(state: AppState, target: String) {
    state.uploads.filter { it.target == target }.forEach { upload ->
        UploadRow(upload, Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp))
    }
}
