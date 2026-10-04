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

    const val BARS = 36          // bars of the waveform in the message bubble
    private const val WAVE_RATE = 4000

    /** Loudness per bar of the waveform, 0.08…1 (square root, so quiet speech still shows), like the
     *  bars of a voice message in Apple's Messages. Same rules as audio.peaks on Ubuntu. */
    fun peaks(samples: ShortArray, bars: Int = BARS): FloatArray {
        val count = samples.size.toLong()
        if (count == 0L) return FloatArray(bars) { 0.08f }
        val values = IntArray(bars) { index ->
            val start = (index * count / bars).toInt()
            val end = maxOf(start + 1, ((index + 1) * count / bars).toInt())
            var top = 0
            for (i in start until end) top = maxOf(top, kotlin.math.abs(samples[i].toInt()))
            top
        }
        val top = values.maxOrNull()?.takeIf { it > 0 } ?: 1
        return FloatArray(bars) { (Math.round(maxOf(0.08, kotlin.math.sqrt(values[it].toDouble() / top)) * 1000) / 1000.0).toFloat() }
    }

    /** Read a recording and give its waveform – blocking, run it in the background. Only loudness
     *  leaves this function, nothing is stored. */
    fun waveform(file: File, bars: Int = BARS): FloatArray {
        val extractor = android.media.MediaExtractor()
        var codec: android.media.MediaCodec? = null
        try {
            extractor.setDataSource(file.absolutePath)
            val track = (0 until extractor.trackCount).first {
                extractor.getTrackFormat(it).getString(android.media.MediaFormat.KEY_MIME)?.startsWith("audio/") == true
            }
            extractor.selectTrack(track)
            val format = extractor.getTrackFormat(track)
            val rate = format.getInteger(android.media.MediaFormat.KEY_SAMPLE_RATE)
            val channels = format.getInteger(android.media.MediaFormat.KEY_CHANNEL_COUNT)
            // Keep the loudest sample of every block, about WAVE_RATE values per second.
            val block = maxOf(1, rate / WAVE_RATE) * channels
            val kept = java.io.ByteArrayOutputStream()
            var loudest = 0
            var inBlock = 0
            codec = android.media.MediaCodec.createDecoderByType(format.getString(android.media.MediaFormat.KEY_MIME)!!)
            codec.configure(format, null, null, 0)
            codec.start()
            val info = android.media.MediaCodec.BufferInfo()
            var inputDone = false
            while (true) {
                if (!inputDone) {
                    val index = codec.dequeueInputBuffer(10_000)
                    if (index >= 0) {
                        val size = extractor.readSampleData(codec.getInputBuffer(index)!!, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(index, 0, 0, 0, android.media.MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val out = codec.dequeueOutputBuffer(info, 10_000)
                if (out >= 0) {
                    val shorts = codec.getOutputBuffer(out)!!.order(java.nio.ByteOrder.LITTLE_ENDIAN).asShortBuffer()
                    while (shorts.hasRemaining()) {
                        loudest = maxOf(loudest, kotlin.math.abs(shorts.get().toInt()))
                        if (++inBlock == block) {
                            val value = minOf(loudest, Short.MAX_VALUE.toInt())
                            kept.write(value and 0xFF); kept.write(value shr 8 and 0xFF)
                            loudest = 0; inBlock = 0
                        }
                    }
                    codec.releaseOutputBuffer(out, false)
                    if (info.flags and android.media.MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                }
            }
            val bytes = kept.toByteArray()
            val samples = ShortArray(bytes.size / 2) { ((bytes[2 * it].toInt() and 0xFF) or (bytes[2 * it + 1].toInt() shl 8)).toShort() }
            return peaks(samples, bars)
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            extractor.release()
        }
    }

    private val MONTHS = listOf("Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez.")
    private val NAME = Regex("^(.*?)\\s*(\\d{4})-(\\d{2})-(\\d{2})[ _](\\d{2})-(\\d{2})\\.\\w+$")

    /** Title and the line below it on the player card, like Apple's: "Aufnahme", "4. Okt. 2026, 14:22 · 0:07".
     *  Same rules as audio.recording_label on Ubuntu. */
    fun label(block: JSONObject): Pair<String, String> {
        val name = block.optString("n")
        val duration = if (block.optDouble("d", 0.0) > 0) durationText(block.optDouble("d")) else ""
        val match = NAME.find(name)
        if (match != null && match.groupValues[3].toInt() in 1..12) {
            val g = match.groupValues
            val title = g[1].trim().ifEmpty { "Aufnahme" }
            val date = "${g[4].toInt()}. ${MONTHS[g[3].toInt() - 1]} ${g[2]}, ${g[5]}:${g[6]}"
            return title to listOf(date, duration).filter { it.isNotEmpty() }.joinToString(" · ")
        }
        val title = if ('.' in name) name.substringBeforeLast('.') else name
        return title.ifEmpty { "Audioaufnahme" } to duration
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

/** Plays one recording at a time inside the note; pause and seek (the message bubble in the note
 *  shows it – RichEditor.showAudio). */
class AudioPlayer {
    var playing by mutableStateOf<String?>(null)  // file id of the loaded recording (playing or paused)
        private set
    var paused by mutableStateOf(false)
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
        paused = false
        playing = fileId
    }

    /** Pause or go on. */
    fun toggle() {
        val current = player ?: return
        if (paused) current.start() else current.pause()
        paused = !paused
        update()
    }

    fun seek(millis: Long) {
        val current = player ?: return
        current.seekTo(millis.coerceIn(0L, maxOf(0L, length - 50)).toInt())
        update()
    }

    fun update() { player?.let { position = it.currentPosition.toLong() } }

    fun stop() {
        player?.release()
        player = null
        playing = null
        paused = false
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
