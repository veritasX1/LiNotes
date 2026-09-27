package io.github.veritasx1.linotes.data

import android.util.Base64
import org.json.JSONObject
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * End-to-end encryption for locked notes, identical to the Linux client:
 * PBKDF2-HMAC-SHA256 (200 000 rounds) -> AES-256-GCM, JSON {"n","c"} in Base64.
 */
object Vault {
    const val ITERATIONS = 200_000
    private const val CHECK = "LiNotes"
    private val random = SecureRandom()

    class WrongPassword : Exception("wrong password")

    private fun b64(bytes: ByteArray) = Base64.encodeToString(bytes, Base64.NO_WRAP)
    private fun unb64(text: String) = Base64.decode(text, Base64.NO_WRAP)

    fun derive(password: String, salt: ByteArray, iterations: Int = ITERATIONS): ByteArray {
        val spec = PBEKeySpec(password.toCharArray(), salt, iterations, 256)
        return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
    }

    fun seal(key: ByteArray, plain: String): JSONObject {
        val nonce = ByteArray(12).also { random.nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        return JSONObject().put("n", b64(nonce)).put("c", b64(cipher.doFinal(plain.toByteArray())))
    }

    fun open(key: ByteArray, box: JSONObject): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, unb64(box.getString("n"))))
        return cipher.doFinal(unb64(box.getString("c"))).decodeToString()
    }

    /** Returns vault data (for the server) and the key. */
    fun create(password: String, hint: String): Pair<JSONObject, ByteArray> {
        val salt = ByteArray(16).also { random.nextBytes(it) }
        val key = derive(password, salt)
        // Seal the JSON string "LiNotes" exactly like Python's json.dumps.
        val data = JSONObject()
            .put("salt", b64(salt))
            .put("iter", ITERATIONS)
            .put("hint", hint)
            .put("check", seal(key, "\"$CHECK\""))
        return data to key
    }

    fun unlock(vault: JSONObject, password: String): ByteArray {
        val key = derive(password, unb64(vault.getString("salt")), vault.optInt("iter", ITERATIONS))
        val check = try {
            open(key, vault.getJSONObject("check"))
        } catch (error: Exception) {
            throw WrongPassword()
        }
        if (check != "\"$CHECK\"") throw WrongPassword()
        return key
    }

    fun checkKey(vault: JSONObject, key: ByteArray): Boolean =
        try { open(key, vault.getJSONObject("check")) == "\"$CHECK\"" } catch (error: Exception) { false }

    /** Encrypt a note body (list of blocks) the same way as the Linux app: {"body": [...]}. */
    fun sealBody(key: ByteArray, body: org.json.JSONArray): JSONObject =
        seal(key, JSONObject().put("body", body).toString())

    fun openBody(key: ByteArray, box: JSONObject): org.json.JSONArray =
        JSONObject(open(key, box)).getJSONArray("body")
}
