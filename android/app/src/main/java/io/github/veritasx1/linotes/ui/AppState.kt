package io.github.veritasx1.linotes.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
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
    data object Settings : Route()
}

/** Everything the screens share: sync, navigation per tab, the vault key, toasts. */
class AppState(val sync: SyncEngine) {
    var signedIn by mutableStateOf(sync.restore())
    var tab by mutableIntStateOf(0)
    val stacks = listOf(
        mutableStateListOf<Route>(Route.Folders),
        mutableStateListOf<Route>(Route.Lists),
        mutableStateListOf<Route>(Route.Boards),
    )
    var toast by mutableStateOf<String?>(null)
    var vaultKey: ByteArray? = null
        private set
    private var vaultUsed = 0L
    var pickImage: ((ByteArray, String) -> Unit) -> Unit = {}

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
        delay(2600)
        if (toast == text) toast = null
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
        if (vaultKey != null && System.currentTimeMillis() - vaultUsed > 10 * 60 * 1000) vaultKey = null
    }

    fun lockAll() {
        vaultKey = null
    }

    fun createVault(password: String, hint: String) {
        val (data, key) = Vault.create(password, hint)
        sync.put("vault", data, "private", "vault-${sync.userId}")
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
            sync.put("note", updated, note.space, note.id)
            count++
        }
        sync.put("vault", data, "private", vault.id)
        vaultKey = newKey
        touchVault()
        return count
    }

    fun ensureDefaults() = Model.ensureDefaults(sync)
}
