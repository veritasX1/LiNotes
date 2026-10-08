package io.github.veritasx1.linotes.i18n

import android.content.Context
import org.json.JSONObject
import java.util.Locale

/**
 * Translations, the twin of linux/linotes/i18n.py. German is the source language: the code keeps
 * its German texts and passes them through [tr]; assets/locale/<lang>.json (copied at build time
 * from linux/linotes/locale, the one catalogue of both apps) maps each German text to its
 * translation. A missing entry shows German, so nothing breaks.
 *
 * Placeholders use {name}: tr("„{name}“ entfernt", "name" to title). Plurals follow the Unicode
 * CLDR categories (one, few, many, other) so Russian or Arabic can be added later.
 */
object I18n {
    val LANGUAGES = linkedMapOf("de" to "Deutsch", "en" to "English", "fr" to "Français")
    private val RTL = setOf("ar", "he", "fa", "ur")

    private var context: Context? = null
    private var loaded: String? = null
    private var catalog: JSONObject = JSONObject()

    fun init(context: Context) {
        this.context = context.applicationContext
    }

    private val prefs get() = context?.getSharedPreferences("ui", Context.MODE_PRIVATE)

    /** The language chosen in the app, or null for "like the system". */
    var chosen: String?
        get() = prefs?.getString("language", null)?.takeIf { it in LANGUAGES }
        set(value) { prefs?.edit()?.putString("language", value)?.apply() }

    fun systemLanguage(): String {
        val code = Locale.getDefault().language
        // A language we do not have yet: English is understood more widely than German.
        return if (code in LANGUAGES) code else "en"
    }

    /** Tests pin the language (gradle: systemProperty "linotes.language"). */
    private val pinned: String? = System.getProperty("linotes.language")?.takeIf { it in LANGUAGES }

    fun language(): String = pinned ?: if (context == null) "de" else chosen ?: systemLanguage()

    fun isRtl() = language() in RTL

    internal fun entries(): JSONObject {
        val language = language()
        if (language != loaded) {
            loaded = language
            catalog = if (language == "de") JSONObject() else try {
                context!!.assets.open("locale/$language.json").use { JSONObject(it.readBytes().decodeToString()) }
            } catch (error: Exception) {
                JSONObject()
            }
        }
        return catalog
    }

    /** For tests: use this catalogue instead of the asset. */
    internal fun use(language: String, entries: JSONObject) {
        loaded = language
        catalog = entries
    }

    fun pluralCategory(n: Long, language: String = language()): String {
        val k = kotlin.math.abs(n)
        return when (language) {
            "fr" -> if (k < 2) "one" else "other"
            "ru" -> when {
                k % 10 == 1L && k % 100 != 11L -> "one"
                k % 10 in 2..4 && k % 100 !in 12..14 -> "few"
                else -> "many"
            }
            "ar" -> when {
                k == 0L -> "zero"
                k == 1L -> "one"
                k == 2L -> "two"
                k % 100 in 3..10 -> "few"
                k % 100 in 11..99 -> "many"
                else -> "other"
            }
            else -> if (k == 1L) "one" else "other"
        }
    }

    internal fun fill(text: String, values: Array<out Pair<String, Any?>>): String {
        if (values.isEmpty()) return text
        var out = text
        for ((name, value) in values) out = out.replace("{$name}", value.toString())
        return out
    }
}

/** Translate a German text; values fill {placeholders}. */
fun tr(text: String, vararg values: Pair<String, Any?>): String {
    // German is the source: no catalogue needed (also keeps plain JVM tests free of org.json).
    if (I18n.language() == "de") return I18n.fill(text, values)
    val entries = I18n.entries()
    val translated = when (val entry = entries.opt(text)) {
        is String -> entry
        is JSONObject -> entry.optString("other", text)
        else -> text
    }
    return I18n.fill(translated, values)
}

/** Plural: German singular/plural as source ({n} is the count), translations by CLDR category. */
fun trn(singular: String, plural: String, n: Number, vararg values: Pair<String, Any?>): String {
    val count = n.toLong()
    if (I18n.language() == "de") return I18n.fill(if (count == 1L) singular else plural, arrayOf("n" to n, *values))
    val entries = I18n.entries()
    val entry = entries.opt(plural) ?: entries.opt(singular)
    val german = if (count == 1L) singular else plural
    val text = when (entry) {
        is JSONObject -> entry.optString(I18n.pluralCategory(count)).ifEmpty { entry.optString("other", german) }
        is String -> entry
        else -> german
    }
    return I18n.fill(text, arrayOf("n" to n, *values))
}
