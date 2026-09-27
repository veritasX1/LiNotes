package io.github.veritasx1.linotes

import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.data.Api
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncEngine
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/** Using LiNotes without a server, then moving everything into a new account
 *  (needs the scratch server on 127.0.0.1:8499, invite in android_invite2.txt). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LocalModeTest {
    private val scratch = "/tmp/claude-1000/-home-olaf-winkler/307e9b08-3ef7-4558-9ee3-51920f668e56/scratchpad"
    private val server = "http://127.0.0.1:8499"

    @Test
    fun localThenConnect() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        assertTrue(sync.isLocal)
        Model.ensureDefaults(sync)
        val folder = Model.privateFolder(sync.userId)
        val picture = sync.uploadFile(byteArrayOf(1, 2, 3, 4), null)
        assertTrue(picture.startsWith("local:"))
        val body = JSONArray().put(JSONObject().put("t", "title").put("x", "Offline geschrieben"))
            .put(JSONObject().put("t", "image").put("f", picture))
        val note = sync.put("note", JSONObject().put("folder", folder).put("body", body).put("created", Model.now()).put("modified", Model.now()))
        sync.put("item", JSONObject().put("list", Model.defaultList(sync.userId)).put("text", "Milch").put("by", sync.userId))

        // Later: create an account on a server with the keys this device already has.
        val invite = File("$scratch/android_invite2.txt").readText().trim()
        val response = Api(server).register(invite, "offline", "Offline", sync.account!!.auth,
            sync.identity!!.exportSealed(sync.account!!), "robolectric")
        sync.connectLocal(server, response, sync.account!!)
        sync.syncNow()
        assertFalse(sync.isLocal)
        val uid = sync.userId
        assertTrue(uid > 0)
        val moved = sync.get(note.id)!!
        assertEquals("notes-$uid", moved.data.getString("folder"))
        val reference = moved.data.getJSONArray("body").getJSONObject(1).getString("f")
        assertFalse(reference.startsWith("local:"))
        val item = sync.all("item").single()
        assertEquals("list-$uid", item.data.getString("list"))
        assertEquals(uid, item.data.getInt("by"))
        assertTrue(sync.exists("notes-$uid") && sync.exists("board-$uid-offen"))

        // A second device of this account sees everything, pictures included.
        val raw = sync.api!!.pull(0)
        val ids = (0 until raw.getJSONArray("objects").length()).map { raw.getJSONArray("objects").getJSONObject(it).getString("id") }
        assertTrue(note.id in ids && "list-$uid" in ids)
        assertFalse(ids.any { it.contains("--1") })
        File(ApplicationProvider.getApplicationContext<android.content.Context>().cacheDir, "files").deleteRecursively()
        assertEquals(listOf<Byte>(1, 2, 3, 4), sync.fetchFile(reference, null).readBytes().toList())
    }
}
