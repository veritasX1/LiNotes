package io.github.veritasx1.linotes

import androidx.test.core.app.ApplicationProvider
import io.github.veritasx1.linotes.data.E2E
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject
import io.github.veritasx1.linotes.data.User
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Card fc38cfad (08.10.2026: cards lost twice): sharing a board with more people keeps the share – everyone reads every
 *  card, other people's too; removing someone rotates the key only when everything inside is the sharer's own.
 *  Twin of linux/tests/test_share_keeps_others.py. Runs without a server. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ShareKeepsOthersTest {
    private val bernd = 2
    private val carla = 3

    @Suppress("UNCHECKED_CAST")
    private fun plain(sync: SyncEngine) = SyncEngine::class.java.getDeclaredField("plain").apply { isAccessible = true }
        .get(sync) as LinkedHashMap<String, SyncObject>

    /** What [uid] would read of [id]: their key unwrapped from the share, the server data opened. */
    private fun readable(sync: SyncEngine, people: Map<Int, E2E.Identity>, uid: Int, id: String): JSONObject? {
        val obj = sync.get(id)!!
        val wrapped = sync.get(obj.share!!)!!.data.getJSONObject("keys").optJSONObject(uid.toString()) ?: return null
        val key = E2E.unwrapKey(people.getValue(uid), wrapped, obj.share!!)
        val encrypt = SyncEngine::class.java.getDeclaredMethod("encrypt", SyncObject::class.java).apply { isAccessible = true }
        return E2E.open(key, (encrypt.invoke(sync, obj) as JSONObject).getJSONObject("m"), "$id|m")
    }

    @Test
    fun addingPeopleKeepsOthersCards() {
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        sync.startLocal("Olaf")
        val people = mapOf(bernd to E2E.Identity.create(), carla to E2E.Identity.create())
        SyncEngine::class.java.getDeclaredField("users").apply { isAccessible = true }
            .set(sync, sync.users + people.map { (uid, identity) -> User(uid, "u$uid", "P$uid", identity.public) })

        val board = sync.put("board", JSONObject().put("name", "Change Requests"))
        val column = sync.put("column", JSONObject().put("board", board.id).put("name", "CR"))
        val mine = sync.put("card", JSONObject().put("board", board.id).put("column", column.id).put("title", "Meine Karte"))
        val first = sync.setSharing(board.id, listOf(bernd))!!
        // Bernd writes a card into the shared board – his, so only he could ever move it to another share.
        val his = sync.put("card", JSONObject().put("board", board.id).put("column", column.id).put("title", "Bernds Karte"), first)
        plain(sync)[his.id] = SyncObject(his.id, his.kind, his.share, bernd, his.data, false, his.version, his.updated, bernd)

        assertEquals(first, sync.setSharing(board.id, listOf(bernd, carla)))
        for (uid in listOf(bernd, carla)) for ((id, title) in listOf(mine.id to "Meine Karte", his.id to "Bernds Karte")) {
            assertEquals(first, sync.get(id)!!.share)
            assertEquals(title, readable(sync, people, uid, id)!!.getString("title"))
        }

        // Carla leaves while Bernd's card is inside: no new key (it would strand his card), her key is gone.
        assertEquals(first, sync.setSharing(board.id, listOf(bernd)))
        assertNull(readable(sync, people, carla, his.id))
        assertEquals("Bernds Karte", readable(sync, people, bernd, his.id)!!.getString("title"))

        // A board that is all mine: removing someone still rotates the key, the old share is emptied (as before).
        val solo = sync.put("board", JSONObject().put("name", "Nur meins"))
        val card = sync.put("card", JSONObject().put("board", solo.id).put("title", "Allein"))
        val s1 = sync.setSharing(solo.id, listOf(bernd, carla))!!
        val s2 = sync.setSharing(solo.id, listOf(bernd))!!
        assertNotEquals(s1, s2)
        assertEquals(s2, sync.get(card.id)!!.share)
        assertEquals(0, sync.get(s1)!!.data.getJSONObject("keys").length())
        assertEquals("Allein", readable(sync, people, bernd, card.id)!!.getString("title"))
    }
}
