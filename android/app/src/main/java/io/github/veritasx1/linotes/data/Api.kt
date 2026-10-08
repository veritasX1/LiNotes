package io.github.veritasx1.linotes.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

open class ApiException(val status: Int, val code: String) : Exception(code)
class OfflineException(message: String) : ApiException(0, "offline")

/** Minimal client for the LiNotes server (no extra libraries). */
class Api(val server: String, var token: String? = null) {

    private fun open(path: String, method: String, timeoutSeconds: Int): HttpURLConnection {
        val connection = URL(server.trimEnd('/') + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = timeoutSeconds * 1000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("User-Agent", "LiNotes-Android/1.0")
        token?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
        return connection
    }

    private fun read(connection: HttpURLConnection): ByteArray {
        val status = try {
            connection.responseCode
        } catch (error: IOException) {
            throw OfflineException(error.message ?: "offline")
        }
        if (status >= 400) {
            val code = try {
                JSONObject(connection.errorStream?.readBytes()?.decodeToString() ?: "{}").optString("error", "error")
            } catch (error: Exception) {
                "error"
            }
            throw ApiException(status, code)
        }
        return try {
            connection.inputStream.readBytes()
        } catch (error: IOException) {
            throw OfflineException(error.message ?: "offline")
        }
    }

    fun request(method: String, path: String, body: JSONObject? = null, timeoutSeconds: Int = 20): JSONObject {
        if (method == "DELETE") return requestNoBody(method, path, timeoutSeconds)
        val connection = open(path, method, timeoutSeconds)
        try {
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                try {
                    connection.outputStream.use { it.write(body.toString().toByteArray()) }
                } catch (error: IOException) {
                    throw OfflineException(error.message ?: "offline")
                }
            }
            val bytes = read(connection)
            return if (bytes.isEmpty()) JSONObject() else JSONObject(bytes.decodeToString())
        } finally {
            connection.disconnect()
        }
    }

    private fun requestNoBody(method: String, path: String, timeoutSeconds: Int): JSONObject {
        val connection = open(path, method, timeoutSeconds)
        try {
            val bytes = read(connection)
            return if (bytes.isEmpty()) JSONObject() else JSONObject(bytes.decodeToString())
        } finally {
            connection.disconnect()
        }
    }

    fun health() = request("GET", "/api/health", timeoutSeconds = 10)

    fun login(username: String, auth: String, device: String) = request(
        "POST", "/api/login", JSONObject().put("username", username).put("auth", auth).put("device", device),
    )

    fun register(invite: String, username: String, name: String, auth: String, identity: JSONObject, device: String) = request(
        "POST", "/api/register",
        JSONObject().put("invite", invite).put("username", username).put("name", name)
            .put("auth", auth).put("identity", identity).put("device", device),
    )

    fun logout() = request("POST", "/api/logout", JSONObject())

    fun me() = request("GET", "/api/me")

    fun invite(): String = request("POST", "/api/invites", JSONObject()).getString("code")

    fun linkRequest(username: String, device: String): String =
        request("POST", "/api/link/request", JSONObject().put("username", username).put("device", device)).getString("channel")

    fun verifyRequest(userId: Int): String =
        request("POST", "/api/verify/request", JSONObject().put("user", userId)).getString("channel")

    fun channels(): JSONArray = request("GET", "/api/channels").getJSONArray("channels")

    fun relayPost(channel: String, role: String, body: String) =
        request("POST", "/api/relay/$channel", JSONObject().put("role", role).put("body", body))

    fun relayGet(channel: String, after: Int, wait: Int): JSONArray =
        request("GET", "/api/relay/$channel?after=$after&wait=$wait", timeoutSeconds = wait + 20).getJSONArray("messages")

    fun relayClose(channel: String) = request("DELETE", "/api/relay/$channel")

    fun getObject(id: String) = request("GET", "/api/objects/$id")

    fun pull(since: Long, wait: Int = 0) = request("GET", "/api/sync?since=$since&wait=$wait", timeoutSeconds = wait + 20)

    fun push(changes: JSONArray): JSONArray =
        request("POST", "/api/sync", JSONObject().put("changes", changes), timeoutSeconds = 40).getJSONArray("results")

    /** [progress] gets (bytes sent, bytes total) while the body streams out. */
    fun upload(content: ByteArray, share: String?, progress: ((Long, Long) -> Unit)? = null): String {
        val boundary = "----linotes" + UUID.randomUUID().toString().replace("-", "")
        val connection = open("/api/files", "POST", 120)
        try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            val head = ByteArrayOutputStream()
            if (share != null) head.write("--$boundary\r\nContent-Disposition: form-data; name=\"share\"\r\n\r\n$share\r\n".toByteArray())
            head.write("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"datei\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
            val tail = "\r\n--$boundary--\r\n".toByteArray()
            val total = head.size().toLong() + content.size + tail.size
            // Streamed in pieces (not buffered whole), so the progress is the real one.
            connection.setFixedLengthStreamingMode(total)
            try {
                connection.outputStream.use { out ->
                    out.write(head.toByteArray())
                    var sent = head.size().toLong()
                    var offset = 0
                    while (offset < content.size) {
                        val count = minOf(64 * 1024, content.size - offset)
                        out.write(content, offset, count)
                        offset += count
                        sent += count
                        progress?.invoke(sent, total)
                    }
                    out.write(tail)
                    progress?.invoke(total, total)
                }
            } catch (error: IOException) {
                throw OfflineException(error.message ?: "offline")
            }
            return JSONObject(read(connection).decodeToString()).getString("id")
        } finally {
            connection.disconnect()
        }
    }

    fun download(fileId: String): ByteArray {
        val connection = open("/api/files/$fileId", "GET", 120)
        try {
            return read(connection)
        } finally {
            connection.disconnect()
        }
    }
}
