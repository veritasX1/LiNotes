package io.github.veritasx1.linotes.ui

import android.content.Context
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.os.Build
import android.os.SystemClock
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.delay
import org.json.JSONObject
import java.io.File

/** Audio in notes (like Apple's recordings, without transcription): a recording is an encrypted
 *  file block {"t": "file", "m": "audio/…", "d": seconds} and plays inside the note. Same as Ubuntu's audio.py. */
object AudioNotes {
    /** Opus in Ogg like Ubuntu where the phone can (Android 10+), else AAC. */
    val ogg = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
    val mime = if (ogg) "audio/ogg" else "audio/mp4"
    val extension = if (ogg) "ogg" else "m4a"

    fun isAudio(block: JSONObject) = block.optString("m").startsWith("audio/")

    /** 0:07, 12:34, 1:02:03 */
    fun durationText(seconds: Double): String {
        val total = Math.round(seconds).toInt()
        val hours = total / 3600
        val minutes = total % 3600 / 60
        val rest = total % 60
        return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, rest) else "%d:%02d".format(minutes, rest)
    }

    fun recordingName(): String =
        java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("'Aufnahme' yyyy-MM-dd HH-mm")) + ".$extension"
}

class Recorder(context: Context, val file: File) {
    private val recorder = (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()).apply {
        setAudioSource(MediaRecorder.AudioSource.MIC)
        if (AudioNotes.ogg && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            setOutputFormat(MediaRecorder.OutputFormat.OGG)
            setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
        } else {
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        }
        setAudioEncodingBitRate(32_000)
        setAudioSamplingRate(48_000)
        setOutputFile(file.absolutePath)
    }
    private var started = 0L

    fun start() {
        recorder.prepare()
        recorder.start()
        started = SystemClock.elapsedRealtime()
    }

    fun elapsed(): Double = if (started == 0L) 0.0 else (SystemClock.elapsedRealtime() - started) / 1000.0

    /** Finish the file; returns its length in seconds, or null if nothing usable was recorded. */
    fun stop(keep: Boolean): Double? {
        val length = elapsed()
        val ok = try { recorder.stop(); true } catch (error: RuntimeException) { false }  // stop() throws if too short
        recorder.release()
        if (!keep || !ok || length < 0.5) { file.delete(); return null }
        return length
    }
}

/** Red dot and running time; "Fertig" keeps the recording, "Abbrechen" throws it away. */
@Composable
fun RecordDialog(onDone: (File, Double) -> Unit, onFailed: (String) -> Unit, onCancel: () -> Unit) {
    val colors = palette
    val context = LocalContext.current
    var elapsed by remember { mutableStateOf(0.0) }
    val recorder = remember {
        val folder = File(context.cacheDir, "recordings").apply { mkdirs() }
        try { Recorder(context, File(folder, AudioNotes.recordingName())).also { it.start() } } catch (error: Exception) { null }
    }
    var finished by remember { mutableStateOf(false) }
    fun finish(keep: Boolean) {
        if (finished || recorder == null) return
        finished = true
        val length = recorder.stop(keep)
        when {
            !keep -> onCancel()
            length == null -> onFailed("Die Aufnahme war zu kurz.")
            else -> onDone(recorder.file, length)
        }
    }
    LaunchedEffect(recorder) {
        if (recorder == null) { onFailed("Das Mikrofon lässt sich nicht öffnen."); return@LaunchedEffect }
        while (!finished) { elapsed = recorder.elapsed(); delay(250) }
    }
    DisposableEffect(Unit) { onDispose { finish(false) } }
    if (recorder == null) return
    Dialog(onDismissRequest = { finish(false) }, properties = DialogProperties(dismissOnClickOutside = false)) {
        Column(
            Modifier.width(290.dp).clip(RoundedCornerShape(14.dp)).background(if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2)),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Audioaufnahme", style = Type.headline, color = colors.label)
                Spacer(Modifier.height(14.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(14.dp).background(colors.red, CircleShape))
                    Spacer(Modifier.width(10.dp))
                    Text(AudioNotes.durationText(elapsed), style = Type.title1, color = colors.label)
                }
                Spacer(Modifier.height(6.dp))
                Text("Aufnahme läuft …", style = Type.footnote, color = colors.secondary)
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().height(46.dp)) {
                Box(Modifier.weight(1f).fillMaxSize().clickable { finish(false) }, contentAlignment = Alignment.Center) {
                    Text("Abbrechen", style = Type.body, color = colors.accentText)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(Modifier.weight(1f).fillMaxSize().clickable { finish(true) }, contentAlignment = Alignment.Center) {
                    Text("Fertig", style = Type.headline, color = colors.accentText)
                }
            }
        }
    }
}

/** Plays one recording at a time inside the note. */
class AudioPlayer {
    var playing by mutableStateOf<String?>(null)  // file id
        private set
    var position by mutableLongStateOf(0L)
    var length by mutableLongStateOf(0L)
    private var player: MediaPlayer? = null

    fun play(fileId: String, file: File) {
        stop()
        player = MediaPlayer().apply {
            setDataSource(file.absolutePath)
            setOnCompletionListener { stop() }
            prepare()
            start()
        }
        length = player?.duration?.toLong() ?: 0L
        playing = fileId
    }

    fun update() { player?.let { position = it.currentPosition.toLong() } }

    fun stop() {
        player?.release()
        player = null
        playing = null
        position = 0
    }
}

/** While a recording plays: time and a stop button at the bottom of the note. */
@Composable
fun PlayerBar(player: AudioPlayer) {
    val colors = palette
    if (player.playing == null) return
    LaunchedEffect(player.playing) { while (player.playing != null) { player.update(); delay(200) } }
    Row(
        Modifier.fillMaxWidth().background(colors.surface).padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text("Audioaufnahme  ${AudioNotes.durationText(player.position / 1000.0)} / ${AudioNotes.durationText(player.length / 1000.0)}",
            style = Type.subheadline, color = colors.label)
        Text("Stopp", style = Type.headline, color = colors.accentText, modifier = Modifier.clickable { player.stop() }.padding(6.dp))
    }
}
