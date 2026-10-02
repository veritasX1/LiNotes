package io.github.veritasx1.linotes.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.github.veritasx1.linotes.data.BiometricStore
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.Vault
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject

sealed class Route {
    data object Folders : Route()
    data class NoteList(val key: String) : Route()
    data class Editor(val noteId: String) : Route()
    data object Lists : Route()
    data class ListDetail(val listId: String) : Route()
    data object Boards : Route()
    data class Board(val boardId: String) : Route()
    data object Plans : Route()
    data class Plan(val planId: String) : Route()
    data object Settings : Route()
    data object People : Route()
    data class Verify(val userId: Int) : Route()
    data class Share(val objectId: String) : Route()
    data object Help : Route()
    data object Connect : Route()
}

/** Everything the screens share: sync, navigation per tab, the vault key, toasts. */
class AppState(val sync: SyncEngine, val biometric: BiometricStore? = null) {
    var signedIn by mutableStateOf(sync.restore())
    var tab by mutableIntStateOf(0)
    /** Notes made on this device in this run: dropped when left empty (like Apple). */
    val freshNotes = mutableSetOf<String>()
    val stacks = listOf(
        mutableStateListOf<Route>(Route.Folders),
        mutableStateListOf<Route>(Route.Lists),
        mutableStateListOf<Route>(Route.Boards),
        mutableStateListOf<Route>(Route.Plans),
    )
    var toast by mutableStateOf<String?>(null)
    /** Observed: when it goes away, open locked notes redraw as locked. */
    var vaultKey by mutableStateOf<ByteArray?>(null)
        private set

    /** Saves the open locked note before the key goes away (set by the editor). */
    var flushLocked: (() -> Unit)? = null
    private var vaultUsed = 0L
    var pickImage: ((ByteArray, String) -> Unit) -> Unit = {}
    var takePhoto: ((ByteArray, String) -> Unit) -> Unit = {}
    /** Any file to attach: (name, mime, content), or a message if it is too big. */
    var pickFile: ((String, String, ByteArray) -> Unit) -> Unit = {}
    /** Open a decrypted attachment with the app that handles its type. */
    var openFile: (file: java.io.File, mime: String) -> Unit = { _, _ -> }

    // Platform hooks, filled in by MainActivity.
    var authenticate: (title: String, done: (Boolean) -> Unit) -> Unit = { _, done -> done(false) }
    var saveDocument: (name: String, content: ByteArray, done: (Boolean) -> Unit) -> Unit = { _, _, done -> done(false) }
    var openDocument: (done: (ByteArray?) -> Unit) -> Unit = { it(null) }
    var requestCamera: (done: (Boolean) -> Unit) -> Unit = { it(false) }
    var requestMicrophone: (done: (Boolean) -> Unit) -> Unit = { it(false) }
    var shareFile: (file: java.io.File, mime: String, title: String) -> Unit = { _, _, _ -> }

    /** Offer to save the key file (right after creating an account). */

    /** Incoming link and verification requests (shown as dialogs). */
    val incoming = mutableStateListOf<JSONObject>()

    /** Set while the QR scanner is open; receives the scanned text. */
    var scanner by mutableStateOf<((String) -> Unit)?>(null)

    fun scanQr(onResult: (String) -> Unit) {
        requestCamera { granted ->
            if (granted) scanner = onResult else toastLater("Ohne Kamerazugriff kann kein QR-Code gescannt werden.")
        }
    }

    val stack get() = stacks[tab]
    val route: Route get() = stack.last()

    fun push(route: Route) {
        stack.add(route)
    }

    fun pop(): Boolean {
        if (stack.size <= 1) return false
        stack.removeAt(stack.lastIndex)
        return true
    }

    fun openTab(index: Int) {
        // Tapping the active tab again returns to its first screen, like on iOS.
        if (index == tab) while (stacks[index].size > 1) stacks[index].removeAt(stacks[index].lastIndex)
        tab = index
    }

    suspend fun showToast(text: String) {
        toast = text
        try {
            delay(2600)
        } finally {
            // Also when the screen that showed it goes away meanwhile.
            if (toast == text) toast = null
        }
    }

    fun toastLater(text: String) {
        sync.launch { withContext(Dispatchers.Main) { showToast(text) } }
    }

    // --- locked notes ------------------------------------------

    fun vaultObject() = sync.get("vault-${sync.userId}")

    fun hasVault() = vaultObject() != null

    fun touchVault() {
        if (vaultKey != null) vaultUsed = System.currentTimeMillis()
    }

    fun checkAutoLock() {
        // Like Apple: an unlocked note stays open for a few minutes of inactivity.
        if (vaultKey != null && System.currentTimeMillis() - vaultUsed > 5 * 60 * 1000) lockAll()
    }

    fun lockAll() {
        if (vaultKey != null) flushLocked?.invoke()
        vaultKey = null
    }

    val biometricEnabled: Boolean get() = biometric?.enabled == true

    /** Keep the vault key behind fingerprint / PIN / pattern (needs the vault unlocked). */
    fun enableBiometric(done: (Boolean) -> Unit) {
        val key = vaultKey ?: return done(false)
        val store = biometric ?: return done(false)
        authenticate("Entsperren mit Fingerabdruck, PIN oder Muster einschalten") { ok ->
            val stored = ok && try { store.store(key, vaultObject()?.id.orEmpty()); true } catch (error: Exception) { false }
            done(stored)
        }
    }

    fun disableBiometric() {
        biometric?.clear()
    }

    fun unlockWithBiometric(done: (Boolean) -> Unit) {
        val store = biometric?.takeIf { it.enabled } ?: return done(false)
        authenticate("Gesperrte Notizen öffnen") { ok ->
            if (!ok) return@authenticate done(false)
            val key = try { store.load() } catch (error: Exception) { null }
            val vault = vaultObject()
            if (key == null || vault == null || !Vault.checkKey(vault.data, key)) {
                // The notes password changed or the phone's lock was reset.
                store.clear()
                toastLater("Bitte einmal das Notizen-Passwort eingeben.")
                return@authenticate done(false)
            }
            vaultKey = key
            touchVault()
            done(true)
        }
    }

    fun createVault(password: String, hint: String) {
        val (data, key) = Vault.create(password, hint)
        sync.put("vault", data, null, "vault-${sync.userId}")
        vaultKey = key
        touchVault()
    }

    /** Throws Vault.WrongPassword. Slow (key derivation): call off the main thread. */
    fun unlock(password: String) {
        val vault = vaultObject() ?: throw Vault.WrongPassword()
        vaultKey = Vault.unlock(vault.data, password)
        touchVault()
    }

    fun changeVaultPassword(old: String, new: String, hint: String): Int {
        val vault = vaultObject() ?: return 0
        val oldKey = Vault.unlock(vault.data, old)
        val (data, newKey) = Vault.create(new, hint)
        var count = 0
        for (note in sync.all("note")) {
            if (note.owner != sync.userId || !note.data.has("enc")) continue
            val body = Vault.openBody(oldKey, note.data.getJSONObject("enc"))
            val updated = JSONObject(note.data.toString()).put("enc", Vault.sealBody(newKey, body))
            sync.put("note", updated, note.share, note.id)
            count++
        }
        sync.put("vault", data, null, vault.id)
        disableBiometric()
        vaultKey = newKey
        touchVault()
        return count
    }

    fun ensureDefaults() = Model.ensureDefaults(sync)
}
