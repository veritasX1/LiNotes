package io.github.veritasx1.linotes.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import io.github.veritasx1.linotes.R
import io.github.veritasx1.linotes.data.Api
import io.github.veritasx1.linotes.data.ApiException
import io.github.veritasx1.linotes.data.DEFAULT_SERVER
import io.github.veritasx1.linotes.data.OfflineException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

fun errorText(error: Throwable): String = when {
    error is OfflineException -> "Der Server ist nicht erreichbar. Prüfe die Internetverbindung."
    error is ApiException -> when (error.code) {
        "wrong-credentials" -> "Benutzername oder Passwort ist falsch."
        "too-many-attempts" -> "Zu viele Versuche. Bitte warte ein paar Minuten."
        "invalid-invite" -> "Dieser Einladungscode ist ungültig oder wurde schon verwendet."
        "invalid-username" -> "Der Benutzername darf nur Kleinbuchstaben, Ziffern, Punkt, Minus und Unterstrich enthalten."
        "password-too-short" -> "Das Passwort muss mindestens 8 Zeichen lang sein."
        "username-taken" -> "Dieser Benutzername ist schon vergeben."
        else -> "Fehler: ${error.code}"
    }
    else -> "Fehler: ${error.message}"
}

@Composable
fun LoginScreen(state: AppState) {
    val colors = palette
    val scope = rememberCoroutineScope()
    var register by remember { mutableStateOf(false) }
    var invite by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var server by remember { mutableStateOf(DEFAULT_SERVER) }
    var showServer by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun submit() {
        if (username.isBlank() || password.isEmpty()) {
            error = "Bitte Benutzername und Passwort eingeben."
            return
        }
        busy = true
        error = null
        scope.launch {
            try {
                val url = server.trim().ifEmpty { DEFAULT_SERVER }
                val response = withContext(Dispatchers.IO) {
                    val api = Api(url)
                    if (register) api.register(invite.trim(), username.trim().lowercase(), name.trim(), password, state.sync.deviceName)
                    else api.login(username.trim().lowercase(), password, state.sync.deviceName)
                }
                state.sync.signIn(url, response)
                withContext(Dispatchers.IO) { state.sync.syncNow() }
                state.ensureDefaults()
                state.signedIn = true
            } catch (failure: Exception) {
                error = errorText(failure)
            } finally {
                busy = false
            }
        }
    }

    Column(
        Modifier.fillMaxSize().background(colors.background).statusBarsPadding().imePadding().verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(48.dp))
        // The adaptive launcher icon cannot be drawn by Compose; stack its layers.
        androidx.compose.foundation.layout.Box(Modifier.size(96.dp).clip(RoundedCornerShape(22.dp))) {
            Image(painterResource(R.drawable.ic_launcher_background), null, Modifier.size(96.dp))
            Image(painterResource(R.drawable.ic_launcher_foreground), null, Modifier.size(96.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text("LiNotes", style = Type.largeTitle, color = colors.label)
        Text(
            if (register) "Gib den Einladungscode ein und wähle deinen Benutzernamen und dein Passwort."
            else "Notizen, Einkaufslisten und Aufgaben – auf deinem eigenen Server.",
            style = Type.subheadline, color = colors.secondary, textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 40.dp, vertical = 6.dp),
        )
        Spacer(Modifier.height(20.dp))
        Column(Modifier.padding(horizontal = 16.dp).fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colors.surface)) {
            if (register) {
                InputRow(invite, { invite = it }, "Einladungscode")
                InputRow(name, { name = it }, "Dein Name")
            }
            InputRow(username, { username = it }, "Benutzername")
            InputRow(password, { password = it }, "Passwort", password = true, divider = false, imeAction = ImeAction.Go, onDone = { submit() })
        }
        if (showServer) {
            Spacer(Modifier.height(12.dp))
            Column(Modifier.padding(horizontal = 16.dp).fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colors.surface)) {
                InputRow(server, { server = it }, "Server", divider = false)
            }
        }
        error?.let {
            Text(it, style = Type.footnote, color = colors.red, textAlign = TextAlign.Center, modifier = Modifier.padding(16.dp))
        }
        Spacer(Modifier.height(20.dp))
        PrimaryButton(if (busy) "Einen Moment …" else if (register) "Konto erstellen" else "Anmelden", enabled = !busy,
            modifier = Modifier.padding(horizontal = 16.dp)) { submit() }
        Spacer(Modifier.height(10.dp))
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            TextButton(if (register) "Ich habe schon ein Konto" else "Neues Konto mit Einladungscode") { register = !register; error = null }
            TextButton(if (showServer) "Server ausblenden" else "Anderer Server …", color = colors.secondary) { showServer = !showServer }
        }
        Spacer(Modifier.height(40.dp))
    }
}
