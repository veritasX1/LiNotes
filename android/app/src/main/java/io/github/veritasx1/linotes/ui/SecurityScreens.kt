package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

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
    error is OfflineException -> tr("Der Server ist nicht erreichbar. Prüfe die Internetverbindung.")
    error is Pairing.PairingError -> error.message ?: tr("Abgebrochen")
    error is ApiException -> when (error.code) {
        "wrong-credentials" -> tr("Anmeldung fehlgeschlagen – der Schlüssel passt nicht zu diesem Konto.")
        "too-many-attempts" -> tr("Zu viele Versuche. Bitte warte ein paar Minuten.")
        "invalid-invite" -> tr("Dieser Einladungscode ist ungültig oder wurde schon verwendet.")
        "invalid-username" -> tr("Der Benutzername darf nur aus Kleinbuchstaben, Ziffern, Punkt, Minus und Unterstrich bestehen (2–32 Zeichen).")
        "username-taken" -> tr("Dieser Benutzername ist schon vergeben.")
        else -> tr("Fehler: {code}", "code" to error.code)
    }
    else -> tr("Fehler: {message}", "message" to error.message)
}

/** "nur für dich" / "geteilt mit Anna" / "von Anna geteilt". */
fun shareLabel(sync: SyncEngine, obj: SyncObject): String {
    val share = obj.share ?: return tr("nur für dich")
    if (obj.owner != sync.userId) return tr("von {person} geteilt", "person" to (sync.userName(obj.owner)))
    val others = sync.shareMembers(share).filter { it != sync.userId }.map { sync.userName(it) }
    return if (others.isEmpty()) "geteilt" else tr("geteilt mit ") + others.joinToString(", ")
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
    Image(bitmap, tr("QR-Code"), Modifier.size(size.dp).clip(RoundedCornerShape(12.dp)), filterQuality = FilterQuality.None)
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
                throw Pairing.PairingError(tr("Dieses Konto hat schon ein Notizen-Passwort. Entferne auf diesem Gerät zuerst die Sperre ") +
                    tr("deiner gesperrten Notizen, dann verbinde erneut."))
            }
            state.lockAll()
            state.ensureDefaults()
            state.sync.start()
            state.toastLater(tr("Mit dem Server verbunden – deine Notizen werden hochgeladen."))
            while (state.stack.size > 1) state.pop()
            return
        }
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
            if (step != "server" || connecting) Box(Modifier.align(Alignment.CenterStart)) { TextButton(tr("Zurück")) { back() } }
        }
        Spacer(Modifier.height(16.dp))
        Box(Modifier.size(84.dp).clip(RoundedCornerShape(20.dp))) {
            Image(painterResource(R.drawable.ic_launcher_background), null, Modifier.size(84.dp))
            Image(painterResource(R.drawable.ic_launcher_foreground), null, Modifier.size(84.dp))
        }
        Spacer(Modifier.height(12.dp))
        when (step) {
            "server" -> {
                Text(if (connecting) tr("Mit Server verbinden") else tr("Willkommen bei LiNotes"), style = Type.title1, color = colors.label)
                Explanation(if (connecting) tr("Deine Notizen werden danach verschlüsselt auf den Server übertragen und lassen sich mit anderen Geräten und Personen teilen.")
                    else tr("Gib die Adresse deines LiNotes-Servers ein. Du bekommst sie von der Person, die den Server betreibt."))
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    InputRow(serverInput, { serverInput = it }, tr("z. B. notizen.example.org"), divider = false,
                        keyboard = KeyboardType.Uri, imeAction = ImeAction.Go, onDone = {})
                }
                ErrorText(error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton(if (busy) tr("Einen Moment …") else tr("Weiter"), enabled = !busy && serverInput.isNotBlank(),
                    modifier = Modifier.padding(horizontal = 16.dp)) {
                    var url = serverInput.trim().trimEnd('/')
                    if (!url.startsWith("http://") && !url.startsWith("https://")) url = "https://$url"
                    run {
                        val health = withContext(Dispatchers.IO) { Api(url).health() }
                        when {
                            health.optString("app") != "LiNotes" -> error = tr("Unter dieser Adresse läuft kein LiNotes-Server.")
                            health.optInt("protocol") != 2 -> error = tr("Dieser Server ist zu alt für diese App.")
                            else -> { server = url; step = "choice" }
                        }
                    }
                }
                if (!connecting) {
                    Spacer(Modifier.height(28.dp))
                    TextButton(tr("Ohne Server nutzen")) { error = null; step = "local" }
                    Text(tr("Einfach als Notizen-App auf diesem Gerät. Einen Server kannst du später eintragen."),
                        style = Type.footnote, color = colors.secondary, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 40.dp))
                }
            }
            "local" -> {
                Text(tr("Ohne Server"), style = Type.title1, color = colors.label)
                Explanation(tr("Deine Notizen, Listen und Aufgaben liegen verschlüsselt nur auf diesem Gerät. Geht es verloren, sind sie weg – ") +
                    tr("verbinde LiNotes später mit einem Server (Einstellungen), um sie zu sichern und zu teilen."))
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    InputRow(name, { name = it }, tr("Dein Name (optional)"), divider = false, imeAction = ImeAction.Done)
                }
                Spacer(Modifier.height(16.dp))
                PrimaryButton(tr("Los geht’s"), modifier = Modifier.padding(horizontal = 16.dp)) {
                    state.sync.startLocal(name.trim())
                    state.ensureDefaults()
                    state.signedIn = true
                }
            }
            "choice" -> {
                Text(tr("Wie möchtest du starten?"), style = Type.title1, color = colors.label, textAlign = TextAlign.Center)
                Explanation(server.removePrefix("https://"))
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    GroupRow(tr("Neues Konto erstellen"), Glyph.Plus, subtitle = tr("Du hast einen Einladungscode bekommen.")) { step = "register" }
                    GroupRow(tr("Mit anderem Gerät verbinden"), Glyph.Person, subtitle = tr("Dein Konto gibt es schon, z. B. am Computer.")) { cancelled = false; step = "link" }
                    GroupRow(tr("Mit Schlüsseldatei wiederherstellen"), Glyph.Lock, subtitle = tr("Aus deiner Notfall-Sicherung."), divider = false) { step = "keyfile" }
                }
            }
            "register" -> {
                Text(tr("Neues Konto"), style = Type.title1, color = colors.label)
                Explanation(tr("Es gibt kein Passwort: Dein Konto ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt."))
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    InputRow(invite, { invite = it }, tr("Einladungscode"))
                    InputRow(username, { username = it }, tr("Benutzername (klein, ohne Leerzeichen)"))
                    InputRow(name, { name = it }, tr("Dein Name"), divider = false, imeAction = ImeAction.Done)
                }
                ErrorText(error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton(if (busy) tr("Einen Moment …") else tr("Konto erstellen"), enabled = !busy && invite.isNotBlank() && username.isNotBlank(),
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
                Text(tr("Mit anderem Gerät verbinden"), style = Type.title1, color = colors.label, textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 24.dp))
                val current = link
                if (current == null) {
                    Explanation(tr("Gib deinen Benutzernamen ein. Danach bestätigst du auf einem Gerät, auf dem du schon angemeldet bist."))
                    Spacer(Modifier.height(12.dp))
                    InsetGroup {
                        InputRow(username, { username = it }, tr("Benutzername"), divider = false, imeAction = ImeAction.Done)
                    }
                    ErrorText(error)
                    Spacer(Modifier.height(16.dp))
                    PrimaryButton(if (busy) tr("Einen Moment …") else tr("Verbinden"), enabled = !busy && username.isNotBlank(),
                        modifier = Modifier.padding(horizontal = 16.dp)) {
                        val url = server
                        val user = username.trim().lowercase()
                        cancelled = false
                        run {
                            val created = try {
                                withContext(Dispatchers.IO) { Pairing.NewDeviceLink(Api(url), user, state.sync.deviceName) }
                            } catch (failure: ApiException) {
                                throw if (failure.status == 404) Pairing.PairingError(tr("Diesen Benutzernamen gibt es auf dem Server nicht.")) else failure
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
                    Explanation(tr("Auf deinem anderen Gerät erscheint „Neues Gerät verbinden?“. Gib dort diesen Code ein oder scanne den QR-Code:"))
                    CodeText(current.code)
                    QrImage(current.qr)
                    Spacer(Modifier.height(12.dp))
                    Text(tr("Warte auf Bestätigung …"), style = Type.footnote, color = colors.secondary)
                    ErrorText(error)
                }
            }
            "keyfile" -> {
                Text(tr("Wiederherstellen"), style = Type.title1, color = colors.label)
                Explanation(tr("Wähle deine Schlüsseldatei und gib die Passphrase ein, mit der du sie geschützt hast."))
                Spacer(Modifier.height(12.dp))
                InsetGroup {
                    GroupRow(if (keyfile == null) tr("Schlüsseldatei auswählen …") else tr("Schlüsseldatei ausgewählt ✓"), Glyph.Folder) {
                        state.openDocument { content -> keyfile = content }
                    }
                    InputRow(passphrase, { passphrase = it }, tr("Passphrase"), password = true, divider = false, imeAction = ImeAction.Done)
                }
                ErrorText(error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton(if (busy) tr("Einen Moment …") else tr("Wiederherstellen"), enabled = !busy && keyfile != null && passphrase.isNotEmpty(),
                    modifier = Modifier.padding(horizontal = 16.dp)) {
                    val content = keyfile ?: return@PrimaryButton
                    run {
                        val restored = withContext(Dispatchers.Default) {
                            try {
                                E2E.importKeyfile(JSONObject(content.decodeToString()), passphrase)
                            } catch (failure: Exception) {
                                throw Pairing.PairingError(tr("Falsche Passphrase oder keine gültige Schlüsseldatei."))
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
fun KeyfileDialog(state: AppState, onDone: () -> Unit) {
    val sync = state.sync
    AlertDialog(
        tr("Schlüsseldatei sichern"),
        tr("Die Schlüsseldatei ist deine Notfall-Sicherung: Verlierst du alle Geräte, kommst du nur damit wieder an deine Notizen. ") +
            tr("Schütze sie mit einer Passphrase und lege sie z. B. auf einen USB-Stick an einen sicheren Ort."),
        tr("Speichern …"),
        fields = listOf(AlertField(tr("Passphrase (min. 8 Zeichen)"), password = true), AlertField(tr("Passphrase wiederholen"), password = true)),
        onDismiss = onDone,
    ) { values ->
        when {
            values[0].length < 8 -> state.toastLater(tr("Die Passphrase muss mindestens 8 Zeichen haben."))
            values[0] != values[1] -> state.toastLater(tr("Die Passphrasen stimmen nicht überein."))
            else -> {
                onDone()
                state.toastLater(tr("Schlüsseldatei wird vorbereitet …"))
                // The dialog is gone now: run in the app's scope, not the dialog's.
                sync.launch {
                    val account = sync.account ?: return@launch
                    val user = sync.user ?: return@launch
                    val data = E2E.exportKeyfile(sync.server, user.username, account, values[0])
                    withContext(Dispatchers.Main) {
                        state.saveDocument(tr("LiNotes-{username}.linotes-key", "username" to user.username), data.toString(2).toByteArray()) { saved ->
                            if (saved) sync.markKeyfileSaved()
                            state.toastLater(if (saved) tr("Schlüsseldatei gespeichert") else tr("Nicht gespeichert"))
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
    LargeTitleScreen(title = tr("Personen"), backLabel = tr("Einstellungen"), onBack = { state.pop() }) {
        section("people", footer = tr("Bevor du etwas teilst, verifiziert ihr euch einmal gegenseitig – so kann niemand, auch nicht der Server, ") +
            tr("einen falschen Schlüssel unterschieben. Tippe auf eine Person, um einen Code zu zeigen.")) {
            if (users.isEmpty()) GroupRow(tr("Noch niemand"), Glyph.Person, subtitle = tr("Lade jemanden mit einem Einladungscode ein."), chevron = false, divider = false)
            users.forEachIndexed { index, user ->
                val status = when (Pairing.verifiedState(sync, user)) {
                    "verified" -> tr("✓ verifiziert")
                    "changed" -> tr("⚠ Schlüssel hat sich geändert – neu verifizieren")
                    else -> tr("noch nicht verifiziert")
                }
                GroupRow(user.name, Glyph.Person, subtitle = "@${user.username} · $status", divider = index < users.lastIndex) {
                    state.push(Route.Verify(user.id))
                }
            }
        }
        section("invite", footer = tr("Mit einem Einladungscode kann sich jemand einmalig ein eigenes Konto auf deinem Server anlegen.")) {
            GroupRow(tr("Jemanden einladen …"), Glyph.Plus, divider = false) {
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
        AlertDialog(tr("Einladungscode"), tr("Einmalig gültig:\n\n{code}\n\nServer: {server}\n\nIn der App „Neues Konto erstellen“ wählen.", "code" to code, "server" to sync.server), tr("Kopieren"),
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
            state.showToast(tr("{name} ist jetzt verifiziert ✓", "name" to user.name))
            if (state.route == Route.Verify(userId)) state.pop()
        } catch (failure: Exception) {
            if (!closed) error = errorText(failure)
        }
    }
    DisposableEffect(Unit) { onDispose { closed = true } }
    Column(Modifier.fillMaxSize().background(colors.background)) {
        NavBar(title = tr("Verifizieren"), backLabel = tr("Personen"), onBack = { state.pop() })
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(tr("{name} verifizieren", "name" to user.name), style = Type.title1, color = colors.label, textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 24.dp))
            Explanation(tr("Auf dem Gerät von {name} erscheint gleich eine Anfrage. Dort diesen Code eintippen (oder vorlesen) oder den QR-Code scannen.", "name" to user.name))
            val current = show
            if (current != null) {
                CodeText(current.code)
                QrImage(current.qr, 200)
            } else if (error == null) {
                Text(tr("Einen Moment …"), style = Type.footnote, color = colors.secondary, modifier = Modifier.padding(24.dp))
            }
            ErrorText(error)
            Spacer(Modifier.height(16.dp))
            Text(tr("Sicherheitsnummer zum Vergleichen:"), style = Type.footnote, color = colors.secondary)
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
                    tr("Neues Gerät verbunden")
                } else if (other != null) {
                    val fingerprint = Pairing.verifyEnter(sync.api!!, channel, code, other.id, sync.identity!!.public, sync.users)
                    withContext(Dispatchers.Main) { Pairing.markVerified(sync, other.id, fingerprint) }
                    tr("{name} ist jetzt verifiziert ✓", "name" to other.name)
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
                if (scanned.channel != channel || scanned.purpose != purpose) state.toastLater(tr("Dieser QR-Code gehört zu einer anderen Anfrage."))
                else answer(scanned.code)
            } catch (failure: Exception) {
                state.toastLater(tr("Das ist kein LiNotes-Code."))
            }
        }
    }

    if (purpose == "link") {
        CodeDialog(
            tr("Neues Gerät verbinden?"),
            tr("„{name}“ möchte sich mit deinem Konto verbinden. ", "name" to (request.optString("note").ifEmpty { "Ein neues Gerät" })) +
                tr("Gib den 6-stelligen Code ein, der dort angezeigt wird, oder scanne den QR-Code. Warst du das nicht selbst, tippe auf „Ablehnen“."),
            confirm = tr("Verbinden"), cancel = tr("Ablehnen"),
            onScan = { scan() },
            onCancel = {
                dismiss()
                sync.launch { try { sync.api?.relayClose(channel) } catch (error: Exception) { } }
            },
            onConfirm = { answer(it) },
        )
    } else if (other != null) {
        CodeDialog(
            tr("{name} möchte euch verifizieren", "name" to other.name),
            tr("Gib den Code ein, den {name} dir zeigt oder vorliest – oder scanne den QR-Code.", "name" to other.name),
            confirm = tr("Bestätigen"), cancel = tr("Abbrechen"),
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
                TextButton(tr("QR-Code scannen …")) { onScan() }
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
        LargeTitleScreen(title = tr("Teilen"), backLabel = tr("Zurück"), onBack = { state.pop() }) {
            section("local", footer = tr("Zum Teilen brauchst du einen LiNotes-Server. Deine Notizen werden dabei Ende-zu-Ende verschlüsselt übertragen.")) {
                GroupRow(tr("Mit Server verbinden …"), Glyph.Cloud, divider = false) { state.pop(); state.push(Route.Connect) }
            }
        }
        return
    }
    val owner = obj.owner == sync.userId
    val initial = remember(objectId) { sync.shareMembers(obj.share).filter { it != sync.userId }.toSet() }
    val chosen = remember(objectId) { mutableStateListOf<Int>().apply { addAll(initial) } }
    var busy by remember { mutableStateOf(false) }
    val kind = mapOf("folder" to tr("Ordner"), "note" to tr("Notiz"), "list" to tr("Liste"), "board" to tr("Board"))[obj.kind] ?: tr("Objekt")
    val name = if (obj.kind == "note") io.github.veritasx1.linotes.data.Model.title(obj) else obj.data.optString("name")
    val users = otherUsers(sync)
    val footer = if (!owner) tr("Geteilt von {person}. Nur wer es erstellt hat, kann die Freigabe ändern.", "person" to (sync.userName(obj.owner)))
    else tr("Wähle, wer mitlesen und mitbearbeiten darf.") + (if (obj.kind == "folder") tr(" Alles in diesem Ordner wird mitgeteilt – Unterordner, Notizen, Listen und Boards.") else "") +
        tr(" Alles bleibt Ende-zu-Ende verschlüsselt.")

    LargeTitleScreen(title = tr("{kind} teilen", "kind" to kind), subtitle = name, backLabel = tr("Zurück"), onBack = { state.pop() }) {
        section("people", footer = footer) {
            if (users.isEmpty()) GroupRow(tr("Noch niemand zum Teilen da"), Glyph.Person, subtitle = tr("Lade jemanden in den Einstellungen ein."), chevron = false, divider = false)
            users.forEachIndexed { index, user ->
                val verified = Pairing.verifiedState(sync, user) == "verified"
                if (verified) {
                    val selected = user.id in chosen
                    GroupRow(user.name, subtitle = tr("✓ verifiziert"), chevron = false, divider = index < users.lastIndex,
                        trailing = { CheckCircleIcon(selected, colors.accent, colors.tertiary) },
                        onClick = if (owner) ({ if (selected) chosen.remove(user.id) else chosen.add(user.id) }) else null)
                } else {
                    GroupRow(user.name, subtitle = tr("Erst verifizieren, dann teilen"), detail = tr("Verifizieren"), divider = index < users.lastIndex) {
                        state.push(Route.Verify(user.id))
                    }
                }
            }
        }
        if (owner) item("apply") {
            Spacer(Modifier.height(20.dp))
            PrimaryButton(if (busy) tr("Wird verschlüsselt …") else tr("Übernehmen"), enabled = !busy && chosen.toSet() != initial,
                modifier = Modifier.padding(horizontal = 16.dp)) {
                val members = chosen.toList()
                if (obj.kind == "note" && obj.data.has("enc") && members.isNotEmpty()) {
                    state.toastLater(tr("Gesperrte Notizen können nicht geteilt werden."))
                    return@PrimaryButton
                }
                busy = true
                sync.launch {
                    val message = try {
                        sync.setSharing(objectId, members)
                        if (members.isEmpty()) tr("Nicht mehr geteilt") else tr("Geteilt")
                    } catch (error: Exception) {
                        tr("Teilen fehlgeschlagen: {message}", "message" to error.message)
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
    tr("Erste Schritte") to listOf(
        tr("Ohne Server") to tr("Beim ersten Start „Ohne Server nutzen“ wählen: LiNotes ist dann einfach eine Notizen-App, alles liegt ") +
            tr("verschlüsselt nur auf diesem Gerät. Später unter Einstellungen → „Mit Server verbinden …“ einen Server eintragen – ") +
            tr("deine Notizen werden dann hochgeladen und lassen sich teilen und auf anderen Geräten nutzen."),
        tr("Konto anlegen") to tr("Beim ersten Start gibst du die Adresse deines LiNotes-Servers ein und wählst „Neues Konto erstellen“. ") +
            tr("Dafür brauchst du einen Einladungscode von der Person, die den Server betreibt. Ein Passwort gibt es nicht – ") +
            tr("dein Konto ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt."),
        tr("Schlüsseldatei sichern") to tr("Speichere direkt danach die Schlüsseldatei (Einstellungen → „Schlüsseldatei sichern“) ") +
            tr("und lege sie z. B. auf einem USB-Stick an einen sicheren Ort. Ohne Gerät und ohne Schlüsseldatei kann niemand ") +
            tr("– auch nicht der Server-Betreiber – deine Notizen wiederherstellen."),
        tr("Weiteres Gerät") to tr("Auf dem neuen Gerät „Mit anderem Gerät verbinden“ wählen und deinen Benutzernamen eingeben. ") +
            tr("Auf einem Gerät, auf dem du schon angemeldet bist, erscheint dann eine Anfrage: dort den 6-stelligen Code ") +
            tr("eintippen oder den QR-Code scannen."),
    ),
    tr("Notizen") to listOf(
        tr("Formatieren") to tr("Über „Aa“ wählst du Titel, Überschrift, Unterüberschrift, Text, Monospace, Listen oder Zitat."),
        tr("Checklisten") to tr("Kreis antippen, um einen Punkt abzuhaken. Eine leere Zeile beendet die Liste. Über „Mehr“ kannst du ") +
            tr("abgehakte Punkte automatisch nach unten sortieren lassen."),
        tr("Tags") to tr("Schreibe #Wort in eine Notiz – der Tag erscheint in der Ordnerübersicht zum Filtern."),
        tr("Profi-Funktionen") to tr("Ab Werk zeigt LiNotes nur, was man im Alltag braucht. Einstellungen → „Profi-Funktionen“ einschalten – dann gibt es im Format-Feld (Aa) zusätzlich Code mit Syntaxfarben (Python, Kotlin, Shell, JSON) und Fußnoten/Quellen – hochgestellte Nummern im Text, die Liste „Fußnoten und Quellen“ unter der Notiz und im PDF; Nummer antippen zum Bearbeiten – sowie Formeln in LaTeX-Schreibweise („Formel (LaTeX) …“, z. B. \\frac{a}{b}, x^2, \\sqrt{x}, \\sum_{i=1}^{n}, Matrizen und Fallunterscheidungen), sauber gesetzt in der Notiz und im PDF, ohne Internet; Formel antippen zum Ändern, unbekannte Befehle werden rot markiert. Der Schalter gilt für dein Konto auf allen Geräten. Notizen, die solche Elemente schon enthalten, werden immer richtig angezeigt. Ein leerer Code-Absatz mit Enter beendet den Code-Block."),
        tr("Vorlagen") to tr("In einem Ordner „…“ → „Neue Notiz aus Vorlage …“: mitgeliefert sind Besprechung, Protokoll, Reisecheckliste und Tagebuch. Eigene Vorlage: Notiz lange drücken → „Als Vorlage verwenden“. {{Datum}}, {{Uhrzeit}} und {{Wochentag}} werden beim Anlegen durch die aktuellen Werte ersetzt, z. B. „Besprechung {{Datum}}“."),
        tr("Link-Vorschau") to tr("Steht eine Webadresse allein in einer Zeile, wird sie nach Enter zur Vorschau mit Titel, Bild und Domain – wenn du Einstellungen → „Link-Vorschau“ einschaltest; ab Werk ist sie aus. Dafür ruft nur dieses Handy die Seite ab, der Betreiber sieht dabei die Adresse deines Anschlusses. Die Vorschau liegt verschlüsselt in der Notiz, andere Geräte rufen nichts ab. Vorschau antippen → „Im Browser öffnen“ oder „Nur als Adresse zeigen“. Gesperrte Notizen bekommen keine Vorschau."),
        tr("Gesperrte Notizen") to tr("Über „Mehr“ → „Notiz sperren“ schützt du eine Notiz mit deinem Notizen-Passwort. In den ") +
            tr("Einstellungen kannst du das Entsperren mit Fingerabdruck, PIN oder Muster einschalten. Gesperrte Notizen ") +
            tr("sperren sich nach 10 Minuten ohne Benutzung wieder. Geteilte Notizen können nicht gesperrt werden."),
        tr("Auf dem Handy behalten") to tr("Notizen liegen auf deinem Handy und verschlüsselt auf dem Server. Wie lange der Inhalt ") +
            tr("nach der letzten Benutzung auf dem Handy bleibt, stellst du pro Notiz (Mehr → „Auf dem Gerät behalten“) oder ") +
            tr("für alle in den Einstellungen ein. Danach wird die Notiz beim Öffnen vom Server geladen. Angeheftete Notizen, ") +
            tr("Listen und Boards bleiben immer auf dem Gerät."),
        tr("Gelöschte Notizen") to tr("Gelöschte Notizen liegen 30 Tage in „Zuletzt gelöscht“ und lassen sich dort wiederherstellen."),
    ),
    tr("Teilen") to listOf(
        tr("Personen verifizieren") to tr("Bevor du etwas teilst, verifiziert ihr euch einmal: Einstellungen → „Personen“ → Person antippen. ") +
            tr("Dein Gerät zeigt einen Code, die andere Person tippt ihn ein oder scannt den QR-Code. So kann niemand – auch ") +
            tr("nicht der Server – euch einen falschen Schlüssel unterschieben."),
        tr("Etwas teilen") to tr("Ordner, Liste, Board oder Notiz lange gedrückt halten → „Teilen …“ und die Personen auswählen. ") +
            tr("Wird ein Ordner geteilt, gilt das für alle Notizen darin. Entfernst du jemanden, wird neu verschlüsselt."),
    ),
    tr("Listen und Aufgaben") to listOf(
        tr("Listen") to tr("Einträge unten eintippen – sie landen automatisch in der passenden Warengruppe. Abgehakt wird mit dem Kreis."),
        tr("Aufgaben-Board") to tr("Karte antippen für Fälligkeit, Zuständigkeit, Priorität, Farbe und Notizen; lange drücken zum Verschieben."),
        tr("Entwicklungsprojekt") to tr("Board in der Übersicht lange drücken → „Als Entwicklungsprojekt führen“. Dann zeigen die Karten ") +
            tr("ihre Kurz-ID (zum Zitieren in Commits und Berichten) und im Dialog den Verlauf: wer die Karte wann in welche ") +
            tr("Spalte geschoben hat. Unter „Verifikation“ hängst du Nachweise an – Prüfprotokolle, Screenshots, Messdaten. ") +
            tr("Sie liegen verschlüsselt an der Karte, mit Zeitpunkt, Person und Prüfsumme (SHA-256). ") +
            tr("Für einfache Boards bleibt alles wie gewohnt."),
        tr("Pläne") to tr("Reiter „Pläne“ → „+“ und eine Vorlage wählen: Stundenplan, Schichtplan, Putzplan, OP-/Raumplan oder Projektplan. ") +
            tr("Raster: Zelle antippen für Text und Farbe, Zeilen- und Spaltenköpfe zum Einfügen, Verschieben und Löschen. ") +
            tr("Projektplan: „…“ → „Reihenfolge ändern“ oder „Nach Datum sortieren“; verschiebst du einen Meilenstein, bleibt der alte ") +
            tr("Termin blass sichtbar und das Plan-PDF listet die Verschiebung. „…“ → „Als PDF teilen …“ zum Aushängen."),
        tr("Bericht") to tr("Board lange drücken → „Bericht teilen (PDF)“: der aktuelle Stand als PDF, z. B. als Nachweis für Kunden. ") +
            tr("Bei Entwicklungsprojekten mit Traceability-Matrix (Karte ↔ Commits ↔ Verifikation ↔ Abnahme); Nachweise stehen mit Prüfsumme darin, Bilder eingebettet."),
    ),
    tr("Agiles Arbeiten") to listOf(
        tr("Das agile Manifest") to tr("Manifest für Agile Softwareentwicklung\n\nWir erschließen bessere Wege, Software zu entwickeln, indem wir es selbst tun und anderen dabei helfen. Durch diese Tätigkeit haben wir diese Werte zu schätzen gelernt:\n\nIndividuen und Interaktionen mehr als Prozesse und Werkzeuge\nFunktionierende Software mehr als umfassende Dokumentation\nZusammenarbeit mit dem Kunden mehr als Vertragsverhandlung\nReagieren auf Veränderung mehr als das Befolgen eines Plans\n\nDas heißt, obwohl wir die Werte auf der rechten Seite wichtig finden, schätzen wir die Werte auf der linken Seite höher ein.\n\nKent Beck, Mike Beedle, Arie van Bennekum, Alistair Cockburn, Ward Cunningham, Martin Fowler, James Grenning, Jim Highsmith, Andrew Hunt, Ron Jeffries, Jon Kern, Brian Marick, Robert C. Martin, Steve Mellor, Ken Schwaber, Jeff Sutherland, Dave Thomas\n\n© 2001, the above authors – this declaration may be freely copied in any form, but only in its entirety through this notice.\n\nWortlaut und deutsche Übersetzung: agilemanifesto.org/iso/de/manifesto.html"),
        tr("Die zwölf Prinzipien – kurz gefasst") to tr("1. Früh und regelmäßig etwas Nützliches liefern – das stellt Kunden am besten zufrieden.\n2. Geänderte Anforderungen sind willkommen, auch spät.\n3. In kurzen Abständen funktionierende Ergebnisse liefern, lieber Wochen als Monate.\n4. Fachleute und Entwickler arbeiten täglich zusammen.\n5. Projekte um motivierte Menschen bauen, ihnen Umfeld, Unterstützung und Vertrauen geben.\n6. Am besten informiert das direkte Gespräch.\n7. Fortschritt misst sich an dem, was funktioniert.\n8. Ein Tempo halten, das alle dauerhaft durchhalten können.\n9. Technische Qualität und gutes Design machen beweglich.\n10. Einfachheit: möglichst viel Arbeit gar nicht erst tun müssen.\n11. Gute Lösungen entstehen in Teams, die sich selbst organisieren.\n12. Regelmäßig innehalten, gemeinsam besser werden und das Vorgehen anpassen.\n\nIn eigenen Worten zusammengefasst; Wortlaut: agilemanifesto.org/iso/de/principles.html"),
        tr("Agil arbeiten mit LiNotes") to tr("Ein Board zeigt den Arbeitsfluss auf einen Blick: Spalten wie „Offen – In Arbeit – Erledigt“, jede Karte ein kleines, abgeschlossenes Stück Arbeit. So passen die vier Werte dazu:\n• Individuen und Interaktionen: Boards teilen, Karten zuweisen und mit @-Erwähnungen ins Gespräch holen – LiNotes unterstützt das Gespräch, ersetzt es aber nicht.\n• Funktionierende Software: Karten klein schneiden und erst nach „Erledigt“ schieben, wenn es wirklich funktioniert; bei Entwicklungsprojekten belegen Nachweise das.\n• Zusammenarbeit mit dem Kunden: Auftraggeber ins Board einladen: Sie schreiben Wünsche als Karten und nehmen selbst ab – z. B. so vereinbart, dass nur sie nach „Erledigt“ schieben.\n• Reagieren auf Veränderung: Prioritäten jederzeit ändern und Karten umsortieren; Pläne zeigen verschobene Meilensteine offen, statt sie zu verstecken.\n\nRegelmäßig reflektieren: den Bericht als PDF erzeugen und gemeinsam durchgehen – was lief gut, was ändern wir? Dokumentation nur so viel wie nötig: Auswirkungsanalyse, Verifikation und Nachweise sind für Projekte gedacht, die sie brauchen (z. B. nach ISO 26262 oder Automotive SPICE) – einfache Boards bleiben schlank."),
    ),
    tr("Datenschutz") to listOf(
        tr("Was der Server weiß") to tr("Alles – Notizen, Listen, Boards, Ordnernamen und Bilder – wird auf deinem Gerät verschlüsselt, ") +
            tr("bevor es den Server erreicht. Der Server sieht nur, dass es Einträge gibt, wie groß sie sind und wann sie ") +
            tr("geändert wurden – nicht, was darin steht."),
    ),
)

@Composable
fun HelpScreen(state: AppState) {
    val colors = palette
    var open by remember { mutableStateOf<String?>(null) }
    LargeTitleScreen(title = tr("Hilfe"), backLabel = tr("Einstellungen"), onBack = { state.pop() }) {
        HELP.forEach { (header, entries) ->
            section("help-$header", header = header) {
                entries.forEachIndexed { index, (title, text) ->
                    GroupRow(title, chevron = false, divider = index < entries.lastIndex && open != title,
                        detail = if (open == title) "−" else "+") { open = if (open == title) null else title }
                    if (open == title) {
                        Text(text, style = Type.subheadline, color = colors.secondary, modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp))
                        HelpPictures(state, title)
                        if (index < entries.lastIndex) HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
                    }
                }
            }
        }
    }
}

/** Screenshots for a help entry (tools/help-images.json → assets/help), light or dark like the app;
 *  tapping one shows it large in the quick look. */
@Composable
private fun HelpPictures(state: AppState, title: String) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val dark = palette.dark
    val names = remember(title, dark) {
        try {
            val index = org.json.JSONObject(context.assets.open("help/index.json").bufferedReader().use { it.readText() })
            val list = index.optJSONArray(title) ?: return@remember emptyList<String>()
            (0 until list.length()).map { i -> list.getJSONObject(i).let { if (dark && !it.isNull("dark")) it.getString("dark") else it.getString("light") } }
        } catch (error: Exception) { emptyList() }
    }
    names.forEachIndexed { index, name ->
        val bitmap = remember(name) {
            try { context.assets.open("help/$name").use { android.graphics.BitmapFactory.decodeStream(it) } } catch (error: Exception) { null }
        } ?: return@forEachIndexed
        androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 12.dp),
            contentAlignment = Alignment.Center) {
            androidx.compose.foundation.Image(bitmap.asImageBitmap(), tr("Bildschirmfoto: {title}", "title" to title),
                Modifier.fillMaxWidth(if (bitmap.height > bitmap.width) 0.6f else 1f).clip(RoundedCornerShape(10.dp)).clickable {
                    // Named after the help entry, so the quick look shows "Aufgaben-Board", not the asset name.
                    val label = title + if (names.size > 1) " (${index + 1})" else ""
                    val file = java.io.File(java.io.File(context.cacheDir, "help").apply { mkdirs() }, "$label.webp")
                    context.assets.open("help/$name").use { input -> file.outputStream().use { input.copyTo(it) } }
                    state.quickLook = LookFile(file, "image/webp")
                })
        }
    }
}
