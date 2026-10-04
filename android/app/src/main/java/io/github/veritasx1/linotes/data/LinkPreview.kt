package io.github.veritasx1.linotes.data

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

/** Link previews like Apple's: a web address alone on a line becomes a card with title, picture and
 *  domain. Privacy as in Signal: only the device that inserts the link fetches the page, the preview
 *  is stored encrypted in the note, other devices fetch nothing. Off unless switched on in the
 *  settings. The same rules as Ubuntu's linkpreview.py (LinkPreviewTest has its cases). */
object LinkPreview {
    private val LONE_URL = Regex("^\\s*(https?://[^\\s<>\"']+)\\s*$")
    private val META = Regex("<meta\\b[^>]*>", RegexOption.IGNORE_CASE)
    private val ATTRIBUTE = Regex("([a-zA-Z:_-]+)\\s*=\\s*(\"([^\"]*)\"|'([^']*)'|([^\\s\"'>]+))")
    private val TITLE = Regex("<title[^>]*>(.*?)</title>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
    private const val PAGE_LIMIT = 512 * 1024
    private const val IMAGE_LIMIT = 3 * 1024 * 1024
    const val IMAGE_SIZE = 600
    private const val TIMEOUT = 8000
    private const val AGENT = "Mozilla/5.0 (Linux; Android) LiNotes-Linkvorschau"

    data class Found(val title: String, val description: String, val image: String, val site: String, val picture: ByteArray? = null)

    /** The web address if the line holds nothing else (http/https only). */
    fun loneUrl(text: String?): String? = text?.let { LONE_URL.find(it)?.groupValues?.get(1) }

    fun domain(url: String): String =
        (runCatching { URI(url).host }.getOrNull() ?: "").lowercase().removePrefix("www.")

    private fun clean(text: String) = text.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")

    private fun unescape(text: String) =
        android.text.Html.fromHtml(text, android.text.Html.FROM_HTML_MODE_LEGACY).toString()

    fun parse(page: String, url: String): Found {
        val meta = mutableMapOf<String, String>()
        for (tag in META.findAll(page)) {
            val attrs = ATTRIBUTE.findAll(tag.value).associate { m ->
                m.groupValues[1].lowercase() to (m.groups[3]?.value ?: m.groups[4]?.value ?: m.groups[5]?.value ?: "")
            }
            val key = (attrs["property"] ?: attrs["name"] ?: "").lowercase()
            val content = attrs["content"]?.trim().orEmpty()
            if (key.isNotEmpty() && content.isNotEmpty() && key !in meta) meta[key] = content
        }
        fun first(vararg keys: String) = keys.firstNotNullOfOrNull { meta[it] }?.let { unescape(it).trim() }.orEmpty()
        val title = first("og:title", "twitter:title").ifEmpty { TITLE.find(page)?.groupValues?.get(1)?.let { clean(unescape(it)) }.orEmpty() }
        val image = first("og:image", "og:image:url", "twitter:image", "twitter:image:src")
        return Found(
            title = clean(title).take(200),
            description = clean(first("og:description", "twitter:description", "description")).take(300),
            image = if (image.isNotEmpty()) runCatching { URL(URL(url), image).toString() }.getOrDefault("") else "",
            site = first("og:site_name").ifEmpty { domain(url) },
        )
    }

    private fun get(url: String, limit: Int, accept: String): Pair<ByteArray, String> {
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = TIMEOUT
            connection.readTimeout = TIMEOUT
            connection.setRequestProperty("User-Agent", AGENT)
            connection.setRequestProperty("Accept", accept)
            if (connection.url.protocol !in setOf("http", "https")) throw IllegalArgumentException("kein Web-Link")
            val type = connection.contentType.orEmpty()
            val buffer = ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val chunk = ByteArray(16 * 1024)
                while (buffer.size() < limit) {
                    val read = input.read(chunk, 0, minOf(chunk.size, limit - buffer.size()))
                    if (read < 0) break
                    buffer.write(chunk, 0, read)
                }
            }
            return buffer.toByteArray() to type
        } finally {
            connection.disconnect()
        }
    }

    /** Fetch a page (only its beginning) and its picture. Blocking – run in the background. */
    fun fetch(url: String): Found {
        if (loneUrl(url) == null) throw IllegalArgumentException("kein Web-Link")
        val (body, type) = get(url, PAGE_LIMIT, "text/html,application/xhtml+xml")
        if (type.isNotEmpty() && "html" !in type.lowercase()) throw IllegalArgumentException("keine Webseite")
        val charset = Regex("charset=([\\w-]+)", RegexOption.IGNORE_CASE).find(type)?.groupValues?.get(1) ?: "UTF-8"
        val found = parse(String(body, runCatching { charset(charset) }.getOrDefault(Charsets.UTF_8)), url)
        val picture = if (found.image.isEmpty()) null else runCatching {
            val (data, imageType) = get(found.image, IMAGE_LIMIT, "image/*")
            if (imageType.startsWith("image/")) shrink(data) else null
        }.getOrNull()
        return found.copy(picture = picture)
    }

    /** The picture at most IMAGE_SIZE px on its longest side, as JPEG (PNG with transparency). */
    fun shrink(data: ByteArray): ByteArray? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(data, 0, data.size, bounds)
        if (bounds.outWidth <= 0) return null
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= IMAGE_SIZE) sample *= 2
        val decoded = BitmapFactory.decodeByteArray(data, 0, data.size, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return null
        val scale = minOf(1f, IMAGE_SIZE.toFloat() / maxOf(decoded.width, decoded.height))
        val bitmap = if (scale < 1f) Bitmap.createScaledBitmap(decoded, maxOf(1, (decoded.width * scale).toInt()), maxOf(1, (decoded.height * scale).toInt()), true) else decoded
        val out = ByteArrayOutputStream()
        bitmap.compress(if (bitmap.hasAlpha()) Bitmap.CompressFormat.PNG else Bitmap.CompressFormat.JPEG, 85, out)
        return out.toByteArray()
    }

    /** The note block. "x" keeps the address, so older LiNotes versions show it as a plain line. */
    fun block(url: String, found: Found, fileRef: String? = null): JSONObject {
        val block = JSONObject().put("t", "link").put("x", url).put("u", url)
            .put("n", found.title.ifEmpty { domain(url) }).put("dm", found.site.ifEmpty { domain(url) })
        if (found.description.isNotEmpty()) block.put("ds", found.description)
        if (fileRef != null) block.put("f", fileRef)
        return block
    }
}
