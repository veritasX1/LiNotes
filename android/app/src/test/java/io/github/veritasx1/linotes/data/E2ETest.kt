package io.github.veritasx1.linotes.data

import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.math.BigInteger

// Robolectric only for org.json (the crypto itself is plain JVM).
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class E2ETest {
    private val scratch = File("/tmp/claude-1000/-home-olaf-winkler/307e9b08-3ef7-4558-9ee3-51920f668e56/scratchpad")

    private data class Vector(val a: String, val b: String, val w: String, val x: String, val y: String,
                              val pA: String, val pB: String, val ke: String, val cA: String, val cB: String)

    private val vectors = listOf(
        Vector("server", "client",
            "2ee57912099d31560b3a44b1184b9b4866e904c49d12ac5042c97dca461b1a5f",
            "43dd0fd7215bdcb482879fca3220c6a968e66d70b1356cac18bb26c84a78d729",
            "dcb60106f276b02606d8ef0a328c02e4b629f84f89786af5befb0bc75b6e66be",
            "04a56fa807caaa53a4d28dbb9853b9815c61a411118a6fe516a8798434751470f9010153ac33d0d5f2047ffdb1a3e42c9b4e6be662766e1eeb4116988ede5f912c",
            "0406557e482bd03097ad0cbaa5df82115460d951e3451962f1eaf4367a420676d09857ccbc522686c83d1852abfa8ed6e4a1155cf8f1543ceca528afb591a1e0b7",
            "0e0672dc86f8e45565d338b0540abe69",
            "58ad4aa88e0b60d5061eb6b5dd93e80d9c4f00d127c65b3b35b1b5281fee38f0",
            "d3e2e547f1ae04f2dbdbf0fc4b79f8ecff2dff314b5d32fe9fcef2fb26dc459b"),
        Vector("", "client",
            "0548d8729f730589e579b0475a582c1608138ddf7054b73b5381c7e883e2efae",
            "403abbe3b1b4b9ba17e3032849759d723939a27a27b9d921c500edde18ed654b",
            "903023b6598908936ea7c929bd761af6039577a9c3f9581064187c3049d87065",
            "04a897b769e681c62ac1c2357319a3d363f610839c4477720d24cbe32f5fd85f44fb92ba966578c1b712be6962498834078262caa5b441ecfa9d4a9485720e918a",
            "04e0f816fd1c35e22065d5556215c097e799390d16661c386e0ecc84593974a61b881a8c82327687d0501862970c64565560cb5671f696048050ca66ca5f8cc7fc",
            "642f05c473c2cd79909f9a841e2f30a7",
            "47d29e6666af1b7dd450d571233085d7a9866e4d49d2645e2df975489521232b",
            "3313c5cefc361d27fb16847a91c2a73b766ffa90a4839122a9b70a2f6bd1d6df"),
    )

    @Test
    fun rfc9382Vectors() {
        for (v in vectors) {
            val w = BigInteger(v.w, 16)
            val a = E2E.Spake2("A", w, v.a.toByteArray(), v.b.toByteArray(), BigInteger(v.x, 16))
            val b = E2E.Spake2("B", w, v.a.toByteArray(), v.b.toByteArray(), BigInteger(v.y, 16))
            assertEquals(v.pA, E2E.toHex(a.message))
            assertEquals(v.pB, E2E.toHex(b.message))
            val ra = a.finish(b.message)
            val rb = b.finish(a.message)
            assertEquals(v.ke, E2E.toHex(ra.ke))
            assertEquals(v.ke, E2E.toHex(rb.ke))
            assertEquals(v.cA, E2E.toHex(ra.confirmation))
            assertEquals(v.cA, E2E.toHex(rb.expected))
            assertEquals(v.cB, E2E.toHex(rb.confirmation))
        }
    }

    @Test
    fun opensWhatLinuxWrote() {
        val s = JSONObject(File(scratch, "interop_py.json").readText())
        val account = E2E.Account(E2E.unb64(s.getString("secret")))
        assertEquals(s.getString("auth"), account.auth)
        val identity = E2E.Identity.fromSealed(account, s.getJSONObject("identity"))
        val shareKey = E2E.unwrapKey(identity, s.getJSONObject("wrapped"), "share-x")
        assertArrayEquals(E2E.unb64(s.getString("share_key")), shareKey)
        val item = E2E.open(shareKey, s.getJSONObject("sealed"), "item-1|m")
        assertEquals("Milch äöü ß", item.getString("text"))
        assertEquals("bilddaten", E2E.openBytes(shareKey, E2E.unb64(s.getString("blob")), "file-1").decodeToString())
        val keyfile = E2E.importKeyfile(s.getJSONObject("keyfile"), "tresor-passphrase")
        assertEquals("olaf", keyfile.username)
        assertArrayEquals(account.secret, keyfile.account.secret)
        assertEquals(s.getString("safety"), E2E.safetyNumber(identity.public, s.getString("safety_other")))
        assertEquals(s.getString("fingerprint"), E2E.fingerprint(identity.public))
        assertEquals(s.getString("spake_w").removePrefix("0x"), E2E.spakeW("123456", "kanal").toString(16))
        var rejected = false
        try { E2E.importKeyfile(s.getJSONObject("keyfile"), "falsch") } catch (error: E2E.CryptoError) { rejected = true }
        assertTrue(rejected)

        // The other direction: Linux checks what Android writes.
        val androidAccount = E2E.Account.create()
        val androidIdentity = E2E.Identity.create()
        val key = E2E.newKey()
        val out = JSONObject()
            .put("secret", E2E.b64(androidAccount.secret)).put("auth", androidAccount.auth)
            .put("identity", androidIdentity.exportSealed(androidAccount))
            .put("wrapped", E2E.wrapKey(key, androidIdentity.public, "share-y"))
            .put("share_key", E2E.b64(key))
            .put("sealed", E2E.seal(key, JSONObject().put("text", "Butter / Brot ä"), "item-2|m"))
            .put("blob", E2E.b64(E2E.sealBytes(key, "foto".toByteArray(), "file-2")))
            .put("keyfile", E2E.exportKeyfile("https://x.example", "anna", androidAccount, "zweite-passphrase"))
        File(scratch, "interop_android.json").writeText(out.toString())
    }
}
