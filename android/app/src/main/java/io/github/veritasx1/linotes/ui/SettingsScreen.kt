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
    var textChoice by remember { mutableStateOf(false) }
    var textSize by remember { mutableStateOf(sync.textSize) }
    var justify by remember { mutableStateOf(sync.justify) }
    var hyphenate by remember { mutableStateOf(sync.hyphenate) }
    var linkPreviews by remember { mutableStateOf(sync.linkPreviews) }
    var changeVault by remember { mutableStateOf(false) }
    var enableBiometric by remember { mutableStateOf(false) }
    var signOut by remember { mutableStateOf(false) }
    var biometricOn by remember { mutableStateOf(state.biometricEnabled) }
    val online by sync.online.collectAsStateCompat()

    LargeTitleScreen(title = "Einstellungen", backLabel = "Ordner", onBack = { state.pop() }) {
        if (sync.isLocal) section("account", header = "Konto", compact = true, footer = "Deine Notizen liegen verschlüsselt nur auf diesem Gerät. " +
            "Mit einem Server werden sie gesichert, auf deinen anderen Geräten abgeglichen und lassen sich teilen.") {
            GroupRow("Nur auf diesem Gerät", Glyph.CloudOff, tint = colors.secondary, chevron = false)
            GroupRow("Mit Server verbinden …", Glyph.Cloud, divider = false) { state.push(Route.Connect) }
        } else section("account", header = "Konto", compact = true) {
            GroupRow(sync.user?.name ?: "", Glyph.Person, subtitle = "@${sync.user?.username}", chevron = false)
            GroupRow(if (online) "Verbunden mit ${sync.server.removePrefix("https://")}" else "Offline – Änderungen werden später übertragen",
                if (online) Glyph.Cloud else Glyph.CloudOff, tint = if (online) colors.accent else colors.red, chevron = false)
            // Recommended, never forced at the first start.
            GroupRow("Schlüsseldatei sichern …", Glyph.Key, detail = if (sync.keyfileSaved()) null else "Empfohlen", divider = false) { keyfile = true }
        }
        if (!sync.isLocal) section("people", header = "Personen", compact = true, footer = "Verifiziere Personen, bevor du etwas mit ihnen teilst.") {
            val others = otherUsers(sync)
            val open = others.count { Pairing.verifiedState(sync, it) != "verified" }
            GroupRow("Personen und Einladungen", Glyph.Person, detail = if (open > 0) "$open nicht verifiziert" else null, divider = false) {
                state.push(Route.People)
            }
        }
        section("text", header = "Darstellung", compact = true, footer = "Gilt für den Text in Notizen auf diesem Handy, zusätzlich zur Schriftgröße in den Android-Einstellungen. " +
            "Blocksatz gilt für normal ausgerichtete Absätze, Silbentrennung nach der Sprache des Handys.") {
            GroupRow("Textgröße", Glyph.Format, detail = io.github.veritasx1.linotes.data.TEXT_SIZES[textSize].second) { textChoice = true }
            fun toggleJustify() { justify = !justify; sync.justify = justify }
            fun toggleHyphenate() { hyphenate = !hyphenate; sync.hyphenate = hyphenate }
            GroupRow("Blocksatz", Glyph.Format, chevron = false, trailing = { IosSwitch(justify, "Blocksatz") { toggleJustify() } }) { toggleJustify() }
            GroupRow("Silbentrennung", Glyph.Format, chevron = false, divider = false,
                trailing = { IosSwitch(hyphenate, "Silbentrennung") { toggleHyphenate() } }) { toggleHyphenate() }
        }
        section("links", header = "Link-Vorschau", compact = true, footer = "Steht eine Webadresse allein in einer Zeile, wird sie zur Vorschau mit Titel und Bild. " +
            "Dafür ruft dieses Handy die Seite ab – der Betreiber sieht dabei die Adresse deines Anschlusses. Die Vorschau liegt verschlüsselt in der Notiz; " +
            "andere Geräte rufen nichts ab. Gesperrte Notizen bekommen keine Vorschau.") {
            fun toggleLinks() { linkPreviews = !linkPreviews; sync.linkPreviews = linkPreviews }
            GroupRow("Link-Vorschau", Glyph.Globe, chevron = false, divider = false,
                trailing = { IosSwitch(linkPreviews, "Link-Vorschau") { toggleLinks() } }) { toggleLinks() }
        }
        if (!sync.isLocal) section("keep", header = "Auf diesem Handy", compact = true, footer = "So lange bleibt der Inhalt einer Notiz nach der letzten Benutzung auf dem Handy. " +
            "Danach liegt er nur noch verschlüsselt auf dem Server und wird beim Öffnen geladen. Angeheftete Notizen, Listen und Boards bleiben immer hier.") {
            GroupRow("Notizen behalten", Glyph.Notes, detail = Keep.label(sync.keepDefault()), divider = false) { keepChoice = true }
        }
        section("security", header = "Gesperrte Notizen", compact = true, footer = "Gesperrte Notizen sind zusätzlich mit deinem Notizen-Passwort verschlüsselt. " +
            "Der Server kennt weder das Passwort noch den Inhalt.") {
            fun toggleBiometric() {
                when {
                    !state.hasVault() -> state.toastLater("Sperre zuerst eine Notiz, um ein Notizen-Passwort festzulegen.")
                    biometricOn -> { state.disableBiometric(); biometricOn = false }
                    state.vaultKey != null -> state.enableBiometric { ok -> biometricOn = ok; if (!ok) state.toastLater("Nicht eingeschaltet.") }
                    else -> enableBiometric = true
                }
            }
            GroupRow("Fingerabdruck / PIN / Muster", Glyph.Fingerprint, chevron = false,
                titleColor = if (state.hasVault()) colors.label else colors.tertiary,
                trailing = { IosSwitch(biometricOn, "Fingerabdruck / PIN / Muster") { toggleBiometric() } }) { toggleBiometric() }
            GroupRow("Notizen-Passwort ändern …", Glyph.Password, titleColor = if (state.hasVault()) colors.label else colors.tertiary) {
                if (state.hasVault()) changeVault = true else state.toastLater("Du hast noch kein Notizen-Passwort festgelegt.")
            }
            GroupRow("Entsperrte Notizen jetzt sperren", Glyph.Lock, divider = false, chevron = false) {
                state.lockAll()
                state.toastLater("Gesperrte Notizen sind wieder gesperrt.")
            }
        }
        section("about", header = "Über", compact = true, footer = "LiNotes 2.0.2 · Ende-zu-Ende verschlüsselt – auf diesem Gerät oder deinem eigenen Server. Keine Werbung, keine Tracker, keine Cloud eines Konzerns.") {
            GroupRow("Hilfe", Glyph.Notes) { state.push(Route.Help) }
            GroupRow(if (sync.isLocal) "Alle Daten löschen" else "Abmelden", divider = false, chevron = false, titleColor = colors.red) { signOut = true }
        }
    }

    if (keyfile) KeyfileDialog(state) { keyfile = false }
    if (textChoice) {
        ActionSheet("Textgröße in Notizen", io.github.veritasx1.linotes.data.TEXT_SIZES.mapIndexed { index, (_, label) ->
            SheetAction(label + if (index == textSize) " ✓" else "") { sync.textSize = index; textSize = index }
        }) { textChoice = false }
    }
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
        AlertDialog(if (sync.isLocal) "Alle Daten löschen?" else "Abmelden?",
            if (sync.isLocal) "Alle Notizen, Listen und Aufgaben auf diesem Gerät werden endgültig gelöscht."
            else "Auf diesem Gerät wird alles gelöscht. Nicht übertragene Änderungen gehen verloren. " +
                "Hast du deine Schlüsseldatei gesichert oder ein anderes angemeldetes Gerät?",
            if (sync.isLocal) "Löschen" else "Abmelden", destructive = true,
            onDismiss = { signOut = false }) {
            signOut = false
            sync.signOut()
            state.lockAll()
            state.disableBiometric()
            state.signedIn = false
        }
    }
}
