package io.github.veritasx1.linotes.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import io.github.veritasx1.linotes.data.Vault
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun SettingsScreen(state: AppState, revision: Long) {
    val colors = palette
    val sync = state.sync
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboardManager.current
    var inviteCode by remember { mutableStateOf<String?>(null) }
    var changePassword by remember { mutableStateOf(false) }
    var changeVault by remember { mutableStateOf(false) }
    var signOut by remember { mutableStateOf(false) }
    val online by sync.online.collectAsStateCompat()

    LargeTitleScreen(title = "Einstellungen", backLabel = "Ordner", onBack = { state.pop() }) {
        section("account", header = "Konto") {
            GroupRow(sync.user?.name ?: "", Glyph.Person, subtitle = "@${sync.user?.username}", chevron = false)
            GroupRow(if (online) "Verbunden mit ${sync.server.removePrefix("https://")}" else "Offline – Änderungen werden später übertragen",
                if (online) Glyph.Cloud else Glyph.CloudOff, tint = if (online) colors.accent else colors.red, chevron = false, divider = false)
        }
        section("people", header = "Familie", footer = "Mit einem Einladungscode kann sich jemand einmalig ein eigenes Konto anlegen.") {
            val others = sync.users.filter { it.id != sync.userId }
            others.forEach { GroupRow(it.name, Glyph.Person, subtitle = "@${it.username}", chevron = false) }
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
        section("security", header = "Sicherheit", footer = "Gesperrte Notizen sind Ende-zu-Ende verschlüsselt. Der Server kennt weder das Notizen-Passwort noch den Inhalt.") {
            GroupRow("Kontopasswort ändern …", Glyph.Lock) { changePassword = true }
            GroupRow("Notizen-Passwort ändern …", Glyph.Lock, titleColor = if (state.hasVault()) colors.label else colors.tertiary) {
                if (state.hasVault()) changeVault = true else state.toastLater("Du hast noch kein Notizen-Passwort festgelegt.")
            }
            GroupRow("Gesperrte Notizen jetzt sperren", Glyph.Lock, divider = false, chevron = false) {
                state.lockAll()
                state.toastLater("Gesperrte Notizen sind wieder gesperrt.")
            }
        }
        section("about", header = "Über", footer = "LiNotes 1.0 · Deine Daten liegen auf deinem eigenen Server. Keine Werbung, keine Tracker, keine Cloud eines Konzerns.") {
            GroupRow("Abmelden", divider = false, chevron = false, titleColor = colors.red) { signOut = true }
        }
    }

    inviteCode?.let { code ->
        AlertDialog("Einladungscode", "Einmalig gültig:\n\n$code\n\nIn der App „Neues Konto mit Einladungscode“ wählen.", "Kopieren",
            onDismiss = { inviteCode = null }) {
            clipboard.setText(AnnotatedString(code))
            inviteCode = null
        }
    }
    if (changePassword) {
        AlertDialog("Kontopasswort ändern", "Andere Geräte werden danach abgemeldet.", "Ändern",
            fields = listOf(AlertField("Aktuelles Passwort", password = true), AlertField("Neues Passwort (min. 8 Zeichen)", password = true)),
            onDismiss = { changePassword = false }) { values ->
            changePassword = false
            scope.launch {
                try {
                    val response = withContext(Dispatchers.IO) { sync.api!!.changePassword(values[0], values[1], sync.deviceName) }
                    sync.updateToken(response.getString("token"))
                    state.showToast("Passwort geändert.")
                } catch (error: Exception) {
                    state.showToast(errorText(error))
                }
            }
        }
    }
    if (changeVault) {
        AlertDialog("Notizen-Passwort ändern", "Alle gesperrten Notizen werden neu verschlüsselt.", "Ändern",
            fields = listOf(AlertField("Aktuelles Passwort", password = true), AlertField("Neues Passwort", password = true), AlertField("Merkhilfe")),
            onDismiss = { changeVault = false }) { values ->
            changeVault = false
            scope.launch {
                try {
                    val count = withContext(Dispatchers.Default) { state.changeVaultPassword(values[0], values[1], values[2]) }
                    state.showToast("Geändert, $count Notizen neu verschlüsselt.")
                } catch (error: Vault.WrongPassword) {
                    state.showToast("Falsches Passwort.")
                }
            }
        }
    }
    if (signOut) {
        AlertDialog("Abmelden?", "Nicht übertragene Änderungen auf diesem Gerät gehen verloren.", "Abmelden", destructive = true,
            onDismiss = { signOut = false }) {
            signOut = false
            sync.signOut()
            state.lockAll()
            state.signedIn = false
        }
    }
}

