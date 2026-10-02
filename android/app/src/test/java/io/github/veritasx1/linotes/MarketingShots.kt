package io.github.veritasx1.linotes

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.Plans
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState
import io.github.veritasx1.linotes.ui.LiNotesApp
import io.github.veritasx1.linotes.ui.Route
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.LocalDate

/**
 * Pictures for the homepage and the help: the app with demo data (local mode, no server, no
 * personal data). Only runs with -Pshots=<folder>:
 *   ./gradlew testDebugUnitTest --tests '*MarketingShots*' -Pshots=/tmp/shots
 */
@RunWith(org.robolectric.RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
class MarketingShots {
    @get:Rule val compose = createComposeRule()
    private val out: String? = System.getProperty("linotes.shots")

    private fun block(type: String, text: String, vararg extra: Pair<String, Any>) =
        JSONObject().put("t", type).put("x", text).also { b -> extra.forEach { (k, v) -> b.put(k, v) } }

    private fun span(text: String, part: String, name: String) =
        JSONArray().put(JSONArray().put(text.indexOf(part)).put(text.indexOf(part) + part.length).put(name))

    private fun seed(sync: SyncEngine): Map<String, String> {
        sync.startLocal("Olaf")
        Model.ensureDefaults(sync)
        val uid = sync.userId
        val now = Model.now()
        fun folder(name: String, order: Int) = sync.put("folder", JSONObject().put("name", name).put("order", order)).id
        val reisen = folder("Reisen", 1)
        val rezepte = folder("Rezepte", 2)
        val haushalt = folder("Haushalt", 3)
        fun note(folderId: String, minutesAgo: Int, vararg blocks: JSONObject, pinned: Boolean = false): String {
            val data = JSONObject().put("folder", folderId).put("body", JSONArray(blocks.toList()))
                .put("created", now - minutesAgo * 60 - 3600).put("modified", now - minutesAgo * 60)
            if (pinned) data.put("pinned", true)
            return sync.put("note", data).id
        }
        val tour = note(reisen, 95, block("title", "Radtour Kühlungsborn"), block("body", "Rund 42 km, flach und fast immer am Wasser."),
            block("number", "Start am Bahnhof Kühlungsborn West"), block("number", "Steilküste bis Heiligendamm"),
            block("number", "Mittag im Café am Kamp"), block("number", "Zurück durch den Gespensterwald"))
        val intro = "Freitag nach der Arbeit los, Rückfahrt Sonntagabend. Zimmer mit Meerblick ist reserviert."
        val link = "Route: Radtour Kühlungsborn"
        val calc = "240 + 78 + 120 = 438"
        val hero = note(reisen, 3,
            block("title", "Wochenende an der Ostsee"),
            block("body", intro, "s" to span(intro, "Zimmer mit Meerblick", "h:mint")),
            block("heading", "Packliste"),
            block("check", "Badesachen und Handtücher", "c" to true), block("check", "Sonnencreme", "c" to true),
            block("check", "Fahrradschloss und Helm"), block("check", "Ladekabel und Powerbank"),
            block("heading", "Budget"),
            Model.tableBlock(listOf(listOf("Posten", "Betrag", "Wer"), listOf("Unterkunft", "240 €", "Anna"), listOf("Bahn", "78 €", "Olaf"), listOf("Essen", "120 €", "beide"))),
            block("body", calc, "s" to span(calc, "438", "b")),
            block("body", link, "s" to span(link, "Radtour Kühlungsborn", "n:$tour")), pinned = true)
        val cake = note(rezepte, 60 * 26, block("title", "Omas Apfelkuchen"), block("subheading", "Zutaten"),
            block("bullet", "6 säuerliche Äpfel"), block("bullet", "200 g Butter, 180 g Zucker"), block("bullet", "3 Eier, 300 g Mehl, Backpulver"),
            block("subheading", "Zubereitung"), block("number", "Butter und Zucker schaumig schlagen."), block("number", "Mehl und Backpulver unterheben."),
            block("number", "Äpfel einritzen, auf den Teig setzen."), block("number", "45 Minuten bei 180 °C backen."),
            block("quote", "Mit Sahne servieren – Oma bestand darauf."))
        note(haushalt, 60 * 5, block("title", "Haushaltsbuch Oktober"), block("body", "Miete 850 + Strom 74 + Internet 35 = 959"),
            block("body", "Lebensmittel 412 / 2 = 206"), block("body", "Sparrate 959 * 0,1 = 95,9"))
        val audio = sync.uploadFile(ByteArray(2048) { it.toByte() }, null)
        val meetingText = "Kurz besprochen: Lieferung kommt Dienstag, Anna übernimmt die Abholung."
        val meeting = note(Model.privateFolder(uid), 40, block("title", "Elternabend 2b"),
            block("body", meetingText, "s" to span(meetingText, "Dienstag", "b")),
            JSONObject().put("t", "file").put("f", audio).put("n", "Aufnahme.ogg").put("m", "audio/ogg").put("b", 214000).put("d", 512.4),
            JSONObject().put("t", "divider"),
            block("check", "Unterschrift bis Freitag abgeben"), block("check", "10 € Busgeld mitgeben"))
        note(Model.privateFolder(uid), 60 * 30, block("title", "Geschenkideen"), block("heading", "Anna"), block("bullet", "Kochkurs Thai"),
            block("bullet", "Konzertkarten"), block("heading", "Ben"), block("bullet", "Kletterhalle – Zehnerkarte"))
        note(Model.privateFolder(uid), 60 * 50, block("title", "Zählerstände"), block("body", "Strom 24 518 kWh · Gas 8 214 m³ · Wasser 312 m³"))

        val list = Model.defaultList(uid)
        listOf("Hafermilch" to false, "Äpfel (Boskop)" to false, "Vollkornbrot" to false, "Kaffeebohnen" to false, "Basilikum" to false,
            "Butter" to true).forEachIndexed { index, (text, done) ->
            sync.put("item", JSONObject().put("list", list).put("text", text).put("done", done).put("order", now + index * 0.001).put("by", uid))
        }
        val board = Model.defaultBoard(uid)
        val columns = sync.all("column").filter { it.data.optString("board") == board }.associate { it.data.optString("name") to it.id }
        listOf(Triple("Offen", "Steuererklärung abgeben", "hoch"), Triple("Offen", "Fahrrad zur Inspektion", "mittel"),
            Triple("Offen", "Fenster putzen", ""), Triple("In Arbeit", "Gartenhaus planen", "mittel"),
            Triple("Erledigt", "Geburtstagsgeschenk für Anna", "")).forEachIndexed { order, (column, title, priority) ->
            val card = JSONObject().put("board", board).put("column", columns.getValue(column)).put("title", title).put("order", order)
                .put("created", now).put("created_by", uid)
            if (priority.isNotEmpty()) card.put("priority", priority)
            sync.put("card", card)
        }
        val today = LocalDate.now()
        val putz = Plans.template("putzplan").put("name", "Putzplan WG").put("order", 1)
        putz.put("rot", JSONObject().put("people", JSONArray(listOf("Olaf", "Anna", "Ben"))).put("start", Plans.monday(today).toString()))
        val putzId = sync.put("plan", Plans.setCell(putz, 2, 1, "Ben (Urlaub)", "yellow")).id
        val start = Plans.monday(today).minusDays(7)
        fun task(name: String, from: Long, to: Long, color: String, milestone: Boolean = false) = JSONObject().put("x", name)
            .put("from", start.plusDays(from).toString()).put("to", start.plusDays(to).toString()).put("k", color).also { if (milestone) it.put("m", true) }
        val projekt = sync.put("plan", JSONObject().put("name", "Gartenhaus bauen").put("order", 3).put("mode", "timeline").put("tasks", JSONArray(listOf(
            task("Planung", 0, 9, "blue"), task("Fundament", 10, 13, "grey"), task("Material", 14, 14, "pink", true),
            task("Aufbau", 15, 26, "orange"), task("Streichen", 24, 30, "mint"), task("Einweihung", 33, 33, "purple", true))))).id
        var schicht = Plans.template("schichtplan").put("name", "Dienstplan Station 3").put("order", 4).put("rows", JSONArray(listOf("Lena", "Murat", "Sabine", "Tom")))
        val pattern = listOf(listOf("Früh", "Früh", "Spät", "Spät", "Frei", "Nacht", "Nacht"), listOf("Spät", "Spät", "Frei", "Früh", "Früh", "Frei", "Frei"),
            listOf("Nacht", "Nacht", "Frei", "Frei", "Spät", "Spät", "Früh"), listOf("Frei", "Früh", "Früh", "Nacht", "Nacht", "Frei", "Spät"))
        val shiftColors = mapOf("Früh" to "yellow", "Spät" to "blue", "Nacht" to "purple", "Frei" to "grey")
        schicht.put("cells", JSONArray())
        pattern.forEachIndexed { r, row -> row.forEachIndexed { c, value -> schicht = Plans.setCell(schicht, r, c, value, shiftColors.getValue(value)) } }
        val schichtId = sync.put("plan", schicht).id
        return mapOf("hero" to hero, "cake" to cake, "meeting" to meeting, "reisen" to reisen, "list" to list, "board" to board,
            "putz" to putzId, "projekt" to projekt, "schicht" to schichtId)
    }

    private fun shots(prefix: String) {
        assumeTrue(out != null)
        val sync = SyncEngine(ApplicationProvider.getApplicationContext())
        val ids = seed(sync)
        val state = AppState(sync).apply { signedIn = true }
        compose.setContent { LiNotesApp(state) }
        fun shot(name: String, tab: Int, vararg routes: Route) {
            compose.runOnUiThread {
                state.openTab(tab)
                while (state.stacks[tab].size > 1) state.stacks[tab].removeAt(state.stacks[tab].lastIndex)
                routes.forEach { state.push(it) }
            }
            compose.mainClock.advanceTimeBy(1500)
            compose.waitForIdle()
            compose.onRoot().captureRoboImage("$out/$prefix$name.png")
        }
        shot("a-ordner", 0)
        shot("b-notizen", 0, Route.NoteList("folder:" + ids.getValue("reisen")))
        shot("c-notiz", 0, Route.NoteList("folder:" + ids.getValue("reisen")), Route.Editor(ids.getValue("hero")))
        shot("d-rezept", 0, Route.Editor(ids.getValue("cake")))
        shot("e-audio", 0, Route.Editor(ids.getValue("meeting")))
        shot("f-liste", 1, Route.ListDetail(ids.getValue("list")))
        shot("g-board", 2, Route.Board(ids.getValue("board")))
        shot("h-plaene", 3)
        shot("i-putzplan", 3, Route.Plan(ids.getValue("putz")))
        shot("j-projektplan", 3, Route.Plan(ids.getValue("projekt")))
        shot("k-dienstplan", 3, Route.Plan(ids.getValue("schicht")))
        shot("l-einstellungen", 0, Route.Settings)
    }

    @Test fun start() {
        assumeTrue(out != null)
        val state = AppState(SyncEngine(ApplicationProvider.getApplicationContext())).apply { signedIn = false }
        compose.setContent { LiNotesApp(state) }
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("$out/android-m-start.png")
    }

    @Test fun light() = shots("android-")

    @Test fun dark() {
        RuntimeEnvironment.setQualifiers("+night")
        shots("android-dark-")
    }
}
