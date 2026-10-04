package io.github.veritasx1.linotes

import android.content.Intent
import android.os.Bundle
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import io.github.veritasx1.linotes.ui.newNote
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** The server takes 25 MB including encryption (as on Ubuntu). */
const val MAX_ATTACHMENT = 24 * 1024 * 1024

class MainActivity : FragmentActivity() {

    private lateinit var state: AppState
    private var pendingImage: ((ByteArray, String) -> Unit)? = null

    private val picker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        val callback = pendingImage ?: return@registerForActivityResult
        pendingImage = null
        if (uri == null) return@registerForActivityResult
        val mime = contentResolver.getType(uri) ?: "image/jpeg"
        // Read in the background: photos from a cloud gallery can take a while.
        readInBackground({ contentResolver.openInputStream(uri)?.use { it.readBytes() } }) { bytes ->
            if (bytes != null) callback(bytes, mime) else state.toastLater("Das Foto ließ sich nicht lesen.")
        }
    }

    private fun <T> readInBackground(read: () -> T?, done: (T?) -> Unit) {
        lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) { try { read() } catch (error: Exception) { null } }
            done(result)
        }
    }

    // Attachments (like Apple: PDFs and other files): name and size come from the provider.
    private var pendingFile: ((String, String, ByteArray) -> Unit)? = null
    private val filePicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val callback = pendingFile ?: return@registerForActivityResult
        pendingFile = null
        if (uri == null) return@registerForActivityResult
        var name = "Datei"
        var size = -1L
        contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let { name = cursor.getString(it) ?: name }
                cursor.getColumnIndex(android.provider.OpenableColumns.SIZE).takeIf { it >= 0 }?.let { if (!cursor.isNull(it)) size = cursor.getLong(it) }
            }
        }
        if (size > MAX_ATTACHMENT) {
            state.toastLater("„$name“ ist zu groß (höchstens ${MAX_ATTACHMENT / 1024 / 1024} MB).")
            return@registerForActivityResult
        }
        val mime = contentResolver.getType(uri) ?: "application/octet-stream"
        readInBackground({ contentResolver.openInputStream(uri)?.use { it.readBytes() } }) { bytes ->
            if (bytes == null || bytes.size > MAX_ATTACHMENT) {
                state.toastLater(if (bytes == null) "„$name“ ließ sich nicht lesen." else "„$name“ ist zu groß (höchstens ${MAX_ATTACHMENT / 1024 / 1024} MB).")
            } else callback(name, mime, bytes)
        }
    }

    // Photo straight from the camera: the camera app writes into a file we hand it.
    private var pendingPhoto: Pair<java.io.File, (ByteArray, String) -> Unit>? = null
    private val photo = registerForActivityResult(ActivityResultContracts.TakePicture()) { taken ->
        val (file, callback) = pendingPhoto ?: return@registerForActivityResult
        pendingPhoto = null
        if (taken && file.length() > 0) readInBackground({ file.readBytes().also { file.delete() } }) { bytes -> bytes?.let { callback(it, "image/jpeg") } }
        else file.delete()
    }

    private var pendingSave: Pair<ByteArray, (Boolean) -> Unit>? = null
    private var pendingOpen: ((ByteArray?) -> Unit)? = null
    private var pendingCamera: ((Boolean) -> Unit)? = null
    private var pendingMicrophone: ((Boolean) -> Unit)? = null

    private val saver = registerForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        val (content, done) = pendingSave ?: return@registerForActivityResult
        pendingSave = null
        done(uri != null && try {
            contentResolver.openOutputStream(uri, "wt")?.use { it.write(content) } != null
        } catch (error: Exception) {
            false
        })
    }

    private val opener = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val done = pendingOpen ?: return@registerForActivityResult
        pendingOpen = null
        done(uri?.let { try { contentResolver.openInputStream(it)?.use { input -> input.readBytes() } } catch (error: Exception) { null } })
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) io.github.veritasx1.linotes.ui.Mentions.check(this, state)
    }

    private val camera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        pendingCamera?.invoke(granted)
        pendingCamera = null
    }
    private val microphone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        pendingMicrophone?.invoke(granted)
        pendingMicrophone = null
    }

    private fun authenticate(title: String, done: (Boolean) -> Unit) {
        val allowed = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
            BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        else BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        if (BiometricManager.from(this).canAuthenticate(allowed) != BiometricManager.BIOMETRIC_SUCCESS) {
            state.toastLater("Auf diesem Handy ist keine Displaysperre eingerichtet.")
            return done(false)
        }
        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = done(true)
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) = done(false)
        })
        prompt.authenticate(BiometricPrompt.PromptInfo.Builder().setTitle(title)
            .setSubtitle("Fingerabdruck, Gesicht, PIN oder Muster").setAllowedAuthenticators(allowed).build())
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val app = application as LiNotesApplication
        state = app.state
        state.pickImage = { callback ->
            pendingImage = callback
            picker.launch("image/*")
        }
        state.takePhoto = { callback ->
            // The app declares the camera permission (QR codes), so the camera app needs it granted too.
            state.requestCamera { granted ->
                if (!granted) state.toastLater("Ohne Kamera-Erlaubnis kein Foto.")
                else {
                    val file = java.io.File(java.io.File(cacheDir, "photos").apply { mkdirs() }, "foto-${System.currentTimeMillis()}.jpg")
                    pendingPhoto = file to callback
                    photo.launch(androidx.core.content.FileProvider.getUriForFile(this, "$packageName.files", file))
                }
            }
        }
        state.pickFile = { callback ->
            pendingFile = callback
            filePicker.launch(arrayOf("*/*"))
        }
        state.openFile = { file, mime ->
            val uri = androidx.core.content.FileProvider.getUriForFile(this, "$packageName.files", file)
            val intent = android.content.Intent(android.content.Intent.ACTION_VIEW).setDataAndType(uri, mime)
                .addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
            try {
                startActivity(android.content.Intent.createChooser(intent, file.name))
            } catch (error: android.content.ActivityNotFoundException) {
                state.toastLater("Keine App zum Öffnen von „${file.name}“.")
            }
        }
        state.authenticate = { title, done -> authenticate(title, done) }
        state.saveDocument = { name, content, done ->
            pendingSave = content to done
            saver.launch(name)
        }
        state.openDocument = { done ->
            pendingOpen = done
            opener.launch(arrayOf("*/*"))
        }
        state.shareFile = { file, mime, title ->
            val uri = androidx.core.content.FileProvider.getUriForFile(this, "$packageName.files", file)
            val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri)
                .putExtra(Intent.EXTRA_SUBJECT, title).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            startActivity(Intent.createChooser(send, title))
        }
        state.requestCamera = { done ->
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) done(true)
            else {
                pendingCamera = done
                camera.launch(Manifest.permission.CAMERA)
            }
        }
        state.requestMicrophone = { done ->
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) done(true)
            else {
                pendingMicrophone = done
                microphone.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                state.checkAutoLock()
                if (state.signedIn) {
                    state.sync.launch {
                        try { state.sync.syncNow() } catch (error: Exception) { }
                        withContext(Dispatchers.Main) { state.ensureDefaults() }
                        state.sync.evict()
                    }
                    state.sync.start()
                }
            }

            override fun onStop(owner: LifecycleOwner) {
                // Like Apple: leaving the app or switching the screen off locks the notes
                // (the open locked note is saved first, then pushed below).
                state.lockAll()
                state.sync.launch { try { state.sync.pushOnce() } catch (error: Exception) { } }
                state.sync.stop()
            }
        })
        handleShare(intent)
        handleNewNote(intent)
        handleOpenNote(intent)
        setContent { LiNotesApp(state) }
        // @-mentions arrive as notifications (Android 13+ asks once, only if something is shared).
        if (Build.VERSION.SDK_INT >= 33 && state.signedIn &&
            ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED &&
            state.sync.all("note").any { it.share != null }) {
            notificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
        handleNewNote(intent)
        handleOpenNote(intent)
    }

    /** A tapped notification (e.g. an @-mention) opens its note. */
    private fun handleOpenNote(intent: Intent?) {
        if (intent?.action != ACTION_OPEN_NOTE || !state.signedIn) return
        val noteId = intent.getStringExtra(EXTRA_NOTE) ?: return
        intent.action = null
        if (state.sync.get(noteId) == null) return
        state.tab = 0
        state.push(io.github.veritasx1.linotes.ui.Route.Editor(noteId))
    }

    /** Quick note from the tile in the quick settings or the app shortcut. */
    private fun handleNewNote(intent: Intent?) {
        if (intent?.action != ACTION_NEW_NOTE || !state.signedIn) return
        state.tab = 0
        newNote(state, null)
        intent.action = null
    }

    companion object {
        const val ACTION_NEW_NOTE = "io.github.veritasx1.linotes.NEW_NOTE"
        const val ACTION_OPEN_NOTE = "io.github.veritasx1.linotes.OPEN_NOTE"
        const val EXTRA_NOTE = "note"
    }

    /** Text shared from another app becomes a new note. */
    private fun handleShare(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND || !state.signedIn) return
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
        val subject = intent.getStringExtra(Intent.EXTRA_SUBJECT)
        val lines = text.lines()
        val body = JSONArray()
        body.put(JSONObject().put("t", "title").put("x", subject ?: lines.first()))
        (if (subject != null) lines else lines.drop(1)).forEach { body.put(JSONObject().put("t", "body").put("x", it)) }
        val sync = state.sync
        val now = Model.now()
        val note = sync.put("note", JSONObject().put("folder", Model.privateFolder(sync.userId)).put("body", body)
            .put("created", now).put("modified", now))
        state.tab = 0
        state.push(Route.Editor(note.id))
        intent.action = null
    }
}
