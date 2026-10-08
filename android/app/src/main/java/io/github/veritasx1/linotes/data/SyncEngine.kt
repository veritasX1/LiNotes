package io.github.veritasx1.linotes.data

import io.github.veritasx1.linotes.i18n.tr

import android.content.Context
import android.os.Build
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/** A decrypted object as the screens see it. */
class SyncObject(
    val id: String,
    val kind: String,
    val share: String?,
    val owner: Int,
    val data: JSONObject,
    val deleted: Boolean,
    val version: Long,
    val updated: Double,
    val updatedBy: Int,
) {
    /** "shared" if the object belongs to a share, else "private". */
    val space: String get() = if (share != null) "shared" else "private"
    val evicted: Boolean get() = data.optBoolean("evicted")

    fun withVersion(newVersion: Long) = SyncObject(id, kind, share, owner, data, deleted, newVersion, updated, updatedBy)
}

data class User(val id: Int, val username: String, val name: String, val identity: String)

/** How long a note's content stays on this phone (see docs/SECURITY.md). */
object Keep {
    const val ALWAYS = "always"
    const val SERVER = "server"
    val choices = listOf(ALWAYS to tr("Immer"), "90" to tr("90 Tage"), "30" to tr("30 Tage"), "7" to tr("7 Tage"), SERVER to tr("Nur auf dem Server"))
    const val DEFAULT = "90"
    fun label(value: String) = choices.firstOrNull { it.first == value }?.second ?: tr("90 Tage")
}

/**
 * Offline-first, end-to-end encrypted sync (protocol v2), the Android twin
 * of linux/linotes/sync.py. The server copy of every object (encrypted) is
 * kept in state.json; decrypted objects live only in memory. Local edits
 * are encrypted when queued. Shares carry the keys that let others read.
 */
/** Same steps as linux/linotes/textsize.py. */
val TEXT_SIZES = listOf(0.85f to tr("Klein"), 1.0f to tr("Normal"), 1.15f to tr("Groß"), 1.3f to tr("Sehr groß"), 1.5f to tr("Riesig"))

class SyncEngine(private val context: Context) {
    companion object {
        /** User id while LiNotes is used without a server. */
        const val LOCAL_USER = -1
    }

    private val file = File(context.filesDir, "state-v2.json")
    private val filesDir = File(context.cacheDir, "files").apply { mkdirs() }
    private val credentials = TokenStore(context)
    private val openedPrefs = context.getSharedPreferences("opened", Context.MODE_PRIVATE)
    private val uiPrefs = context.getSharedPreferences("ui", Context.MODE_PRIVATE)

    /** When the shopping lists were last looked at (for the badge on the tab). */
    var listsSeen: Double
        get() = uiPrefs.getLong("lists-seen", 0) / 1000.0
        set(value) = uiPrefs.edit().putLong("lists-seen", (value * 1000).toLong()).apply()

    /** Text size of notes (index into [TEXT_SIZES]), per device like on Ubuntu. Adds to the
     *  font size of the system (Android settings). */
    var textSize: Int
        get() = uiPrefs.getInt("text-size", 1).coerceIn(0, TEXT_SIZES.lastIndex)
        set(value) = uiPrefs.edit().putInt("text-size", value.coerceIn(0, TEXT_SIZES.lastIndex)).apply()

    /** How many @-mentions of me each shared note had when last looked at (notify only new ones). */
    var mentionsSeen: org.json.JSONObject
        get() = try { org.json.JSONObject(uiPrefs.getString("mentions-seen", "{}") ?: "{}") } catch (error: Exception) { org.json.JSONObject() }
        set(value) = uiPrefs.edit().putString("mentions-seen", value.toString()).apply()

    /** Justified text and hyphenation in notes – a choice per device like the text size. */
    var justify: Boolean
        get() = uiPrefs.getBoolean("justify", false)
        set(value) = uiPrefs.edit().putBoolean("justify", value).apply()
    var hyphenate: Boolean
        get() = uiPrefs.getBoolean("hyphenate", false)
        set(value) = uiPrefs.edit().putBoolean("hyphenate", value).apply()
    /** Link previews fetch the page, the site then sees this phone's address – off unless switched on. */
    var linkPreviews: Boolean
        get() = uiPrefs.getBoolean("link_previews", false)
        set(value) = uiPrefs.edit().putBoolean("link_previews", value).apply()

    /** Notes as a gallery (like Apple's "View as Gallery") – a choice per device, as on Ubuntu. */
    var noteGallery: Boolean
        get() = uiPrefs.getBoolean("note-gallery", false)
        set(value) = uiPrefs.edit().putBoolean("note-gallery", value).apply()

    /** Open entries someone else added or changed since the lists were last looked at. */
    fun newListItems(): Int {
        val seen = listsSeen
        return all("item").count { !it.data.optBoolean("done") && it.updatedBy != 0 && it.updatedBy != userId && it.updated > seen }
    }
    private val lock = Any()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var jobs: List<Job> = emptyList()
    private val wake = Channel<Unit>(Channel.CONFLATED)

    var server = ""
        private set
    var user: User? = null
        private set
    var users: List<User> = emptyList()
        private set
    private var cursor = 0L
    private val remote = LinkedHashMap<String, JSONObject>()
    private val pending = ArrayList<JSONObject>()
    private var identitySealed: JSONObject? = null

    private val plain = LinkedHashMap<String, SyncObject>()
    private val shareKeys = HashMap<String, ByteArray>()
    var account: E2E.Account? = null
        private set
    var identity: E2E.Identity? = null
        private set
    var api: Api? = null
        private set
    var openNote: String? = null
    private val seenChannels = HashSet<String>()

    val revision = MutableStateFlow(0L)
    val online = MutableStateFlow(false)
    val signedOut = MutableStateFlow(false)
    val requests = MutableSharedFlow<JSONObject>(extraBufferCapacity = 8)

    init {
        load()
    }

    // ================================================================
    // PERSISTENCE
    // ================================================================

    private fun load() {
        try {
            val json = JSONObject(file.readText())
            server = json.optString("server")
            user = json.optJSONObject("user")?.let { userFrom(it) }
            users = json.optJSONArray("users")?.let { a -> (0 until a.length()).map { userFrom(a.getJSONObject(it)) } } ?: emptyList()
            cursor = json.optLong("cursor")
            identitySealed = json.optJSONObject("identity")
            json.optJSONObject("remote")?.let { map -> map.keys().forEach { remote[it] = map.getJSONObject(it) } }
            json.optJSONArray("pending")?.let { a -> for (i in 0 until a.length()) pending.add(a.getJSONObject(i)) }
        } catch (error: Exception) {
            // First start.
        }
    }

    private fun save() {
        val text = synchronized(lock) {
            JSONObject()
                .put("server", server)
                .put("user", user?.let { userJson(it) })
                .put("users", JSONArray(users.map { userJson(it) }))
                .put("cursor", cursor)
                .put("identity", identitySealed)
                .put("remote", JSONObject().also { map -> remote.forEach { (k, v) -> map.put(k, v) } })
                .put("pending", JSONArray(pending))
                .toString()
        }
        synchronized(file) {
            val temp = File(file.parentFile, "state-v2.tmp")
            temp.writeText(text)
            temp.renameTo(file)
        }
    }

    private var saveJob: Job? = null
    private fun persistSoon() {
        saveJob?.cancel()
        saveJob = scope.launch { delay(400); save() }
    }

    private fun userFrom(json: JSONObject) = User(json.optInt("id"), json.optString("username"), json.optString("name"), json.optString("identity"))
    private fun userJson(user: User) = JSONObject().put("id", user.id).put("username", user.username).put("name", user.name).put("identity", user.identity)

    // ================================================================
    // ACCOUNT
    // ================================================================

    val deviceName: String get() = tr("Android ({MANUFACTURER} {MODEL})", "MANUFACTURER" to Build.MANUFACTURER, "MODEL" to Build.MODEL)
    val userId: Int get() = user?.id ?: 0

    fun restore(): Boolean {
        val current = user ?: return false
        val saved = credentials.load() ?: return false
        return try {
            val json = JSONObject(saved)
            api = if (server.isEmpty()) null else Api(server, json.getString("token"))
            account = E2E.Account(E2E.unb64(json.getString("secret")))
            identitySealed?.let { identity = E2E.Identity.fromSealed(account!!, it) }
            rebuild()
            current.id != 0
        } catch (error: Exception) {
            false
        }
    }

    fun signIn(serverUrl: String, response: JSONObject, newAccount: E2E.Account) {
        val newUser = userFrom(response.getJSONObject("user"))
        synchronized(lock) {
            if (serverUrl.trimEnd('/') != server || (user != null && user?.id != newUser.id)) {
                remote.clear(); pending.clear(); cursor = 0
            }
            server = serverUrl.trimEnd('/')
            user = newUser
            response.optJSONArray("users")?.let { a -> users = (0 until a.length()).map { userFrom(a.getJSONObject(it)) } }
            identitySealed = response.getJSONObject("identity")
        }
        val token = response.getString("token")
        credentials.save(JSONObject().put("token", token).put("secret", E2E.b64(newAccount.secret)).toString())
        api = Api(server, token)
        account = newAccount
        identity = E2E.Identity.fromSealed(newAccount, identitySealed!!)
        signedOut.value = false
        rebuild()
        save()
        bump()
    }

    // ================================================================
    // WITHOUT A SERVER (everything stays on this device)
    // ================================================================

    /** True while LiNotes is used without a server. */
    val isLocal: Boolean get() = user != null && server.isEmpty()

    private val localFiles = File(context.filesDir, "local-files")

    fun startLocal(name: String) {
        val newAccount = E2E.Account.create()
        val newIdentity = E2E.Identity.create()
        val me = User(LOCAL_USER, "", name.ifBlank { tr("Ich") }, newIdentity.public)
        synchronized(lock) {
            remote.clear(); pending.clear(); cursor = 0
            server = ""
            user = me
            users = listOf(me)
            identitySealed = newIdentity.exportSealed(newAccount)
        }
        credentials.save(JSONObject().put("token", "").put("secret", E2E.b64(newAccount.secret)).toString())
        api = null
        account = newAccount
        identity = newIdentity
        signedOut.value = false
        rebuild()
        save()
        bump()
    }

    class VaultConflict : Exception("vault conflict")

    /**
     * Move everything made without a server into a server account (a new one,
     * or an existing one reached by linking or with the key file). Blocking.
     * Throws VaultConflict (before changing anything) if both have a notes password.
     */
    fun connectLocal(serverUrl: String, response: JSONObject, newAccount: E2E.Account) {
        val oldAccount = account ?: throw IllegalStateException("not local")
        val uid = response.getJSONObject("user").getInt("id")
        val temp = Api(serverUrl.trimEnd('/'), response.getString("token"))
        val local = synchronized(lock) { plain.values.filter { !it.deleted }.toList() }
        val hasLocalVault = local.any { it.kind == "vault" } && local.any { it.kind == "note" && it.data.has("enc") }
        val onServer = { id: String -> try { temp.getObject(id); true } catch (error: ApiException) { false } }
        if (hasLocalVault && onServer("vault-$uid")) throw VaultConflict()
        // Pictures: re-encrypt with the account key and upload.
        val mapping = HashMap<String, String>()
        localFiles.listFiles()?.forEach { file ->
            val content = E2E.openBytes(oldAccount.privateKey, file.readBytes(), file.name)
            val fileId = temp.upload(E2E.sealBytes(newAccount.privateKey, content, file.name), null)
            mapping["local:${file.name}"] = "$fileId:${file.name}"
        }
        for (obj in local) mapping[obj.id] = remapId(obj.id, uid)
        signIn(serverUrl, response, newAccount)
        try { pullOnce() } catch (error: Exception) { }
        val containers = setOf("folder", "list", "board", "column", "settings", "contacts", "vault")
        for (obj in local) {
            val newId = mapping.getValue(obj.id)
            // An existing account keeps its own default folder, list and board.
            if (newId != obj.id && obj.kind in containers && exists(newId)) continue
            put(obj.kind, remapData(obj.data, mapping, uid) as JSONObject, null, newId)
        }
        localFiles.deleteRecursively()
        save()
    }

    private fun remapId(id: String, uid: Int): String {
        val match = Regex("^(notes|list|board|vault|settings|contacts)-${LOCAL_USER}(-.*)?$").matchEntire(id) ?: return id
        return "${match.groupValues[1]}-$uid${match.groupValues[2]}"
    }

    private fun remapData(value: Any?, mapping: Map<String, String>, uid: Int): Any? = when (value) {
        is JSONObject -> JSONObject().also { copy ->
            value.keys().forEach { key ->
                val item = value.get(key)
                copy.put(key, if (key in setOf("by", "created_by", "assignee") && item == LOCAL_USER) uid else remapData(item, mapping, uid))
            }
        }
        is JSONArray -> JSONArray().also { copy -> for (index in 0 until value.length()) copy.put(remapData(value.get(index), mapping, uid)) }
        is String -> mapping[value] ?: value
        else -> value
    }

    fun signOut() {
        stop()
        val oldApi = api
        scope.launch { try { oldApi?.logout() } catch (error: Exception) { } }
        credentials.clear()
        synchronized(lock) {
            user = null; users = emptyList(); remote.clear(); pending.clear(); cursor = 0
            identitySealed = null; plain.clear(); shareKeys.clear()
        }
        api = null; account = null; identity = null
        localFiles.deleteRecursively()
        save()
        bump()
    }

    fun userName(id: Int): String = users.firstOrNull { it.id == id }?.name ?: "?"
    fun userById(id: Int): User? = users.firstOrNull { it.id == id }

    // ================================================================
    // ENCRYPTION
    // ================================================================

    fun keyFor(share: String?): ByteArray? = if (share == null) account?.privateKey else shareKeys[share]

    private fun encrypt(obj: SyncObject): JSONObject {
        val id = obj.id
        val data = obj.data
        if (obj.kind == "share") {
            val meta = JSONObject(data.toString()).apply { remove("keys") }
            return JSONObject().put("v", 2).put("keys", data.optJSONObject("keys") ?: JSONObject())
                .put("m", E2E.seal(shareKeys.getValue(id), meta, "$id|m"))
        }
        val key = keyFor(obj.share) ?: throw E2E.CryptoError("no key")
        if (obj.kind == "note") {
            val body = JSONObject()
            val meta = JSONObject(data.toString())
            for (field in listOf("body", "enc")) if (meta.has(field)) { body.put(field, meta.get(field)); meta.remove(field) }
            meta.remove("evicted")
            // Title and first line stay readable (for us) when only the metadata is kept on the phone.
            // Locked notes keep their title visible (like Apple's Notes) – still end-to-end
            // encrypted like all metadata; the preview would leak content.
            if (!data.has("enc")) meta.remove("title")
            meta.remove("preview")
            data.optJSONArray("body")?.let { blocks ->
                val lines = (0 until blocks.length()).mapNotNull { blocks.optJSONObject(it)?.optString("x")?.trim() }.filter { it.isNotEmpty() }
                meta.put("title", lines.firstOrNull()?.take(120) ?: "").put("preview", lines.drop(1).joinToString(" ").take(160))
            }
            return JSONObject().put("v", 2).put("m", E2E.seal(key, meta, "$id|m")).put("b", E2E.seal(key, body, "$id|b"))
        }
        return JSONObject().put("v", 2).put("m", E2E.seal(key, data, "$id|m"))
    }

    private fun decrypt(item: JSONObject): SyncObject? {
        val id = item.getString("id")
        val kind = item.getString("kind")
        val share = item.optString("share").takeIf { it.isNotEmpty() && it != "null" }
        val deleted = item.optBoolean("deleted")
        fun make(data: JSONObject) = SyncObject(id, kind, share, item.optInt("owner"), data, deleted,
            item.optLong("version"), item.optDouble("updated", 0.0), item.optInt("updated_by"))
        if (deleted) return make(JSONObject())
        val data = item.optJSONObject("data") ?: return null
        return try {
            if (kind == "share") {
                val wrapped = data.optJSONObject("keys")?.optJSONObject(userId.toString()) ?: return null
                val key = E2E.unwrapKey(identity!!, wrapped, id)
                shareKeys[id] = key
                val result = if (data.has("m")) E2E.open(key, data.getJSONObject("m"), "$id|m") else JSONObject()
                result.put("keys", data.optJSONObject("keys"))
                return make(result)
            }
            val key = keyFor(share) ?: return null
            val result = E2E.open(key, data.getJSONObject("m"), "$id|m")
            if (data.has("b")) {
                val body = E2E.open(key, data.getJSONObject("b"), "$id|b")
                body.keys().forEach { result.put(it, body.get(it)) }
            } else if (kind == "note") {
                result.put("evicted", true)
            }
            make(result)
        } catch (error: Exception) {
            null
        }
    }

    private fun pendingAsRemote(change: JSONObject): JSONObject {
        val existing = remote[change.getString("id")]
        return JSONObject()
            .put("id", change.getString("id")).put("kind", change.getString("kind"))
            .put("share", change.opt("share") ?: JSONObject.NULL)
            .put("owner", existing?.optInt("owner") ?: userId)
            .put("data", change.optJSONObject("data") ?: JSONObject())
            .put("deleted", change.optBoolean("deleted"))
            .put("version", change.optLong("base"))
            .put("updated", change.optDouble("updated", Model.now()))
            .put("updated_by", userId)
    }

    private fun rebuild() {
        synchronized(lock) {
            plain.clear()
            shareKeys.clear()
            if (account == null || identity == null) return
            for (item in remote.values.sortedBy { it.optString("kind") != "share" }) {
                decrypt(item)?.let { plain[it.id] = it }
            }
            for (change in pending.sortedBy { it.optString("kind") != "share" }) {
                decrypt(pendingAsRemote(change))?.let { plain[it.id] = it }
            }
        }
    }

    // ================================================================
    // LOCAL OBJECTS
    // ================================================================

    fun all(kind: String): List<SyncObject> = synchronized(lock) { plain.values.filter { it.kind == kind && !it.deleted } }

    fun get(id: String): SyncObject? = synchronized(lock) { plain[id]?.takeIf { !it.deleted } }

    fun exists(id: String): Boolean = synchronized(lock) { plain.containsKey(id) || remote.containsKey(id) }

    fun put(kind: String, data: JSONObject, share: String? = null, id: String? = null, members: List<Int>? = null): SyncObject {
        val objectId = id ?: UUID.randomUUID().toString().replace("-", "")
        val obj = synchronized(lock) {
            val existing = plain[objectId]
            val clean = JSONObject(data.toString()).apply { remove("evicted") }
            val created = SyncObject(objectId, kind, share, existing?.owner ?: userId, clean, false,
                existing?.version ?: 0, Model.now(), userId)
            plain[objectId] = created
            queue(created, members)
            created
        }
        persistSoon()
        bump()
        return obj
    }

    fun update(id: String, change: (JSONObject) -> Unit): SyncObject? {
        val obj = get(id) ?: return null
        if (obj.evicted) return null
        val data = JSONObject(obj.data.toString())
        change(data)
        return put(obj.kind, data, obj.share, obj.id)
    }

    fun delete(id: String) {
        synchronized(lock) {
            val obj = plain[id] ?: return
            val gone = SyncObject(obj.id, obj.kind, obj.share, obj.owner, JSONObject(), true, obj.version, Model.now(), userId)
            plain[id] = gone
            queue(gone, null)
        }
        persistSoon()
        bump()
    }

    private fun queue(obj: SyncObject, members: List<Int>?) {
        val change = JSONObject()
            .put("id", obj.id).put("kind", obj.kind).put("share", obj.share ?: JSONObject.NULL)
            .put("data", if (obj.deleted) JSONObject() else encrypt(obj))
            .put("deleted", obj.deleted).put("base", obj.version).put("updated", obj.updated)
        if (obj.kind == "share") {
            val list = members ?: obj.data.optJSONObject("keys")?.keys()?.asSequence()?.map { it.toInt() }?.filter { it != userId }?.toList() ?: emptyList()
            change.put("members", JSONArray(list))
        }
        val index = pending.indexOfFirst { it.getString("id") == obj.id }
        if (index >= 0) {
            change.put("base", pending[index].optLong("base"))
            // Move to the end: a new share must reach the server before the objects moved into it.
            pending.removeAt(index)
        }
        pending.add(change)
        wake.trySend(Unit)
    }

    private fun bump() {
        revision.value = revision.value + 1
    }

    // ================================================================
    // SHARES
    // ================================================================

    /** Objects that move together with `obj` into or out of a share. A folder takes everything
     *  inside along (like Apple's shared folders): subfolders, their notes, lists with items,
     *  boards with columns and cards – same as container_members in linux/linotes/sync.py. */
    private fun containerMembers(obj: SyncObject): List<SyncObject> = listOf(obj) + when (obj.kind) {
        "folder" -> {
            val folders = all("folder")
            val tree = mutableSetOf(obj.id)
            val subfolders = mutableListOf<SyncObject>()
            val todo = ArrayDeque(listOf(obj.id))
            while (todo.isNotEmpty()) {
                val parent = todo.removeFirst()
                for (folder in folders) if (folder.data.optString("parent") == parent && tree.add(folder.id)) { subfolders.add(folder); todo.add(folder.id) }
            }
            subfolders + all("note").filter { it.data.optString("folder") in tree } +
                (all("list") + all("board") + all("plan")).filter { it.data.optString("folder") in tree }.flatMap { containerMembers(it) }
        }
        "list" -> all("item").filter { it.data.optString("list") == obj.id }
        "board" -> (all("column") + all("card")).filter { it.data.optString("board") == obj.id }
        else -> emptyList()
    }

    /** Move a folder ("parent") or list/board ("folder") into a folder (null = top / none). Into a
     *  shared folder it takes on that share with everything inside (re-encrypted); out of it, it
     *  becomes private again – unless it was shared on its own. Blocking (pictures are re-uploaded). */
    fun shareAfterMove(obj: SyncObject, folderId: String?): String? {
        val field = if (obj.kind == "folder") "parent" else "folder"
        val target = folderId?.let { get(it) }
        val oldPlace = obj.data.optString(field).takeIf { it.isNotEmpty() && it != "null" }?.let { get(it) }
        return when {
            target?.share != null -> target.share
            obj.share != null && oldPlace?.share == obj.share -> null  // it was shared through its old folder
            else -> obj.share
        }
    }

    fun moveToFolder(objectId: String, folderId: String?) {
        val obj = get(objectId) ?: return
        val field = if (obj.kind == "folder") "parent" else "folder"
        val share = shareAfterMove(obj, folderId)
        if (share == obj.share) {
            update(objectId) { if (folderId != null) it.put(field, folderId) else it.remove(field) }
            return
        }
        for (item in containerMembers(obj)) {
            val full = if (item.evicted) fetchNote(item.id) ?: item else item
            val data = rekeyFiles(full, share)
            if (full.id == objectId) { if (folderId != null) data.put(field, folderId) else data.remove(field) }
            put(full.kind, data, share, full.id)
        }
    }

    fun shareMembers(shareId: String?): List<Int> {
        val share = shareId?.let { get(it) } ?: return emptyList()
        return share.data.optJSONObject("keys")?.keys()?.asSequence()?.map { it.toInt() }?.sorted()?.toList() ?: emptyList()
    }

    /** Share `objectId` with exactly `memberIds`; empty = private again. Blocking (network for pictures). */
    fun setSharing(objectId: String, memberIds: List<Int>): String? {
        val obj = get(objectId) ?: return null
        val members = memberIds.toSet().minus(userId).sorted()
        val current = obj.share
        if (current != null && members.toSet() == shareMembers(current).toSet().minus(userId)) return current
        var newShare: String? = null
        if (members.isNotEmpty()) {
            newShare = "share-" + UUID.randomUUID().toString().replace("-", "")
            val key = E2E.newKey()
            shareKeys[newShare] = key
            val keys = JSONObject()
            for (uid in listOf(userId) + members) {
                val target = userById(uid) ?: throw IllegalStateException(tr("Unbekannter Account"))
                keys.put(uid.toString(), E2E.wrapKey(key, target.identity, newShare))
            }
            put("share", JSONObject().put("keys", keys).put("target", objectId)
                .put("name", obj.data.optString("name").ifEmpty { obj.kind }), newShare, newShare, members)
        }
        for (item in containerMembers(obj)) {
            val full = if (item.evicted) fetchNote(item.id) ?: item else item
            put(full.kind, rekeyFiles(full, newShare), newShare, full.id)
        }
        if (current != null && current != newShare) {
            get(current)?.takeIf { it.owner == userId }?.let { old ->
                put("share", JSONObject(old.data.toString()).put("keys", JSONObject()), current, current, emptyList())
            }
        }
        return newShare
    }

    fun rekeyFiles(item: SyncObject, newShare: String?): JSONObject {
        val data = JSONObject(item.data.toString())
        val body = data.optJSONArray("body") ?: return data
        for (index in 0 until body.length()) {
            val block = body.optJSONObject(index) ?: continue
            // Pictures, attached files and link-preview pictures are encrypted with the share's key.
            if (block.optString("t") in setOf("image", "file", "link") && block.optString("f").isNotEmpty()) {
                try {
                    val content = fetchFile(block.getString("f"), item.share).readBytes()
                    block.put("f", uploadFile(content, newShare))
                } catch (error: Exception) {
                    // Keep the old reference; the picture stays readable for the owner.
                }
            }
        }
        return data
    }

    // ================================================================
    // KEEPING NOTES ON THE PHONE
    // ================================================================

    fun keepDefault(): String = get("settings-$userId")?.data?.optString("keep")?.ifEmpty { null } ?: Keep.DEFAULT

    fun setKeepDefault(value: String) {
        val existing = get("settings-$userId")?.data ?: JSONObject()
        put("settings", JSONObject(existing.toString()).put("keep", value), null, "settings-$userId")
    }

    // --- key file: recommended, never forced (first start stays simple) ---

    private fun settings(): JSONObject = get("settings-$userId")?.data ?: JSONObject()

    private fun updateSettings(change: (JSONObject) -> Unit) {
        val data = JSONObject(settings().toString())
        change(data)
        put("settings", data, null, "settings-$userId")
    }

    /** How note lists are sorted – synced, so all devices show the same order. */
    fun noteSort(): String = settings().optString("note_sort", "modified")

    fun setNoteSort(order: String) = updateSettings { it.put("note_sort", order) }

    /** Profi-Funktionen (code colors, footnotes …): off by default so the app stays simple
     *  ("Tante Erna" first); a setting of the account, so every device follows. */
    var proFeatures: Boolean
        get() = settings().optBoolean("pro", false)
        set(value) = updateSettings { it.put("pro", value) }

    fun keyfileSaved(): Boolean = settings().optDouble("keyfile_saved", 0.0) > 0

    fun markKeyfileSaved() = updateSettings { it.put("keyfile_saved", System.currentTimeMillis() / 1000.0) }

    /** A gentle reminder once the account has been in use for a few days – never at the first start. */
    fun keyfileHintDue(): Boolean {
        if (isLocal || keyfileSaved()) return false
        val now = System.currentTimeMillis() / 1000.0
        val since = settings().optDouble("since", 0.0)
        if (since <= 0) { updateSettings { it.put("since", now) }; return false }
        return now - since > 3 * 86400 && now > settings().optDouble("keyfile_hint_until", 0.0)
    }

    fun snoozeKeyfileHint() = updateSettings { it.put("keyfile_hint_until", System.currentTimeMillis() / 1000.0 + 30 * 86400) }

    fun keepOf(note: SyncObject): String = note.data.optString("keep").ifEmpty { keepDefault() }

    // --- changes by others in shared notes (like Apple's highlights) ---
    // What I saw last of each shared note is remembered on this device (same as Ubuntu's activity.py).

    private fun seenNotes(): JSONObject = try { JSONObject(uiPrefs.getString("seen-notes", "{}") ?: "{}") } catch (error: Exception) { JSONObject() }

    /** Notes I have never opened count as new only for changes after this feature arrived. */
    private fun activitySince(): Double {
        val first = uiPrefs.getLong("activity-since", 0)
        if (first > 0) return first / 1000.0
        val now = System.currentTimeMillis()
        uiPrefs.edit().putLong("activity-since", now).apply()
        return now / 1000.0
    }

    /** I have seen this version (opened it, or saved it myself). */
    fun rememberSeen(note: SyncObject, blocks: JSONArray) {
        if (note.share == null) return
        val seen = seenNotes()
        seen.put(note.id, JSONObject().put("t", Model.modified(note)).put("l", JSONArray(Model.blockLines(blocks))))
        uiPrefs.edit().putString("seen-notes", seen.toString()).apply()
    }

    fun changedByOther(note: SyncObject) = note.share != null && note.updatedBy != 0 && note.updatedBy != userId

    /** A dot in the list: someone else changed it since I looked (Apple: the blue dot). */
    fun unread(note: SyncObject): Boolean {
        if (!changedByOther(note) || note.data.has("trashed")) return false
        val snapshot = seenNotes().optJSONObject(note.id)
        return Model.modified(note) > (snapshot?.optDouble("t") ?: activitySince()) + 1
    }

    /** Lines (block indices) changed by someone else since my last view, null: nothing to show. */
    fun changesSinceSeen(note: SyncObject, blocks: JSONArray): List<Int>? {
        val snapshot = seenNotes().optJSONObject(note.id) ?: return null
        if (!unread(note)) return null
        val old = snapshot.optJSONArray("l") ?: JSONArray()
        return Model.changedLines((0 until old.length()).map { old.optString(it) }, Model.blockLines(blocks)).ifEmpty { null }
    }

    fun markOpened(id: String) {
        openedPrefs.edit().putLong(id, System.currentTimeMillis() / 1000).apply()
    }

    private fun shouldEvict(note: SyncObject, now: Double): Boolean {
        if (server.isEmpty()) return false
        if (note.deleted || note.evicted || note.id == openNote) return false
        if (note.data.optBoolean("pinned")) return false
        val keep = keepOf(note)
        if (keep == Keep.ALWAYS) return false
        if (keep == Keep.SERVER) return true
        val days = keep.toIntOrNull() ?: return false
        val lastUse = maxOf(openedPrefs.getLong(note.id, 0).toDouble(), Model.modified(note))
        return now - lastUse > days * 86_400
    }

    /** Remove note contents from the phone according to the chosen period. */
    fun evict(): Int {
        val now = Model.now()
        var count = 0
        synchronized(lock) {
            val pendingIds = pending.map { it.getString("id") }.toSet()
            for (note in plain.values.filter { it.kind == "note" }.toList()) {
                if (note.id in pendingIds || !shouldEvict(note, now)) continue
                val item = remote[note.id] ?: continue
                item.optJSONObject("data")?.remove("b")
                decrypt(item)?.let { plain[note.id] = it }
                count++
            }
        }
        if (count > 0) {
            save()
            bump()
        }
        return count
    }

    /** Load an evicted note's content from the server (blocking). */
    fun fetchNote(id: String): SyncObject? {
        val item = api?.getObject(id) ?: return null
        synchronized(lock) {
            remote[id] = item
            decrypt(item)?.let { plain[id] = it }
        }
        save()
        bump()
        return get(id)
    }

    // ================================================================
    // BACKGROUND SYNC
    // ================================================================

    fun start() {
        if (jobs.isNotEmpty() || api == null) return
        jobs = listOf(scope.launch { pushLoop() }, scope.launch { pullLoop() }, scope.launch { channelLoop() })
        wake.trySend(Unit)
    }

    fun stop() {
        jobs.forEach { it.cancel() }
        jobs = emptyList()
        save()
    }

    private suspend fun pushLoop() {
        var backoff = 2_000L
        while (scope.isActive) {
            withTimeoutOrNull(30_000) { wake.receive() }
            delay(500)
            try {
                pushOnce()
                backoff = 2_000
            } catch (error: OfflineException) {
                online.value = false
                delay(backoff)
                backoff = (backoff * 2).coerceAtMost(60_000)
                wake.trySend(Unit)
            } catch (error: ApiException) {
                if (error.status == 401) { signedOut.value = true; return }
                delay(5_000)
            } catch (error: Exception) {
                delay(5_000)
                wake.trySend(Unit)
            }
        }
    }

    fun pushOnce() {
        val api = api ?: return
        val batch = synchronized(lock) { pending.take(200).map { JSONObject(it.toString()) } }
        if (batch.isEmpty()) return
        val wire = JSONArray(batch.map { JSONObject(it.toString()).apply { remove("updated") } })
        val results = api.push(wire)
        online.value = true
        val conflicts = mutableListOf<JSONObject>()
        synchronized(lock) {
            batch.forEachIndexed { index, sent ->
                val result = results.optJSONObject(index) ?: return@forEachIndexed
                val id = sent.getString("id")
                val status = result.optString("status")
                val current = pending.indexOfFirst { it.getString("id") == id }
                if (status == "conflict") {
                    conflicts.add(sent)
                    if (current >= 0) pending.removeAt(current)
                    return@forEachIndexed
                }
                if (status == "ok") {
                    val version = result.optLong("version")
                    remote[id] = JSONObject().put("id", id).put("kind", sent.getString("kind"))
                        .put("share", sent.opt("share") ?: JSONObject.NULL)
                        .put("owner", plain[id]?.owner ?: userId)
                        .put("data", sent.optJSONObject("data") ?: JSONObject())
                        .put("deleted", sent.optBoolean("deleted")).put("version", version)
                        .put("updated", Model.now()).put("updated_by", userId)
                    plain[id]?.let { plain[id] = it.withVersion(version) }
                }
                if (current >= 0) {
                    val now = pending[current]
                    val same = now.optJSONObject("data")?.toString() == sent.optJSONObject("data")?.toString() &&
                        now.optBoolean("deleted") == sent.optBoolean("deleted")
                    if (same || status != "ok") pending.removeAt(current) else now.put("base", result.optLong("version"))
                }
            }
        }
        for (sent in conflicts) resolveConflict(sent)
        save()
        if (conflicts.isNotEmpty()) { rebuild(); bump() }
        if (synchronized(lock) { pending.isNotEmpty() }) wake.trySend(Unit)
    }

    /** Someone else changed the note meanwhile: keep theirs, save ours as a copy. */
    private fun resolveConflict(sent: JSONObject) {
        val theirs = try { api?.getObject(sent.getString("id")) } catch (error: Exception) { null } ?: return
        val mine = synchronized(lock) {
            remote[theirs.getString("id")] = theirs
            decrypt(pendingAsRemote(sent))
        } ?: return
        if (mine.deleted) return
        val data = JSONObject(mine.data.toString()).put("conflict", true)
        data.optJSONArray("body")?.optJSONObject(0)?.let { it.put("x", it.optString("x") + tr(" (Konflikt)")) }
        put("note", data, mine.share)
    }

    private suspend fun pullLoop() {
        var backoff = 2_000L
        while (scope.isActive) {
            try {
                pullOnce(25)
                backoff = 2_000
            } catch (error: OfflineException) {
                online.value = false
                delay(backoff)
                backoff = (backoff * 2).coerceAtMost(60_000)
            } catch (error: ApiException) {
                if (error.status == 401) { signedOut.value = true; return }
                delay(10_000)
            } catch (error: Exception) {
                delay(5_000)
            }
        }
    }

    fun pullOnce(wait: Int = 0) {
        val api = api ?: return
        val response = api.pull(cursor, wait)
        online.value = true
        var changed = false
        synchronized(lock) {
            val objects = response.getJSONArray("objects")
            for (index in 0 until objects.length()) {
                val item = objects.getJSONObject(index)
                remote[item.getString("id")] = item
                changed = true
            }
            val member = response.optJSONArray("shares")?.let { a -> (0 until a.length()).map { a.getString(it) }.toSet() } ?: emptySet()
            for ((id, item) in remote.entries.toList()) {
                val share = item.optString("share").takeIf { it.isNotEmpty() && it != "null" }
                if (share != null && share !in member && item.optInt("owner") != userId) {
                    remote.remove(id)
                    changed = true
                }
            }
            cursor = response.optLong("cursor", cursor)
            response.optJSONArray("users")?.let { a -> users = (0 until a.length()).map { userFrom(a.getJSONObject(it)) } }
            if (changed) rebuild()
        }
        if (changed) evict()
        save()
        if (changed) bump()
        if (response.optBoolean("more")) pullOnce()
    }

    fun syncNow() {
        try {
            pushOnce()
            pullOnce()
        } catch (error: Exception) {
            online.value = false
        }
    }

    private suspend fun channelLoop() {
        while (scope.isActive) {
            try {
                val list = api?.channels() ?: JSONArray()
                for (index in 0 until list.length()) {
                    val channel = list.getJSONObject(index)
                    if (!seenChannels.add(channel.getString("channel"))) continue
                    // Someone new (e.g. just registered): refresh the list of people first.
                    val from = channel.optInt("from")
                    if (from != 0 && userById(from) == null) try { pullOnce() } catch (error: Exception) { }
                    requests.emit(channel)
                }
            } catch (error: Exception) {
            }
            delay(4_000)
        }
    }

    // ================================================================
    // FILES (encrypted with the key of their container)
    // ================================================================

    fun fetchFile(reference: String, share: String?): File {
        val fileId = reference.substringBefore(":")
        val name = reference.substringAfter(":", fileId)
        val target = File(filesDir, name)
        filesDir.mkdirs()  // Android may clear the cache at any time.
        if (!target.exists() && fileId == "local") {
            val key = keyFor(null) ?: throw E2E.CryptoError("no key")
            target.writeBytes(E2E.openBytes(key, File(localFiles, name).readBytes(), name))
        } else if (!target.exists()) {
            val blob = api?.download(fileId) ?: throw OfflineException("no session")
            val key = keyFor(share) ?: throw E2E.CryptoError("no key")
            target.writeBytes(E2E.openBytes(key, blob, name))
        }
        return target
    }

    fun uploadFile(content: ByteArray, share: String?, progress: ((Long, Long) -> Unit)? = null): String {
        val name = UUID.randomUUID().toString().replace("-", "")
        val key = keyFor(share) ?: throw E2E.CryptoError("no key")
        if (server.isEmpty()) {
            // Without a server: keep it (encrypted) on the device.
            localFiles.mkdirs()
            File(localFiles, name).writeBytes(E2E.sealBytes(key, content, name))
            filesDir.mkdirs()
            File(filesDir, name).writeBytes(content)
            return "local:$name"
        }
        val id = api?.upload(E2E.sealBytes(key, content, name), share, progress) ?: throw OfflineException("no session")
        filesDir.mkdirs()
        File(filesDir, name).writeBytes(content)
        return "$id:$name"
    }

    fun launch(block: suspend CoroutineScope.() -> Unit) = scope.launch(block = block)
}
