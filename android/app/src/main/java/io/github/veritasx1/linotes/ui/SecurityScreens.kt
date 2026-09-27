package io.github.veritasx1.linotes.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import io.github.veritasx1.linotes.R
import io.github.veritasx1.linotes.data.Api
import io.github.veritasx1.linotes.data.ApiException
import io.github.veritasx1.linotes.data.E2E
import io.github.veritasx1.linotes.data.OfflineException
import io.github.veritasx1.linotes.data.Pairing
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.data.SyncObject
import io.github.veritasx1.linotes.data.User
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

// ================================================================
// SMALL HELPERS
// ================================================================

fun errorText(error: Throwable): String = when {
    error is OfflineException -> "Der Server ist nicht erreichbar. Prüfe die Internetverbindung."
    error is Pairing.PairingError -> error.message ?: "Abgebrochen"
    error is ApiException -> when (error.code) {
        "wrong-credentials" -> "Anmeldung fehlgeschlagen – der Schlüssel passt nicht zu diesem Konto."
        "too-many-attempts" -> "Zu viele Versuche. Bitte warte ein paar Minuten."
        "invalid-invite" -> "Dieser Einladungscode ist ungültig oder wurde schon verwendet."
        "invalid-username" -> "Der Benutzername darf nur aus Kleinbuchstaben, Ziffern, Punkt, Minus und Unterstrich bestehen (2–32 Zeichen)."
        "username-taken" -> "Dieser Benutzername ist schon vergeben."
        else -> "Fehler: ${error.code}"
    }
    else -> "Fehler: ${error.message}"
}

/** "nur für dich" / "geteilt mit Anna" / "von Anna geteilt". */
fun shareLabel(sync: SyncEngine, obj: SyncObject): String {
    val share = obj.share ?: return "nur für dich"
    if (obj.owner != sync.userId) return "von ${sync.userName(obj.owner)} geteilt"
    val others = sync.shareMembers(share).filter { it != sync.userId }.map { sync.userName(it) }
    return if (others.isEmpty()) "geteilt" else "geteilt mit " + others.joinToString(", ")
}

fun otherUsers(sync: SyncEngine): List<User> = sync.users.filter { it.id != sync.userId }.sortedBy { it.name.lowercase() }

fun spacedCode(code: String) = if (code.length == 6) code.substring(0, 3) + " " + code.substring(3) else code

@Composable
fun CodeText(code: String) {
    Text(spacedCode(code), fontSize = 40.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold,
        color = palette.label, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp))
}

@Composable
fun QrImage(text: String, size: Int = 220) {
    val bitmap = remember(text) {
        val matrix = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, 0, 0,
            mapOf(EncodeHintType.MARGIN to 2, EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M))
        val image = Bitmap.createBitmap(matrix.width, matrix.height, Bitmap.Config.ARGB_8888)
        for (x in 0 until matrix.width) for (y in 0 until matrix.height) {
            image.setPixel(x, y, if (matrix[x, y]) android.graphics.Color.BLACK else android.graphics.Color.WHITE)
        }
        image.asImageBitmap()
    }
    Image(bitmap, "QR-Code", Modifier.size(size.dp).clip(RoundedCornerShape(12.dp)), filterQuality = FilterQuality.None)
}

@Composable
private fun Explanation(text: String) {
    Text(text, style = Type.subheadline, color = palette.secondary, textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 6.dp))
}

@Composable
private fun ErrorText(text: String?) {
    if (text != null) Text(text, style = Type.footnote, color = palette.red, textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth().padding(16.dp))
}

@Composable
private fun InsetGroup(content: @Composable () -> Unit) {
    Column(Modifier.padding(horizontal = 16.dp).fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(palette.surface)) { content() }
}

// ================================================================
// FIRST START: SERVER, NEW ACCOUNT, LINK, KEY FILE
// ================================================================

@Composable
fun OnboardingScreen(state: AppState, connecting: Boolean = false) {
    // connecting: LiNotes was used without a server so far; its notes move into the account.
    val colors = palette
    val scope = rememberCoroutineScope()
    var step by remember { mutableStateOf("server") }
    var server by remember { mutableStateOf("") }
    var serverInput by remember { mutableStateOf("") }
    var invite by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var passphrase by remember { mutableStateOf("") }
    var keyfile by remember { mutableStateOf<ByteArray?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var link by remember { mutableStateOf<Pairing.NewDeviceLink?>(null) }
    var cancelled by remember { mutableStateOf(false) }

    // This screen disappears at the end, which cancels its coroutines:
    // everything after that must already be done or run in the app's scope.
    suspend fun finish(url: String, response: JSONObject, account: E2E.Account, created: Boolean = false) {
        if (connecting) {
            try {
                withContext(Dispatchers.IO) { state.sync.connectLocal(url, response, account) }
            } catch (conflict: SyncEngine.VaultConflict) {
                throw Pairing.PairingError("Dieses Konto hat schon ein Notizen-Passwort. Entferne auf diesem Gerät zuerst die Sperre " +
                    "deiner gesperrten Notizen, dann verbinde erneut.")
            }
            state.lockAll()
            state.ensureDefaults()
            state.sync.start()
            state.askKeyfile = created
            state.toastLater("Mit dem Server verbunden – deine Notizen werden hochgeladen.")
            while (state.stack.size > 1) state.pop()
            return
        }
        state.askKeyfile = created
        state.sync.signIn(url, response, account)
        try { withContext(Dispatchers.IO) { state.sync.syncNow() } } catch (error: Exception) { }
        state.ensureDefaults()
        state.signedIn = true
        state.sync.start()
    }

    fun run(block: suspend () -> Unit) {
        busy = true
        error = null
        scope.launch {
            try { block() } catch (failure: Exception) { error = errorText(failure) } finally { busy = false }
        }
    }

    fun back() {
        if (step == "server") { state.pop(); return }
        cancelled = true
        link?.let { old -> state.sync.launch { old.close() } }
        link = null
        error = null
        step = if (step == "choice" || step == "local") "server" else "choice"
    }

    DisposableEffect(Unit) { onDispose { cancelled = true; link?.let { old -> state.sync.launch { old.close() } } } }
    if (step != "server" || connecting) androidx.activity.compose.BackHandler { back() }

    Column(
        Modifier.fillMaxSize().background(colors.background).statusBarsPadding().imePadding().verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.fillMaxWidth().height(44.dp)) {
            if (step != "server" || connecting) Box(Modifier.align(Alignment.CenterStart)) { TextButton("Zurück") { back() } }
        }
        Spacer(Modifier.height(16.dp))
        Box(Modifier.size(84.dp).clip(RoundedCornerShape(20.dp))) {
            Image(painterResource(R.drawable.ic_launcher_background), null, Modifier.size(84.dp))
            Image(painterResource(R.drawable.ic_launcher_foreground), null, Modifier.size(84.dp))
        }
        Spacer(Modifier.height(12.dp))
        when (step) {
            "server" -> {
                Text(if (connecting) "Mit Server verbinden" else "Willkommen bei LiNotes", style = Type.title1, color = colors.label)
                Explanation(if (connecting) "Deine Notizen werden danach verschlüsselt auf den Server übertragen und lassen sich mit anderen Geräten und Personen teilen."
                    else "Gib die Adresse deines LiNotes-Servers ein. Du bekommst sie von der Person, die den Server betreibt.")
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    InputRow(serverInput, { serverInput = it }, "z. B. notizen.example.org", divider = false,
                        keyboard = KeyboardType.Uri, imeAction = ImeAction.Go, onDone = {})
                }
                ErrorText(error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton(if (busy) "Einen Moment …" else "Weiter", enabled = !busy && serverInput.isNotBlank(),
                    modifier = Modifier.padding(horizontal = 16.dp)) {
                    var url = serverInput.trim().trimEnd('/')
                    if (!url.startsWith("http://") && !url.startsWith("https://")) url = "https://$url"
                    run {
                        val health = withContext(Dispatchers.IO) { Api(url).health() }
                        when {
                            health.optString("app") != "LiNotes" -> error = "Unter dieser Adresse läuft kein LiNotes-Server."
                            health.optInt("protocol") != 2 -> error = "Dieser Server ist zu alt für diese App."
                            else -> { server = url; step = "choice" }
                        }
                    }
                }
                if (!connecting) {
                    Spacer(Modifier.height(28.dp))
                    TextButton("Ohne Server nutzen") { error = null; step = "local" }
                    Text("Einfach als Notizen-App auf diesem Gerät. Einen Server kannst du später eintragen.",
                        style = Type.footnote, color = colors.secondary, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 40.dp))
                }
            }
            "local" -> {
                Text("Ohne Server", style = Type.title1, color = colors.label)
                Explanation("Deine Notizen, Listen und Aufgaben liegen verschlüsselt nur auf diesem Gerät. Geht es verloren, sind sie weg – " +
                    "verbinde LiNotes später mit einem Server (Einstellungen), um sie zu sichern und zu teilen.")
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    InputRow(name, { name = it }, "Dein Name (optional)", divider = false, imeAction = ImeAction.Done)
                }
                Spacer(Modifier.height(16.dp))
                PrimaryButton("Los geht’s", modifier = Modifier.padding(horizontal = 16.dp)) {
                    state.sync.startLocal(name.trim())
                    state.ensureDefaults()
                    state.signedIn = true
                }
            }
            "choice" -> {
                Text("Wie möchtest du starten?", style = Type.title1, color = colors.label, textAlign = TextAlign.Center)
                Explanation(server.removePrefix("https://"))
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    GroupRow("Neues Konto erstellen", Glyph.Plus, subtitle = "Du hast einen Einladungscode bekommen.") { step = "register" }
                    GroupRow("Mit anderem Gerät verbinden", Glyph.Person, subtitle = "Dein Konto gibt es schon, z. B. am Computer.") { cancelled = false; step = "link" }
                    GroupRow("Mit Schlüsseldatei wiederherstellen", Glyph.Lock, subtitle = "Aus deiner Notfall-Sicherung.", divider = false) { step = "keyfile" }
                }
            }
            "register" -> {
                Text("Neues Konto", style = Type.title1, color = colors.label)
                Explanation("Es gibt kein Passwort: Dein Konto ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt.")
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    InputRow(invite, { invite = it }, "Einladungscode")
                    InputRow(username, { username = it }, "Benutzername (klein, ohne Leerzeichen)")
                    InputRow(name, { name = it }, "Dein Name", divider = false, imeAction = ImeAction.Done)
                }
                ErrorText(error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton(if (busy) "Einen Moment …" else "Konto erstellen", enabled = !busy && invite.isNotBlank() && username.isNotBlank(),
                    modifier = Modifier.padding(horizontal = 16.dp)) {
                    run {
                        val url = server
                        val (account, response) = withContext(Dispatchers.IO) {
                            // Without a server so far: register the keys this device already has.
                            val account = if (connecting) state.sync.account!! else E2E.Account.create()
                            val identity = if (connecting) state.sync.identity!! else E2E.Identity.create()
                            account to Api(url).register(invite.trim(), username.trim().lowercase(), name.trim(), account.auth,
                                identity.exportSealed(account), state.sync.deviceName)
                        }
                        finish(url, response, account, created = true)
                    }
                }
            }
            "link" -> {
                Text("Mit anderem Gerät verbinden", style = Type.title1, color = colors.label, textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 24.dp))
                val current = link
                if (current == null) {
                    Explanation("Gib deinen Benutzernamen ein. Danach bestätigst du auf einem Gerät, auf dem du schon angemeldet bist.")
                    Spacer(Modifier.height(12.dp))
                    InsetGroup {
                        InputRow(username, { username = it }, "Benutzername", divider = false, imeAction = ImeAction.Done)
                    }
                    ErrorText(error)
                    Spacer(Modifier.height(16.dp))
                    PrimaryButton(if (busy) "Einen Moment …" else "Verbinden", enabled = !busy && username.isNotBlank(),
                        modifier = Modifier.padding(horizontal = 16.dp)) {
                        val url = server
                        val user = username.trim().lowercase()
                        cancelled = false
                        run {
                            val created = try {
                                withContext(Dispatchers.IO) { Pairing.NewDeviceLink(Api(url), user, state.sync.deviceName) }
                            } catch (failure: ApiException) {
                                throw if (failure.status == 404) Pairing.PairingError("Diesen Benutzernamen gibt es auf dem Server nicht.") else failure
                            }
                            link = created
                            scope.launch {
                                try {
                                    val secret = withContext(Dispatchers.IO) { created.await { cancelled } }
                                    val account = E2E.Account(secret)
                                    val response = withContext(Dispatchers.IO) { Api(url).login(user, account.auth, state.sync.deviceName) }
                                    finish(url, response, account)
                                } catch (failure: Exception) {
                                    if (!cancelled) {
                                        error = errorText(failure)
                                        link = null
                                    }
                                }
                            }
                        }
                    }
                } else {
                    Explanation("Auf deinem anderen Gerät erscheint „Neues Gerät verbinden?“. Gib dort diesen Code ein oder scanne den QR-Code:")
                    CodeText(current.code)
                    QrImage(current.qr)
                    Spacer(Modifier.height(12.dp))
                    Text("Warte auf Bestätigung …", style = Type.footnote, color = colors.secondary)
                    ErrorText(error)
                }
            }
            "keyfile" -> {
                Text("Wiederherstellen", style = Type.title1, color = colors.label)
                Explanation("Wähle deine Schlüsseldatei und gib die Passphrase ein, mit der du sie geschützt hast.")
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    GroupRow(if (keyfile == null) "Schlüsseldatei auswählen …" else "Schlüsseldatei ausgewählt ✓", Glyph.Folder) {
                        state.openDocument { content -> keyfile = content }
                    }
                    InputRow(passphrase, { passphrase = it }, "Passphrase", password = true, divider = false, imeAction = ImeAction.Done)
                }
                ErrorText(error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton(if (busy) "Einen Moment …" else "Wiederherstellen", enabled = !busy && keyfile != null && passphrase.isNotEmpty(),
                    modifier = Modifier.padding(horizontal = 16.dp)) {
                    val content = keyfile ?: return@PrimaryButton
                    run {
                        val restored = withContext(Dispatchers.Default) {
                            try {
                                E2E.importKeyfile(JSONObject(content.decodeToString()), passphrase)
                            } catch (failure: Exception) {
                                throw Pairing.PairingError("Falsche Passphrase oder keine gültige Schlüsseldatei.")
                            }
                        }
                        val response = withContext(Dispatchers.IO) {
                            Api(restored.server).login(restored.username, restored.account.auth, state.sync.deviceName)
                        }
                        finish(restored.server, response, restored.account)
                    }
                }
            }
        }
        Spacer(Modifier.height(40.dp))
    }
}

// ================================================================
// KEY FILE EXPORT
// ================================================================

@Composable
fun KeyfileDialog(state: AppState, firstTime: Boolean, onDone: () -> Unit) {
    val sync = state.sync
    AlertDialog(
        if (firstTime) "Schlüsseldatei sichern" else "Schlüsseldatei",
        (if (firstTime) "Dein Konto ist angelegt. " else "") +
            "Die Schlüsseldatei ist deine Notfall-Sicherung: Verlierst du alle Geräte, kommst du nur damit wieder an deine Notizen. " +
            "Schütze sie mit einer Passphrase und lege sie z. B. auf einen USB-Stick an einen sicheren Ort.",
        "Speichern …",
        fields = listOf(AlertField("Passphrase (min. 8 Zeichen)", password = true), AlertField("Passphrase wiederholen", password = true)),
        onDismiss = onDone,
    ) { values ->
        when {
            values[0].length < 8 -> state.toastLater("Die Passphrase muss mindestens 8 Zeichen haben.")
            values[0] != values[1] -> state.toastLater("Die Passphrasen stimmen nicht überein.")
            else -> {
                onDone()
                state.toastLater("Schlüsseldatei wird vorbereitet …")
                // The dialog is gone now: run in the app's scope, not the dialog's.
                sync.launch {
                    val account = sync.account ?: return@launch
                    val user = sync.user ?: return@launch
                    val data = E2E.exportKeyfile(sync.server, user.username, account, values[0])
                    withContext(Dispatchers.Main) {
                        state.saveDocument("LiNotes-${user.username}.linotes-key", data.toString(2).toByteArray()) { saved ->
                            state.toastLater(if (saved) "Schlüsseldatei gespeichert" else "Nicht gespeichert")
                        }
                    }
                }
            }
        }
    }
}

// ================================================================
// PEOPLE AND VERIFICATION
// ================================================================

@Composable
fun PeopleScreen(state: AppState, revision: Long) {
    val colors = palette
    val sync = state.sync
    val scope = rememberCoroutineScope()
    var inviteCode by remember { mutableStateOf<String?>(null) }
    val users = otherUsers(sync)
    LargeTitleScreen(title = "Personen", backLabel = "Einstellungen", onBack = { state.pop() }) {
        section("people", footer = "Bevor du etwas teilst, verifiziert ihr euch einmal gegenseitig – so kann niemand, auch nicht der Server, " +
            "einen falschen Schlüssel unterschieben. Tippe auf eine Person, um einen Code zu zeigen.") {
            if (users.isEmpty()) GroupRow("Noch niemand", Glyph.Person, subtitle = "Lade jemanden mit einem Einladungscode ein.", chevron = false, divider = false)
            users.forEachIndexed { index, user ->
                val status = when (Pairing.verifiedState(sync, user)) {
                    "verified" -> "✓ verifiziert"
                    "changed" -> "⚠ Schlüssel hat sich geändert – neu verifizieren"
                    else -> "noch nicht verifiziert"
                }
                GroupRow(user.name, Glyph.Person, subtitle = "@${user.username} · $status", divider = index < users.lastIndex) {
                    state.push(Route.Verify(user.id))
                }
            }
        }
        section("invite", footer = "Mit einem Einladungscode kann sich jemand einmalig ein eigenes Konto auf deinem Server anlegen.") {
            GroupRow("Jemanden einladen …", Glyph.Plus, divider = false) {
                scope.launch {
                    try {
                        inviteCode = withContext(Dispatchers.IO) { sync.api!!.invite() }
                    } catch (error: Exception) {
                        state.showToast(errorText(error))
                    }
                }
            }
        }
    }
    inviteCode?.let { code ->
        val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
        AlertDialog("Einladungscode", "Einmalig gültig:\n\n$code\n\nServer: ${sync.server}\n\nIn der App „Neues Konto erstellen“ wählen.", "Kopieren",
            onDismiss = { inviteCode = null }) {
            clipboard.setText(androidx.compose.ui.text.AnnotatedString(code))
            inviteCode = null
        }
    }
}

@Composable
fun VerifyScreen(state: AppState, userId: Int) {
    val colors = palette
    val sync = state.sync
    val user = sync.userById(userId)
    var show by remember { mutableStateOf<Pairing.VerifyShow?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var closed by remember { mutableStateOf(false) }
    val identity = sync.identity
    if (user == null || identity == null) {
        LaunchedEffect(Unit) { state.pop() }
        return
    }
    LaunchedEffect(userId) {
        try {
            val started = withContext(Dispatchers.IO) { Pairing.VerifyShow(sync.api!!, userId) }
            show = started
            val fingerprint = withContext(Dispatchers.IO) { started.await(identity.public, sync.users) { closed } }
            Pairing.markVerified(sync, userId, fingerprint)
            state.showToast("${user.name} ist jetzt verifiziert ✓")
            if (state.route == Route.Verify(userId)) state.pop()
        } catch (failure: Exception) {
            if (!closed) error = errorText(failure)
        }
    }
    DisposableEffect(Unit) { onDispose { closed = true } }
    Column(Modifier.fillMaxSize().background(colors.background)) {
        NavBar(title = "Verifizieren", backLabel = "Personen", onBack = { state.pop() })
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("${user.name} verifizieren", style = Type.title1, color = colors.label, textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 24.dp))
            Explanation("Auf dem Gerät von ${user.name} erscheint gleich eine Anfrage. Dort diesen Code eintippen (oder vorlesen) oder den QR-Code scannen.")
            val current = show
            if (current != null) {
                CodeText(current.code)
                QrImage(current.qr, 200)
            } else if (error == null) {
                Text("Einen Moment …", style = Type.footnote, color = colors.secondary, modifier = Modifier.padding(24.dp))
            }
            ErrorText(error)
            Spacer(Modifier.height(16.dp))
            Text("Sicherheitsnummer zum Vergleichen:", style = Type.footnote, color = colors.secondary)
            Text(E2E.safetyNumber(identity.public, user.identity).chunked(5).joinToString(" "), style = Type.footnote,
                fontFamily = FontFamily.Monospace, color = colors.secondary)
            Spacer(Modifier.height(32.dp))
        }
    }
}

// ================================================================
// INCOMING REQUESTS: NEW DEVICE / SOMEONE VERIFIES ME
// ================================================================

@Composable
fun IncomingRequests(state: AppState) {
    val request = state.incoming.firstOrNull() ?: return
    val sync = state.sync
    val channel = request.optString("channel")
    val purpose = request.optString("purpose")
    val other = sync.userById(request.optInt("from"))
    fun dismiss() { state.incoming.remove(request) }

    fun answer(code: String) {
        dismiss()
        // The dialog leaves the composition now: work in the app's scope.
        sync.launch {
            val message = try {
                if (purpose == "link") {
                    Pairing.approveLink(sync.api!!, channel, code, sync.account!!)
                    "Neues Gerät verbunden"
                } else if (other != null) {
                    val fingerprint = Pairing.verifyEnter(sync.api!!, channel, code, other.id, sync.identity!!.public, sync.users)
                    withContext(Dispatchers.Main) { Pairing.markVerified(sync, other.id, fingerprint) }
                    "${other.name} ist jetzt verifiziert ✓"
                } else null
            } catch (failure: Exception) {
                errorText(failure)
            }
            message?.let { state.toastLater(it) }
        }
    }

    fun scan() {
        state.scanQr { text ->
            try {
                val scanned = Pairing.parseQr(text)
                if (scanned.channel != channel || scanned.purpose != purpose) state.toastLater("Dieser QR-Code gehört zu einer anderen Anfrage.")
                else answer(scanned.code)
            } catch (failure: Exception) {
                state.toastLater("Das ist kein LiNotes-Code.")
            }
        }
    }

    if (purpose == "link") {
        CodeDialog(
            "Neues Gerät verbinden?",
            "„${request.optString("note").ifEmpty { "Ein neues Gerät" }}“ möchte sich mit deinem Konto verbinden. " +
                "Gib den 6-stelligen Code ein, der dort angezeigt wird, oder scanne den QR-Code. Warst du das nicht selbst, tippe auf „Ablehnen“.",
            confirm = "Verbinden", cancel = "Ablehnen",
            onScan = { scan() },
            onCancel = {
                dismiss()
                sync.launch { try { sync.api?.relayClose(channel) } catch (error: Exception) { } }
            },
            onConfirm = { answer(it) },
        )
    } else if (other != null) {
        CodeDialog(
            "${other.name} möchte euch verifizieren",
            "Gib den Code ein, den ${other.name} dir zeigt oder vorliest – oder scanne den QR-Code.",
            confirm = "Bestätigen", cancel = "Abbrechen",
            onScan = { scan() }, onCancel = { dismiss() }, onConfirm = { answer(it) },
        )
    } else {
        LaunchedEffect(request) { dismiss() }
    }
}

@Composable
fun CodeDialog(title: String, message: String, confirm: String, cancel: String, onScan: () -> Unit, onCancel: () -> Unit, onConfirm: (String) -> Unit) {
    val colors = palette
    var code by remember { mutableStateOf("") }
    val digits = code.filter { it.isDigit() }
    Dialog(onDismissRequest = {}) {
        Column(
            Modifier.width(300.dp).clip(RoundedCornerShape(14.dp)).background(if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2)),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(title, style = Type.headline, color = colors.label, textAlign = TextAlign.Center)
                Spacer(Modifier.height(4.dp))
                Text(message, style = Type.footnote, color = colors.label, textAlign = TextAlign.Center)
                Spacer(Modifier.height(12.dp))
                Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(colors.surface).padding(10.dp), contentAlignment = Alignment.Center) {
                    if (code.isEmpty()) Text("123 456", fontSize = 26.sp, fontFamily = FontFamily.Monospace, color = colors.tertiary)
                    BasicTextField(
                        code, { value -> if (value.count { it.isDigit() } <= 6) code = value }, singleLine = true,
                        textStyle = Type.body.copy(fontSize = 26.sp, fontFamily = FontFamily.Monospace, color = colors.label, textAlign = TextAlign.Center),
                        cursorBrush = SolidColor(colors.accent),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done),
                        keyboardActions = androidx.compose.foundation.text.KeyboardActions(onDone = {
                            val entered = code.filter { it.isDigit() }
                            if (entered.length == 6) onConfirm(entered)
                        }),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                Spacer(Modifier.height(4.dp))
                TextButton("QR-Code scannen …") { onScan() }
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().height(46.dp)) {
                Box(Modifier.weight(1f).fillMaxSize().clickable(onClick = onCancel), contentAlignment = Alignment.Center) {
                    Text(cancel, style = Type.body, color = colors.accentText)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(Modifier.weight(1f).fillMaxSize().clickable(enabled = digits.length == 6) { onConfirm(digits) }, contentAlignment = Alignment.Center) {
                    Text(confirm, style = Type.headline, color = if (digits.length == 6) colors.accentText else colors.tertiary)
                }
            }
        }
    }
}

// ================================================================
// SHARING
// ================================================================

@Composable
fun ShareScreen(state: AppState, objectId: String, revision: Long) {
    val colors = palette
    val sync = state.sync
    val obj = remember(revision, objectId) { sync.get(objectId) }
    if (obj == null) {
        LaunchedEffect(Unit) { state.pop() }
        return
    }
    if (sync.isLocal) {
        LargeTitleScreen(title = "Teilen", backLabel = "Zurück", onBack = { state.pop() }) {
            section("local", footer = "Zum Teilen brauchst du einen LiNotes-Server. Deine Notizen werden dabei Ende-zu-Ende verschlüsselt übertragen.") {
                GroupRow("Mit Server verbinden …", Glyph.Cloud, divider = false) { state.pop(); state.push(Route.Connect) }
            }
        }
        return
    }
    val owner = obj.owner == sync.userId
    val initial = remember(objectId) { sync.shareMembers(obj.share).filter { it != sync.userId }.toSet() }
    val chosen = remember(objectId) { mutableStateListOf<Int>().apply { addAll(initial) } }
    var busy by remember { mutableStateOf(false) }
    val kind = mapOf("folder" to "Ordner", "note" to "Notiz", "list" to "Liste", "board" to "Board")[obj.kind] ?: "Objekt"
    val name = if (obj.kind == "note") io.github.veritasx1.linotes.data.Model.title(obj) else obj.data.optString("name")
    val users = otherUsers(sync)
    val footer = if (!owner) "Geteilt von ${sync.userName(obj.owner)}. Nur wer es erstellt hat, kann die Freigabe ändern."
    else "Wähle, wer mitlesen und mitbearbeiten darf." + (if (obj.kind == "folder") " Alle Notizen in diesem Ordner werden mitgeteilt." else "") +
        " Alles bleibt Ende-zu-Ende verschlüsselt."

    LargeTitleScreen(title = "$kind teilen", subtitle = name, backLabel = "Zurück", onBack = { state.pop() }) {
        section("people", footer = footer) {
            if (users.isEmpty()) GroupRow("Noch niemand zum Teilen da", Glyph.Person, subtitle = "Lade jemanden in den Einstellungen ein.", chevron = false, divider = false)
            users.forEachIndexed { index, user ->
                val verified = Pairing.verifiedState(sync, user) == "verified"
                if (verified) {
                    val selected = user.id in chosen
                    GroupRow(user.name, subtitle = "✓ verifiziert", chevron = false, divider = index < users.lastIndex,
                        trailing = { CheckCircleIcon(selected, colors.accent, colors.tertiary) },
                        onClick = if (owner) ({ if (selected) chosen.remove(user.id) else chosen.add(user.id) }) else null)
                } else {
                    GroupRow(user.name, subtitle = "Erst verifizieren, dann teilen", detail = "Verifizieren", divider = index < users.lastIndex) {
                        state.push(Route.Verify(user.id))
                    }
                }
            }
        }
        if (owner) item("apply") {
            Spacer(Modifier.height(20.dp))
            PrimaryButton(if (busy) "Wird verschlüsselt …" else "Übernehmen", enabled = !busy && chosen.toSet() != initial,
                modifier = Modifier.padding(horizontal = 16.dp)) {
                val members = chosen.toList()
                if (obj.kind == "note" && obj.data.has("enc") && members.isNotEmpty()) {
                    state.toastLater("Gesperrte Notizen können nicht geteilt werden.")
                    return@PrimaryButton
                }
                busy = true
                sync.launch {
                    val message = try {
                        sync.setSharing(objectId, members)
                        if (members.isEmpty()) "Nicht mehr geteilt" else "Geteilt"
                    } catch (error: Exception) {
                        "Teilen fehlgeschlagen: ${error.message}"
                    }
                    withContext(Dispatchers.Main) {
                        busy = false
                        if (state.route == Route.Share(objectId)) state.pop()
                        state.showToast(message)
                    }
                }
            }
        }
    }
}

// ================================================================
// HELP
// ================================================================

private val HELP = listOf(
    "Erste Schritte" to listOf(
        "Ohne Server" to "Beim ersten Start „Ohne Server nutzen“ wählen: LiNotes ist dann einfach eine Notizen-App, alles liegt " +
            "verschlüsselt nur auf diesem Gerät. Später unter Einstellungen → „Mit Server verbinden …“ einen Server eintragen – " +
            "deine Notizen werden dann hochgeladen und lassen sich teilen und auf anderen Geräten nutzen.",
        "Konto anlegen" to "Beim ersten Start gibst du die Adresse deines LiNotes-Servers ein und wählst „Neues Konto erstellen“. " +
            "Dafür brauchst du einen Einladungscode von der Person, die den Server betreibt. Ein Passwort gibt es nicht – " +
            "dein Konto ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt.",
        "Schlüsseldatei sichern" to "Speichere direkt danach die Schlüsseldatei (Einstellungen → „Schlüsseldatei sichern“) " +
            "und lege sie z. B. auf einem USB-Stick an einen sicheren Ort. Ohne Gerät und ohne Schlüsseldatei kann niemand " +
            "– auch nicht der Server-Betreiber – deine Notizen wiederherstellen.",
        "Weiteres Gerät" to "Auf dem neuen Gerät „Mit anderem Gerät verbinden“ wählen und deinen Benutzernamen eingeben. " +
            "Auf einem Gerät, auf dem du schon angemeldet bist, erscheint dann eine Anfrage: dort den 6-stelligen Code " +
            "eintippen oder den QR-Code scannen.",
    ),
    "Notizen" to listOf(
        "Formatieren" to "Über „Aa“ wählst du Titel, Überschrift, Unterüberschrift, Text, Monospace, Listen oder Zitat.",
        "Checklisten" to "Kreis antippen, um einen Punkt abzuhaken. Eine leere Zeile beendet die Liste. Über „Mehr“ kannst du " +
            "abgehakte Punkte automatisch nach unten sortieren lassen.",
        "Tags" to "Schreibe #Wort in eine Notiz – der Tag erscheint in der Ordnerübersicht zum Filtern.",
        "Gesperrte Notizen" to "Über „Mehr“ → „Notiz sperren“ schützt du eine Notiz mit deinem Notizen-Passwort. In den " +
            "Einstellungen kannst du das Entsperren mit Fingerabdruck, PIN oder Muster einschalten. Gesperrte Notizen " +
            "sperren sich nach 10 Minuten ohne Benutzung wieder. Geteilte Notizen können nicht gesperrt werden.",
        "Auf dem Handy behalten" to "Notizen liegen auf deinem Handy und verschlüsselt auf dem Server. Wie lange der Inhalt " +
            "nach der letzten Benutzung auf dem Handy bleibt, stellst du pro Notiz (Mehr → „Auf dem Gerät behalten“) oder " +
            "für alle in den Einstellungen ein. Danach wird die Notiz beim Öffnen vom Server geladen. Angeheftete Notizen, " +
            "Listen und Boards bleiben immer auf dem Gerät.",
        "Gelöschte Notizen" to "Gelöschte Notizen liegen 30 Tage in „Zuletzt gelöscht“ und lassen sich dort wiederherstellen.",
    ),
    "Teilen" to listOf(
        "Personen verifizieren" to "Bevor du etwas teilst, verifiziert ihr euch einmal: Einstellungen → „Personen“ → Person antippen. " +
            "Dein Gerät zeigt einen Code, die andere Person tippt ihn ein oder scannt den QR-Code. So kann niemand – auch " +
            "nicht der Server – euch einen falschen Schlüssel unterschieben.",
        "Etwas teilen" to "Ordner, Liste, Board oder Notiz lange gedrückt halten → „Teilen …“ und die Personen auswählen. " +
            "Wird ein Ordner geteilt, gilt das für alle Notizen darin. Entfernst du jemanden, wird neu verschlüsselt.",
    ),
    "Listen und Aufgaben" to listOf(
        "Einkaufslisten" to "Einträge unten eintippen – sie landen automatisch in der passenden Warengruppe. Abgehakt wird mit dem Kreis.",
        "Aufgaben-Board" to "Karte antippen für Fälligkeit, Zuständigkeit, Farbe und Notizen; lange drücken zum Verschieben.",
    ),
    "Datenschutz" to listOf(
        "Was der Server weiß" to "Alles – Notizen, Listen, Boards, Ordnernamen und Bilder – wird auf deinem Gerät verschlüsselt, " +
            "bevor es den Server erreicht. Der Server sieht nur, dass es Einträge gibt, wie groß sie sind und wann sie " +
            "geändert wurden – nicht, was darin steht.",
    ),
)

@Composable
fun HelpScreen(state: AppState) {
    val colors = palette
    var open by remember { mutableStateOf<String?>(null) }
    LargeTitleScreen(title = "Hilfe", backLabel = "Einstellungen", onBack = { state.pop() }) {
        HELP.forEach { (header, entries) ->
            section("help-$header", header = header) {
                entries.forEachIndexed { index, (title, text) ->
                    GroupRow(title, chevron = false, divider = index < entries.lastIndex && open != title,
                        detail = if (open == title) "−" else "+") { open = if (open == title) null else title }
                    if (open == title) {
                        Text(text, style = Type.subheadline, color = colors.secondary, modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp))
                        if (index < entries.lastIndex) HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
                    }
                }
            }
        }
    }
}
