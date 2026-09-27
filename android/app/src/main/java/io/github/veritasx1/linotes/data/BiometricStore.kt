package io.github.veritasx1.linotes.data

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Keeps the notes-password key (vault key) on this phone, wrapped with an
 * Android Keystore key that only works for a few seconds after the user
 * proved themselves with fingerprint, face, PIN or pattern. The vault key
 * itself never leaves the phone in this form.
 */
class BiometricStore(context: Context) {
    private val prefs = context.getSharedPreferences("biometric", Context.MODE_PRIVATE)
    private val alias = "linotes-vault-unlock"

    val enabled: Boolean get() = prefs.contains("box")

    private fun keyStore() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    private fun secretKey(create: Boolean): SecretKey {
        keyStore().getKey(alias, null)?.let { return it as SecretKey }
        if (!create) throw IllegalStateException("no key")
        val builder = KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            builder.setUserAuthenticationParameters(15, KeyProperties.AUTH_BIOMETRIC_STRONG or KeyProperties.AUTH_DEVICE_CREDENTIAL)
        } else {
            @Suppress("DEPRECATION")
            builder.setUserAuthenticationValidityDurationSeconds(15)
        }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(builder.build())
            generateKey()
        }
    }

    /** Call right after a successful BiometricPrompt. */
    fun store(vaultKey: ByteArray, vaultId: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey(create = true))
        val sealed = cipher.doFinal(vaultKey)
        val encoder = Base64.getEncoder()
        prefs.edit().putString("box", encoder.encodeToString(sealed)).putString("iv", encoder.encodeToString(cipher.iv))
            .putString("vault", vaultId).apply()
    }

    /** Call right after a successful BiometricPrompt. */
    fun load(): ByteArray {
        val decoder = Base64.getDecoder()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, secretKey(create = false), GCMParameterSpec(128, decoder.decode(prefs.getString("iv", ""))))
        return cipher.doFinal(decoder.decode(prefs.getString("box", "")))
    }

    fun clear() {
        prefs.edit().clear().apply()
        try { keyStore().deleteEntry(alias) } catch (error: Exception) { }
    }
}
