package io.github.veritasx1.linotes.ui

import io.github.veritasx1.linotes.i18n.tr

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
    var languageChoice by remember { mutableStateOf(false) }
    var textSize by remember { mutableStateOf(sync.textSize) }
    var justify by remember { mutableStateOf(sync.justify) }
    var hyphenate by remember { mutableStateOf(sync.hyphenate) }
    var linkPreviews by remember { mutableStateOf(sync.linkPreviews) }
    var pro by remember { mutableStateOf(sync.proFeatures) }
    var changeVault by remember { mutableStateOf(false) }
    var enableBiometric by remember { mutableStateOf(false) }
    var signOut by remember { mutableStateOf(false) }
    var biometricOn by remember { mutableStateOf(state.biometricEnabled) }
    val online by sync.online.collectAsStateCompat()

    LargeTitleScreen(title = tr("Einstellungen"), backLabel = tr("Ordner"), onBack = { state.pop() }) {
        if (sync.isLocal) section("account", header = tr("Konto"), compact = true, footer = tr("Deine Notizen liegen verschlüsselt nur auf diesem Gerät. ") +
            tr("Mit einem Server werden sie gesichert, auf deinen anderen Geräten abgeglichen und lassen sich teilen.")) {
            GroupRow(tr("Nur auf diesem Gerät"), Glyph.CloudOff, tint = colors.secondary, chevron = false)
            GroupRow(tr("Mit Server verbinden …"), Glyph.Cloud, divider = false) { state.push(Route.Connect) }
        } else section("account", header = tr("Konto"), compact = true) {
            GroupRow(sync.user?.name ?: "", Glyph.Person, subtitle = "@${sync.user?.username}", chevron = false)
            GroupRow(if (online) tr("Verbunden mit {removePrefix}", "removePrefix" to (sync.server.removePrefix("https://"))) else tr("Offline – Änderungen werden später übertragen"),
                if (online) Glyph.Cloud else Glyph.CloudOff, tint = if (online) colors.accent else colors.red, chevron = false)
            // Recommended, never forced at the first start.
            GroupRow(tr("Schlüsseldatei sichern …"), Glyph.Key, detail = if (sync.keyfileSaved()) null else tr("Empfohlen"), divider = false) { keyfile = true }
        }
        if (!sync.isLocal) section("people", header = tr("Personen"), compact = true, footer = tr("Verifiziere Personen, bevor du etwas mit ihnen teilst.")) {
            val others = otherUsers(sync)
            val open = others.count { Pairing.verifiedState(sync, it) != "verified" }
            GroupRow(tr("Personen und Einladungen"), Glyph.Person, detail = if (open > 0) tr("{open} nicht verifiziert", "open" to open) else null, divider = false) {
                state.push(Route.People)
            }
        }
        section("text", header = tr("Darstellung"), compact = true, footer = tr("Gilt für den Text in Notizen auf diesem Handy, zusätzlich zur Schriftgröße in den Android-Einstellungen. ") +
            tr("Blocksatz gilt für normal ausgerichtete Absätze, Silbentrennung nach der Sprache des Handys.")) {
            GroupRow(tr("Sprache"), Glyph.Format, detail = io.github.veritasx1.linotes.i18n.I18n.chosen?.let { io.github.veritasx1.linotes.i18n.I18n.LANGUAGES[it] }
                ?: tr("Wie das System")) { languageChoice = true }
            GroupRow(tr("Textgröße"), Glyph.Format, detail = io.github.veritasx1.linotes.data.TEXT_SIZES[textSize].second) { textChoice = true }
            fun toggleJustify() { justify = !justify; sync.justify = justify }
            fun toggleHyphenate() { hyphenate = !hyphenate; sync.hyphenate = hyphenate }
            GroupRow(tr("Blocksatz"), Glyph.Format, chevron = false, trailing = { IosSwitch(justify, tr("Blocksatz")) { toggleJustify() } }) { toggleJustify() }
            GroupRow(tr("Silbentrennung"), Glyph.Format, chevron = false, divider = false,
                trailing = { IosSwitch(hyphenate, tr("Silbentrennung")) { toggleHyphenate() } }) { toggleHyphenate() }
        }
        section("pro", header = tr("Profi-Funktionen"), compact = true, footer = tr("Zusätzliche Werkzeuge für Fortgeschrittene, z. B. Code mit Syntaxfarben, ") +
            tr("Fußnoten und Literaturverzeichnis sowie Formeln (LaTeX). Ab Werk aus, damit LiNotes einfach bleibt. Gilt für dein Konto auf allen Geräten; ") +
            tr("Notizen, die solche Elemente schon enthalten, werden immer richtig angezeigt.")) {
            fun togglePro() { pro = !pro; sync.proFeatures = pro }
            GroupRow(tr("Profi-Funktionen"), Glyph.Gear, chevron = false, divider = false,
                trailing = { IosSwitch(pro, tr("Profi-Funktionen")) { togglePro() } }) { togglePro() }
        }
        section("links", header = tr("Link-Vorschau"), compact = true, footer = tr("Steht eine Webadresse allein in einer Zeile, wird sie zur Vorschau mit Titel und Bild. ") +
            tr("Dafür ruft dieses Handy die Seite ab – der Betreiber sieht dabei die Adresse deines Anschlusses. Die Vorschau liegt verschlüsselt in der Notiz; ") +
            tr("andere Geräte rufen nichts ab. Gesperrte Notizen bekommen keine Vorschau.")) {
            fun toggleLinks() { linkPreviews = !linkPreviews; sync.linkPreviews = linkPreviews }
            GroupRow(tr("Link-Vorschau"), Glyph.Globe, chevron = false, divider = false,
                trailing = { IosSwitch(linkPreviews, tr("Link-Vorschau")) { toggleLinks() } }) { toggleLinks() }
        }
        if (!sync.isLocal) section("keep", header = tr("Auf diesem Handy"), compact = true, footer = tr("So lange bleibt der Inhalt einer Notiz nach der letzten Benutzung auf dem Handy. ") +
            tr("Danach liegt er nur noch verschlüsselt auf dem Server und wird beim Öffnen geladen. Angeheftete Notizen, Listen und Boards bleiben immer hier.")) {
            GroupRow(tr("Notizen behalten"), Glyph.Notes, detail = Keep.label(sync.keepDefault()), divider = false) { keepChoice = true }
        }
        section("security", header = tr("Gesperrte Notizen"), compact = true, footer = tr("Gesperrte Notizen sind zusätzlich mit deinem Notizen-Passwort verschlüsselt. ") +
            tr("Der Server kennt weder das Passwort noch den Inhalt.")) {
            fun toggleBiometric() {
                when {
                    !state.hasVault() -> state.toastLater(tr("Sperre zuerst eine Notiz, um ein Notizen-Passwort festzulegen."))
                    biometricOn -> { state.disableBiometric(); biometricOn = false }
                    state.vaultKey != null -> state.enableBiometric { ok -> biometricOn = ok; if (!ok) state.toastLater(tr("Nicht eingeschaltet.")) }
                    else -> enableBiometric = true
                }
            }
            GroupRow(tr("Fingerabdruck / PIN / Muster"), Glyph.Fingerprint, chevron = false,
                titleColor = if (state.hasVault()) colors.label else colors.tertiary,
                trailing = { IosSwitch(biometricOn, tr("Fingerabdruck / PIN / Muster")) { toggleBiometric() } }) { toggleBiometric() }
            GroupRow(tr("Notizen-Passwort ändern …"), Glyph.Password, titleColor = if (state.hasVault()) colors.label else colors.tertiary) {
                if (state.hasVault()) changeVault = true else state.toastLater(tr("Du hast noch kein Notizen-Passwort festgelegt."))
            }
            GroupRow(tr("Entsperrte Notizen jetzt sperren"), Glyph.Lock, divider = false, chevron = false) {
                state.lockAll()
                state.toastLater(tr("Gesperrte Notizen sind wieder gesperrt."))
            }
        }
        section("about", header = tr("Über"), compact = true, footer = tr("LiNotes 2.0.2 · Ende-zu-Ende verschlüsselt – auf diesem Gerät oder deinem eigenen Server. Keine Werbung, keine Tracker, keine Cloud eines Konzerns.")) {
            GroupRow(tr("Hilfe"), Glyph.Notes) { state.push(Route.Help) }
            GroupRow(if (sync.isLocal) tr("Alle Daten löschen") else tr("Abmelden"), divider = false, chevron = false, titleColor = colors.red) { signOut = true }
        }
    }

    if (keyfile) KeyfileDialog(state) { keyfile = false }
    if (languageChoice) {
        val i18n = io.github.veritasx1.linotes.i18n.I18n
        // Takes effect at the next start – the screens are built once with their texts.
        ActionSheet(tr("Sprache"), (listOf<String?>(null) + i18n.LANGUAGES.keys).map { code ->
            SheetAction((code?.let { i18n.LANGUAGES[it] } ?: tr("Wie das System")) + if (code == i18n.chosen) " ✓" else "") {
                i18n.chosen = code; state.toastLater(tr("Die Sprache wechselt beim nächsten Start von LiNotes."))
            }
        }) { languageChoice = false }
    }
    if (textChoice) {
        ActionSheet(tr("Textgröße in Notizen"), io.github.veritasx1.linotes.data.TEXT_SIZES.mapIndexed { index, (_, label) ->
            SheetAction(label + if (index == textSize) " ✓" else "") { sync.textSize = index; textSize = index }
        }) { textChoice = false }
    }
    if (keepChoice) {
        ActionSheet(tr("Notizen auf dem Handy behalten"), Keep.choices.map { (value, label) ->
            SheetAction(label + if (value == sync.keepDefault()) " ✓" else "") { sync.setKeepDefault(value); sync.evict() }
        }) { keepChoice = false }
    }
    if (enableBiometric) {
        UnlockDialog(state, tr("Gib einmal dein Notizen-Passwort ein."), onDismiss = { enableBiometric = false }) {
            enableBiometric = false
            state.enableBiometric { ok -> biometricOn = ok; if (!ok) state.toastLater(tr("Nicht eingeschaltet.")) }
        }
    }
    if (changeVault) {
        AlertDialog(tr("Notizen-Passwort ändern"), tr("Alle gesperrten Notizen werden neu verschlüsselt."), tr("Ändern"),
            fields = listOf(AlertField(tr("Aktuelles Passwort"), password = true), AlertField(tr("Neues Passwort"), password = true), AlertField(tr("Merkhilfe"))),
            onDismiss = { changeVault = false }) { values ->
            changeVault = false
            scope.launch {
                try {
                    val count = withContext(Dispatchers.Default) { state.changeVaultPassword(values[0], values[1], values[2]) }
                    biometricOn = state.biometricEnabled
                    state.showToast(tr("Geändert, {count} Notizen neu verschlüsselt.", "count" to count))
                } catch (error: Vault.WrongPassword) {
                    state.showToast(tr("Falsches Passwort."))
                }
            }
        }
    }
    if (signOut) {
        AlertDialog(if (sync.isLocal) tr("Alle Daten löschen?") else tr("Abmelden?"),
            if (sync.isLocal) tr("Alle Notizen, Listen und Aufgaben auf diesem Gerät werden endgültig gelöscht.")
            else tr("Auf diesem Gerät wird alles gelöscht. Nicht übertragene Änderungen gehen verloren. ") +
                tr("Hast du deine Schlüsseldatei gesichert oder ein anderes angemeldetes Gerät?"),
            if (sync.isLocal) tr("Löschen") else tr("Abmelden"), destructive = true,
            onDismiss = { signOut = false }) {
            signOut = false
            sync.signOut()
            state.lockAll()
            state.disableBiometric()
            state.signedIn = false
        }
    }
}
