package io.github.veritasx1.linotes

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : ComponentActivity() {

    private lateinit var state: AppState
    private var pendingImage: ((ByteArray, String) -> Unit)? = null

    private val picker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        val callback = pendingImage ?: return@registerForActivityResult
        pendingImage = null
        if (uri == null) return@registerForActivityResult
        val mime = contentResolver.getType(uri) ?: "image/jpeg"
        val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@registerForActivityResult
        callback(bytes, mime)
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
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                state.checkAutoLock()
                if (state.signedIn) {
                    state.sync.launch {
                        state.sync.syncNow()
                        withContext(Dispatchers.Main) { state.ensureDefaults() }
                    }
                    state.sync.start()
                }
            }

            override fun onStop(owner: LifecycleOwner) {
                state.sync.launch { try { state.sync.pushOnce() } catch (error: Exception) { } }
                state.sync.stop()
            }
        })
        handleShare(intent)
        setContent { LiNotesApp(state) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
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
            .put("created", now).put("modified", now), "private")
        state.tab = 0
        state.push(Route.Editor(note.id))
        intent.action = null
    }
}
