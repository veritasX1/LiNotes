package io.github.veritasx1.linotes.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import io.github.veritasx1.linotes.data.Keep
import io.github.veritasx1.linotes.data.Pairing
import io.github.veritasx1.linotes.data.Vault
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun SettingsScreen(state: AppState, revision: Long) {
    val colors = palette
    val sync = state.sync
    val scope = rememberCoroutineScope()
    var keyfile by remember { mutableStateOf(false) }
    var keepChoice by remember { mutableStateOf(false) }
    var changeVault by remember { mutableStateOf(false) }
    var enableBiometric by remember { mutableStateOf(false) }
    var signOut by remember { mutableStateOf(false) }
    var biometricOn by remember { mutableStateOf(state.biometricEnabled) }
    val online by sync.online.collectAsStateCompat()

    LargeTitleScreen(title = "Einstellungen", backLabel = "Ordner", onBack = { state.pop() }) {
        section("account", header = "Konto") {
            GroupRow(sync.user?.name ?: "", Glyph.Person, subtitle = "@${sync.user?.username}", chevron = false)
            GroupRow(if (online) "Verbunden mit ${sync.server.removePrefix("https://")}" else "Offline – Änderungen werden später übertragen",
                if (online) Glyph.Cloud else Glyph.CloudOff, tint = if (online) colors.accent else colors.red, chevron = false)
            GroupRow("Schlüsseldatei sichern …", Glyph.Lock, divider = false) { keyfile = true }
        }
        section("people", header = "Personen", footer = "Verifiziere Personen, bevor du etwas mit ihnen teilst.") {
            val others = otherUsers(sync)
            val open = others.count { Pairing.verifiedState(sync, it) != "verified" }
            GroupRow("Personen und Einladungen", Glyph.Person, detail = if (open > 0) "$open nicht verifiziert" else null, divider = false) {
                state.push(Route.People)
            }
        }
        section("keep", header = "Auf diesem Handy", footer = "So lange bleibt der Inhalt einer Notiz nach der letzten Benutzung auf dem Handy. " +
            "Danach liegt er nur noch verschlüsselt auf dem Server und wird beim Öffnen geladen. Angeheftete Notizen, Listen und Boards bleiben immer hier.") {
            GroupRow("Notizen behalten", Glyph.Notes, detail = Keep.label(sync.keepDefault()), divider = false) { keepChoice = true }
        }
        section("security", header = "Gesperrte Notizen", footer = "Gesperrte Notizen sind zusätzlich mit deinem Notizen-Passwort verschlüsselt. " +
            "Der Server kennt weder das Passwort noch den Inhalt.") {
            GroupRow("Fingerabdruck / PIN / Muster", Glyph.Lock, chevron = false,
                titleColor = if (state.hasVault()) colors.label else colors.tertiary,
                detail = if (biometricOn) "Ein" else "Aus") {
                when {
                    !state.hasVault() -> state.toastLater("Sperre zuerst eine Notiz, um ein Notizen-Passwort festzulegen.")
                    biometricOn -> { state.disableBiometric(); biometricOn = false }
                    state.vaultKey != null -> state.enableBiometric { ok -> biometricOn = ok; if (!ok) state.toastLater("Nicht eingeschaltet.") }
                    else -> enableBiometric = true
                }
            }
            GroupRow("Notizen-Passwort ändern …", Glyph.Lock, titleColor = if (state.hasVault()) colors.label else colors.tertiary) {
                if (state.hasVault()) changeVault = true else state.toastLater("Du hast noch kein Notizen-Passwort festgelegt.")
            }
            GroupRow("Gesperrte Notizen jetzt sperren", Glyph.Lock, divider = false, chevron = false) {
                state.lockAll()
                state.toastLater("Gesperrte Notizen sind wieder gesperrt.")
            }
        }
        section("about", header = "Über", footer = "LiNotes 2.0 · Ende-zu-Ende verschlüsselt auf deinem eigenen Server. Keine Werbung, keine Tracker, keine Cloud eines Konzerns.") {
            GroupRow("Hilfe", Glyph.Notes) { state.push(Route.Help) }
            GroupRow("Abmelden", divider = false, chevron = false, titleColor = colors.red) { signOut = true }
        }
    }

    if (keyfile) KeyfileDialog(state, firstTime = false) { keyfile = false }
    if (keepChoice) {
        ActionSheet("Notizen auf dem Handy behalten", Keep.choices.map { (value, label) ->
            SheetAction(label + if (value == sync.keepDefault()) " ✓" else "") { sync.setKeepDefault(value); sync.evict() }
        }) { keepChoice = false }
    }
    if (enableBiometric) {
        UnlockDialog(state, "Gib einmal dein Notizen-Passwort ein.", onDismiss = { enableBiometric = false }) {
            enableBiometric = false
            state.enableBiometric { ok -> biometricOn = ok; if (!ok) state.toastLater("Nicht eingeschaltet.") }
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
                    biometricOn = state.biometricEnabled
                    state.showToast("Geändert, $count Notizen neu verschlüsselt.")
                } catch (error: Vault.WrongPassword) {
                    state.showToast("Falsches Passwort.")
                }
            }
        }
    }
    if (signOut) {
        AlertDialog("Abmelden?", "Auf diesem Gerät wird alles gelöscht. Nicht übertragene Änderungen gehen verloren. " +
            "Hast du deine Schlüsseldatei gesichert oder ein anderes angemeldetes Gerät?", "Abmelden", destructive = true,
            onDismiss = { signOut = false }) {
            signOut = false
            sync.signOut()
            state.lockAll()
            state.disableBiometric()
            state.signedIn = false
        }
    }
}
