package io.github.veritasx1.linotes.data

import org.json.JSONObject
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.interfaces.ECPrivateKey
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPrivateKeySpec
import java.security.spec.ECPublicKeySpec
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * End-to-end encryption, byte-for-byte compatible with linux/linotes/e2e.py
 * (see docs/SECURITY.md). Pure JVM: no Android classes, so it is unit tested
 * directly, including the RFC 9382 SPAKE2 test vectors.
 */
object E2E {
    class CryptoError(message: String) : Exception(message)

    private val random = SecureRandom()

    fun b64(bytes: ByteArray): String = Base64.getEncoder().encodeToString(bytes)
    fun unb64(text: String): ByteArray = Base64.getDecoder().decode(text)
    fun randomBytes(size: Int) = ByteArray(size).also { random.nextBytes(it) }
    fun newKey() = randomBytes(32)

    // --- HKDF / HMAC ---------------------------------------------------

    fun hmac(key: ByteArray, data: ByteArray): ByteArray =
        Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(key, "HmacSHA256")) }.doFinal(data)

    fun hkdf(secret: ByteArray, info: ByteArray, length: Int = 32, salt: ByteArray? = null): ByteArray {
        val prk = hmac(salt ?: ByteArray(32), secret)
        val out = ByteArray(length)
        var previous = ByteArray(0)
        var offset = 0
        var counter = 1
        while (offset < length) {
            previous = hmac(prk, previous + info + byteArrayOf(counter.toByte()))
            val take = minOf(previous.size, length - offset)
            System.arraycopy(previous, 0, out, offset, take)
            offset += take
            counter++
        }
        return out
    }

    fun hkdf(secret: ByteArray, info: String, length: Int = 32) = hkdf(secret, info.toByteArray(), length)

    fun sha256(data: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(data)

    // --- AES-GCM -----------------------------------------------------

    private fun gcm(mode: Int, key: ByteArray, nonce: ByteArray, aad: String) =
        Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(mode, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
            updateAAD(aad.toByteArray())
        }

    /** Encrypt a JSON value (object, array or string encoded as JSON text). */
    fun sealText(key: ByteArray, json: String, aad: String): JSONObject {
        val nonce = randomBytes(12)
        val cipher = gcm(Cipher.ENCRYPT_MODE, key, nonce, aad).doFinal(json.toByteArray())
        return JSONObject().put("n", b64(nonce)).put("c", b64(cipher))
    }

    fun openText(key: ByteArray, box: JSONObject, aad: String): String = try {
        gcm(Cipher.DECRYPT_MODE, key, unb64(box.getString("n")), aad).doFinal(unb64(box.getString("c"))).decodeToString()
    } catch (error: Exception) {
        throw CryptoError("decryption failed")
    }

    fun seal(key: ByteArray, value: JSONObject, aad: String) = sealText(key, value.toString(), aad)
    fun open(key: ByteArray, box: JSONObject, aad: String) = JSONObject(openText(key, box, aad))

    fun sealBytes(key: ByteArray, data: ByteArray, aad: String): ByteArray {
        val nonce = randomBytes(12)
        return nonce + gcm(Cipher.ENCRYPT_MODE, key, nonce, aad).doFinal(data)
    }

    fun openBytes(key: ByteArray, blob: ByteArray, aad: String): ByteArray = try {
        gcm(Cipher.DECRYPT_MODE, key, blob.copyOfRange(0, 12), aad).doFinal(blob, 12, blob.size - 12)
    } catch (error: Exception) {
        throw CryptoError("decryption failed")
    }

    // --- account -------------------------------------------------------

    class Account(val secret: ByteArray) {
        val auth: String = b64(hkdf(secret, "linotes v2 auth"))
        val privateKey: ByteArray = hkdf(secret, "linotes v2 private data")
        val identityWrapKey: ByteArray = hkdf(secret, "linotes v2 identity")

        companion object {
            fun create() = Account(randomBytes(32))
        }
    }

    // --- P-256 keys -----------------------------------------------------

    val curve: ECParameterSpec by lazy {
        AlgorithmParameters.getInstance("EC").apply { init(ECGenParameterSpec("secp256r1")) }
            .getParameterSpec(ECParameterSpec::class.java)
    }

    private fun fixed(value: BigInteger): ByteArray {
        val raw = value.toByteArray()
        return when {
            raw.size == 32 -> raw
            raw.size > 32 -> raw.copyOfRange(raw.size - 32, raw.size)
            else -> ByteArray(32 - raw.size) + raw
        }
    }

    fun encodePublic(key: ECPublicKey): ByteArray = byteArrayOf(4) + fixed(key.w.affineX) + fixed(key.w.affineY)

    fun decodePublic(bytes: ByteArray): ECPublicKey {
        if (bytes.size != 65 || bytes[0] != 4.toByte()) throw CryptoError("bad public key")
        val point = ECPoint(BigInteger(1, bytes.copyOfRange(1, 33)), BigInteger(1, bytes.copyOfRange(33, 65)))
        return KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(point, curve)) as ECPublicKey
    }

    class Identity(val private: ECPrivateKey, val publicBytes: ByteArray) {
        val public: String get() = b64(publicBytes)

        fun exportSealed(account: Account): JSONObject = JSONObject()
            .put("pub", public)
            .put("priv", sealText(account.identityWrapKey, JSONObject.quote(b64(fixed(private.s))), "identity"))

        companion object {
            fun create(): Identity {
                val pair = KeyPairGenerator.getInstance("EC").apply { initialize(ECGenParameterSpec("secp256r1"), random) }.generateKeyPair()
                return Identity(pair.private as ECPrivateKey, encodePublic(pair.public as ECPublicKey))
            }

            fun fromSealed(account: Account, data: JSONObject): Identity {
                val quoted = openText(account.identityWrapKey, data.getJSONObject("priv"), "identity")
                val raw = unb64(org.json.JSONTokener(quoted).nextValue() as String)
                val scalar = BigInteger(1, raw)
                val private = KeyFactory.getInstance("EC").generatePrivate(ECPrivateKeySpec(scalar, curve)) as ECPrivateKey
                val public = unb64(data.getString("pub"))
                val point = P256.mul(scalar, P256.G) ?: throw CryptoError("bad identity")
                if (!P256.encode(point).contentEquals(public)) throw CryptoError("identity mismatch")
                return Identity(private, public)
            }
        }
    }

    private fun ecdh(private: ECPrivateKey, public: ECPublicKey): ByteArray =
        KeyAgreement.getInstance("ECDH").apply { init(private); doPhase(public, true) }.generateSecret()

    /** ECIES: encrypt a 32-byte key for the holder of [recipientPublic]. */
    fun wrapKey(key: ByteArray, recipientPublic: String, aad: String): JSONObject {
        val recipientBytes = unb64(recipientPublic)
        val recipient = decodePublic(recipientBytes)
        val pair = KeyPairGenerator.getInstance("EC").apply { initialize(ECGenParameterSpec("secp256r1"), random) }.generateKeyPair()
        val ephemeral = encodePublic(pair.public as ECPublicKey)
        val shared = ecdh(pair.private as ECPrivateKey, recipient)
        val wrapping = hkdf(shared, "linotes v2 wrap".toByteArray() + ephemeral + recipientBytes)
        val nonce = randomBytes(12)
        val cipher = gcm(Cipher.ENCRYPT_MODE, wrapping, nonce, aad).doFinal(key)
        return JSONObject().put("e", b64(ephemeral)).put("n", b64(nonce)).put("c", b64(cipher))
    }

    fun unwrapKey(identity: Identity, wrapped: JSONObject, aad: String): ByteArray = try {
        val ephemeral = unb64(wrapped.getString("e"))
        val shared = ecdh(identity.private, decodePublic(ephemeral))
        val wrapping = hkdf(shared, "linotes v2 wrap".toByteArray() + ephemeral + identity.publicBytes)
        gcm(Cipher.DECRYPT_MODE, wrapping, unb64(wrapped.getString("n")), aad).doFinal(unb64(wrapped.getString("c")))
    } catch (error: Exception) {
        throw CryptoError("unwrap failed")
    }

    fun fingerprint(public: String): String =
        sha256("linotes v2 fingerprint".toByteArray() + unb64(public)).joinToString("") { "%02x".format(it) }

    fun safetyNumber(publicA: String, publicB: String): String {
        val (first, second) = listOf(unb64(publicA), unb64(publicB)).sortedWith { a, b -> compareBytes(a, b) }
        val digest = sha256("linotes v2 safety".toByteArray() + first + second)
        val number = BigInteger(1, digest.copyOfRange(0, 12)).mod(BigInteger.TEN.pow(20))
        val text = number.toString().padStart(20, '0')
        return text.chunked(5).joinToString(" ")
    }

    private fun compareBytes(a: ByteArray, b: ByteArray): Int {
        for (index in 0 until minOf(a.size, b.size)) {
            val difference = (a[index].toInt() and 0xff) - (b[index].toInt() and 0xff)
            if (difference != 0) return difference
        }
        return a.size - b.size
    }

    // --- key file --------------------------------------------------------

    const val KEYFILE_ITERATIONS = 600_000

    private fun pbkdf2(passphrase: String, salt: ByteArray, iterations: Int): ByteArray =
        SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            .generateSecret(PBEKeySpec(passphrase.toCharArray(), salt, iterations, 256)).encoded

    fun exportKeyfile(server: String, username: String, account: Account, passphrase: String): JSONObject {
        val salt = randomBytes(16)
        val key = pbkdf2(passphrase, salt, KEYFILE_ITERATIONS)
        val content = JSONObject().put("server", server).put("username", username).put("secret", b64(account.secret))
        return JSONObject()
            .put("format", "linotes-key").put("version", 1).put("username", username)
            .put("kdf", "pbkdf2-sha256").put("iterations", KEYFILE_ITERATIONS).put("salt", b64(salt))
            .put("box", seal(key, content, "linotes-key"))
    }

    data class KeyfileContent(val server: String, val username: String, val account: Account)

    fun importKeyfile(data: JSONObject, passphrase: String): KeyfileContent {
        if (data.optString("format") != "linotes-key") throw CryptoError("not a LiNotes key file")
        val key = pbkdf2(passphrase, unb64(data.getString("salt")), data.optInt("iterations", KEYFILE_ITERATIONS))
        val content = open(key, data.getJSONObject("box"), "linotes-key")
        return KeyfileContent(content.getString("server"), content.getString("username"), Account(unb64(content.getString("secret"))))
    }

    // --- SPAKE2 (RFC 9382, P256-SHA256-HKDF-HMAC) ---------------------------

    object P256 {
        val P = BigInteger("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16)
        val A: BigInteger = P.subtract(BigInteger.valueOf(3))
        val B = BigInteger("5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B", 16)
        val N = BigInteger("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)
        val G = Pair(
            BigInteger("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16),
            BigInteger("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16),
        )

        fun add(p1: Pair<BigInteger, BigInteger>?, p2: Pair<BigInteger, BigInteger>?): Pair<BigInteger, BigInteger>? {
            if (p1 == null) return p2
            if (p2 == null) return p1
            val (x1, y1) = p1
            val (x2, y2) = p2
            if (x1 == x2 && (y1 + y2).mod(P) == BigInteger.ZERO) return null
            val slope = if (x1 == x2 && y1 == y2) {
                (BigInteger.valueOf(3) * x1 * x1 + A) * (BigInteger.valueOf(2) * y1).modInverse(P)
            } else {
                (y2 - y1) * (x2 - x1).mod(P).modInverse(P)
            }.mod(P)
            val x3 = (slope * slope - x1 - x2).mod(P)
            return Pair(x3, (slope * (x1 - x3) - y1).mod(P))
        }

        fun neg(point: Pair<BigInteger, BigInteger>?) = point?.let { Pair(it.first, it.second.negate().mod(P)) }

        fun mul(scalar: BigInteger, point: Pair<BigInteger, BigInteger>): Pair<BigInteger, BigInteger>? {
            var result: Pair<BigInteger, BigInteger>? = null
            var addend: Pair<BigInteger, BigInteger>? = point
            var k = scalar.mod(N)
            while (k.signum() > 0) {
                if (k.testBit(0)) result = add(result, addend)
                addend = add(addend, addend)
                k = k.shiftRight(1)
            }
            return result
        }

        fun encode(point: Pair<BigInteger, BigInteger>): ByteArray = byteArrayOf(4) + fixed(point.first) + fixed(point.second)

        fun decode(data: ByteArray): Pair<BigInteger, BigInteger> {
            val x: BigInteger
            var y: BigInteger
            if (data.size == 65 && data[0] == 4.toByte()) {
                x = BigInteger(1, data.copyOfRange(1, 33))
                y = BigInteger(1, data.copyOfRange(33, 65))
            } else if (data.size == 33 && (data[0] == 2.toByte() || data[0] == 3.toByte())) {
                x = BigInteger(1, data.copyOfRange(1, 33))
                y = (x.pow(3) + A * x + B).mod(P).modPow(P.add(BigInteger.ONE).shiftRight(2), P)
                if (y.testBit(0) != (data[0] == 3.toByte())) y = P - y
            } else throw CryptoError("bad point")
            if ((y * y - (x.pow(3) + A * x + B)).mod(P) != BigInteger.ZERO) throw CryptoError("point not on curve")
            return Pair(x, y)
        }

        val M by lazy { decode(hex("02886e2f97ace46e55ba9dd7242579f2993b64e16ef3dcab95afd497333d8fa12f")) }
        val SPAKE_N by lazy { decode(hex("03d8bbd6c639c62937b04d997f38c3770719c629d7014d49a24b4f98baa1292b49")) }
    }

    fun hex(text: String): ByteArray = ByteArray(text.length / 2) { text.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    fun toHex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it) }

    fun spakeW(code: String, context: String): BigInteger =
        BigInteger(1, sha256("linotes v2 spake2 ".toByteArray() + context.toByteArray() + "|".toByteArray() + code.toByteArray())).mod(P256.N)

    private fun lengthPrefixed(vararg parts: ByteArray): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        for (part in parts) {
            out.write(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putLong(part.size.toLong()).array())
            out.write(part)
        }
        return out.toByteArray()
    }

    data class SpakeResult(val ke: ByteArray, val confirmation: ByteArray, val expected: ByteArray)

    class Spake2(
        private val role: String,
        private val w: BigInteger,
        private val identityA: ByteArray = ByteArray(0),
        private val identityB: ByteArray = ByteArray(0),
        scalar: BigInteger? = null,
    ) {
        private val x: BigInteger = scalar ?: BigInteger(1, randomBytes(32)).mod(P256.N)
        val message: ByteArray = P256.encode(
            P256.add(P256.mul(x, P256.G), P256.mul(w, if (role == "A") P256.M else P256.SPAKE_N))!!,
        )

        fun finish(peerMessage: ByteArray): SpakeResult {
            val peer = P256.decode(peerMessage)
            val unblind = P256.mul(w, if (role == "A") P256.SPAKE_N else P256.M)
            val shared = P256.add(peer, P256.neg(unblind))?.let { P256.mul(x, it) } ?: throw CryptoError("bad SPAKE2 message")
            val (pA, pB) = if (role == "A") message to peerMessage else peerMessage to message
            val transcript = lengthPrefixed(identityA, identityB, pA, pB, P256.encode(shared), fixed(w))
            val digest = sha256(transcript)
            val ke = digest.copyOfRange(0, 16)
            val ka = digest.copyOfRange(16, 32)
            val confirmation = hkdf(ka, "ConfirmationKeys".toByteArray(), 32)
            val cA = hmac(confirmation.copyOfRange(0, 16), transcript)
            val cB = hmac(confirmation.copyOfRange(16, 32), transcript)
            return if (role == "A") SpakeResult(ke, cA, cB) else SpakeResult(ke, cB, cA)
        }
    }

    fun newCode(): String = "%06d".format(BigInteger(1, randomBytes(4)).mod(BigInteger.valueOf(1_000_000)).toInt())
}
