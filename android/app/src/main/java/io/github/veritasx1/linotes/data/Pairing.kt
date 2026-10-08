package io.github.veritasx1.linotes.data

import io.github.veritasx1.linotes.i18n.tr

import org.json.JSONObject
import java.security.MessageDigest

/**
 * Linking devices and verifying people with a 6-digit code (SPAKE2),
 * the Android twin of linux/linotes/pairing.py. All calls block: run them
 * off the main thread.
 */
object Pairing {
    class PairingError(message: String) : Exception(message)

    private val LINK_A = "linotes-new-device".toByteArray()
    private val LINK_B = "linotes-account".toByteArray()
    private val VERIFY_A = "linotes-verify-a".toByteArray()
    private val VERIFY_B = "linotes-verify-b".toByteArray()

    data class Scanned(val purpose: String, val channel: String, val code: String)

    fun qrText(purpose: String, channel: String, code: String) = "LINOTES|$purpose|$channel|$code"

    fun parseQr(text: String): Scanned {
        val parts = text.trim().split("|")
        if (parts.size != 4 || parts[0] != "LINOTES" || parts[1] !in setOf("link", "verify")) throw PairingError(tr("Kein LiNotes-Code"))
        return Scanned(parts[1], parts[2], parts[3])
    }

    private fun waitMessage(api: Api, channel: String, after: Int, role: String, timeoutSeconds: Int, cancelled: () -> Boolean = { false }): JSONObject {
        val deadline = System.currentTimeMillis() + timeoutSeconds * 1000L
        var last = after
        while (System.currentTimeMillis() < deadline && !cancelled()) {
            val wait = ((deadline - System.currentTimeMillis()) / 1000).toInt().coerceIn(1, 20)
            val messages = try {
                api.relayGet(channel, last, wait)
            } catch (error: ApiException) {
                if (error.status == 404) throw PairingError(tr("Der Vorgang wurde abgebrochen oder ist abgelaufen."))
                throw error
            }
            for (index in 0 until messages.length()) {
                val message = messages.getJSONObject(index)
                if (message.getString("role") == role) return message
                last = message.getInt("seq")
            }
        }
        throw PairingError(tr("Zeitüberschreitung"))
    }

    private fun payloadKey(ke: ByteArray) = E2E.hkdf(ke, "linotes v2 pairing payload")

    private fun mac(ke: ByteArray, label: ByteArray, value: String) = E2E.toHex(E2E.hmac(payloadKey(ke), label + value.toByteArray()))

    private fun equal(a: String, b: String) = MessageDigest.isEqual(a.toByteArray(), b.toByteArray())

    // --- linking ----------------------------------------------------------

    /** On the device that wants to join (role A). */
    class NewDeviceLink(private val api: Api, username: String, device: String) {
        val channel: String = api.linkRequest(username, device)
        val code: String = E2E.newCode()
        val qr: String = qrText("link", channel, code)
        private val spake = E2E.Spake2("A", E2E.spakeW(code, channel), LINK_A, LINK_B)

        init {
            api.relayPost(channel, "A", E2E.toHex(spake.message))
        }

        fun await(cancelled: () -> Boolean): ByteArray {
            val reply = JSONObject(waitMessage(api, channel, 1, "B", 9 * 60, cancelled).getString("body"))
            val result = spake.finish(E2E.hex(reply.getString("p")))
            if (!equal(reply.optString("c"), E2E.toHex(result.expected))) {
                close()
                throw PairingError(tr("Der Code war falsch. Bitte neu versuchen."))
            }
            val content = E2E.open(payloadKey(result.ke), reply.getJSONObject("k"), "link")
            api.relayPost(channel, "A", JSONObject().put("ok", true).put("c", E2E.toHex(result.confirmation)).toString())
            return E2E.unb64(content.getString("secret"))
        }

        fun close() {
            try { api.relayClose(channel) } catch (error: Exception) { }
        }
    }

    /** On a signed-in device (role B): send the account secret. */
    fun approveLink(api: Api, channel: String, code: String, account: E2E.Account) {
        val first = waitMessage(api, channel, 0, "A", 30)
        val spake = E2E.Spake2("B", E2E.spakeW(code.trim(), channel), LINK_A, LINK_B)
        val result = spake.finish(E2E.hex(first.getString("body")))
        val sealed = E2E.seal(payloadKey(result.ke), JSONObject().put("secret", E2E.b64(account.secret)), "link")
        api.relayPost(channel, "B", JSONObject().put("p", E2E.toHex(spake.message)).put("c", E2E.toHex(result.confirmation)).put("k", sealed).toString())
        val done = try {
            JSONObject(waitMessage(api, channel, first.getInt("seq"), "A", 40).getString("body"))
        } catch (error: PairingError) {
            throw PairingError(tr("Das neue Gerät hat nicht bestätigt – war der Code richtig?"))
        }
        if (!equal(done.optString("c"), E2E.toHex(result.expected))) throw PairingError(tr("Der Code war falsch."))
    }

    // --- verifying a person ---------------------------------------------

    private fun peerPublic(users: List<User>, id: Int) = users.firstOrNull { it.id == id }?.identity ?: throw PairingError(tr("Unbekannter Account"))

    /** Shows the code (role A). */
    class VerifyShow(private val api: Api, private val otherId: Int) {
        val channel: String = api.verifyRequest(otherId)
        val code: String = E2E.newCode()
        val qr: String = qrText("verify", channel, code)
        private val spake = E2E.Spake2("A", E2E.spakeW(code, channel), VERIFY_A, VERIFY_B)

        init {
            api.relayPost(channel, "A", E2E.toHex(spake.message))
        }

        fun await(myPublic: String, users: List<User>, cancelled: () -> Boolean): String {
            val reply = JSONObject(waitMessage(api, channel, 1, "B", 9 * 60, cancelled).getString("body"))
            val result = spake.finish(E2E.hex(reply.getString("p")))
            if (!equal(reply.optString("c"), E2E.toHex(result.expected))) throw PairingError(tr("Der eingegebene Code war falsch."))
            val peer = peerPublic(users, otherId)
            if (!equal(reply.optString("m"), mac(result.ke, VERIFY_B, peer))) throw PairingError(tr("Der Schlüssel des anderen Accounts stimmt nicht mit dem Server überein!"))
            api.relayPost(channel, "A", JSONObject().put("c", E2E.toHex(result.confirmation)).put("m", mac(result.ke, VERIFY_A, myPublic)).toString())
            return E2E.fingerprint(peer)
        }
    }

    /** Types the code (role B). */
    fun verifyEnter(api: Api, channel: String, code: String, otherId: Int, myPublic: String, users: List<User>): String {
        val first = waitMessage(api, channel, 0, "A", 30)
        val spake = E2E.Spake2("B", E2E.spakeW(code.trim(), channel), VERIFY_A, VERIFY_B)
        val result = spake.finish(E2E.hex(first.getString("body")))
        api.relayPost(channel, "B", JSONObject().put("p", E2E.toHex(spake.message)).put("c", E2E.toHex(result.confirmation))
            .put("m", mac(result.ke, VERIFY_B, myPublic)).toString())
        val done = JSONObject(waitMessage(api, channel, first.getInt("seq"), "A", 60).getString("body"))
        if (!equal(done.optString("c"), E2E.toHex(result.expected))) throw PairingError(tr("Der Code war falsch."))
        val peer = peerPublic(users, otherId)
        if (!equal(done.optString("m"), mac(result.ke, VERIFY_A, peer))) throw PairingError(tr("Der Schlüssel des anderen Accounts stimmt nicht mit dem Server überein!"))
        return E2E.fingerprint(peer)
    }

    // --- trust store (private, synced) ------------------------------------

    fun contactsId(sync: SyncEngine) = "contacts-${sync.userId}"

    /** "verified", "unverified" or "changed". */
    fun verifiedState(sync: SyncEngine, user: User): String {
        val stored = sync.get(contactsId(sync))?.data?.optJSONObject("verified")?.optString(user.id.toString()).orEmpty()
        return when {
            stored.isEmpty() -> "unverified"
            stored == E2E.fingerprint(user.identity) -> "verified"
            else -> "changed"
        }
    }

    fun markVerified(sync: SyncEngine, userId: Int, fingerprint: String) {
        val existing = sync.get(contactsId(sync))?.data ?: JSONObject().put("verified", JSONObject())
        val data = JSONObject(existing.toString())
        val verified = data.optJSONObject("verified") ?: JSONObject()
        verified.put(userId.toString(), fingerprint)
        data.put("verified", verified)
        sync.put("contacts", data, null, contactsId(sync))
    }
}
