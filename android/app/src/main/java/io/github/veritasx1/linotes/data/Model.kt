package io.github.veritasx1.linotes.data

import io.github.veritasx1.linotes.i18n.I18n
import io.github.veritasx1.linotes.i18n.tr

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/** Helpers shared by the screens, mirroring linux/linotes/model.py. */
object Model {
    // --- templates (Vorlagen), the same as model.py ---
    private val WEEKDAY_NAMES = listOf(tr("Montag"), tr("Dienstag"), tr("Mittwoch"), tr("Donnerstag"), tr("Freitag"), tr("Samstag"), tr("Sonntag"))
    private val PLACEHOLDER = Regex("\\{\\{(Datum|Uhrzeit|Wochentag)\\}\\}")
    private fun t(kind: String, text: String = "") = JSONObject().put("t", kind).put("x", text)

    /** Shipped templates: key, name, blocks (fresh copies on every call). */
    val BUILTIN_TEMPLATES: List<Triple<String, String, List<JSONObject>>> get() = listOf(
        Triple("besprechung", tr("Besprechung"), listOf(t("title", tr("Besprechung {{Datum}}")), t("body", tr("{{Wochentag}}, {{Datum}}, {{Uhrzeit}} Uhr")),
            t("heading", tr("Teilnehmer")), t("bullet"), t("heading", tr("Themen")), t("number"), t("heading", tr("Beschlüsse")), t("body"),
            t("heading", tr("Aufgaben")), t("check"))),
        Triple("protokoll", tr("Protokoll"), listOf(t("title", tr("Protokoll {{Datum}}")), t("body", tr("Ort: ")), t("body", tr("Anwesend: ")),
            t("heading", tr("Verlauf")), t("body"), t("heading", tr("Ergebnisse")), t("bullet"))),
        Triple("reise", tr("Reisecheckliste"), listOf(t("title", tr("Packliste")), t("heading", tr("Dokumente")), t("check", tr("Ausweis oder Reisepass")),
            t("check", tr("Tickets")), t("check", tr("Versicherungskarte")), t("heading", tr("Kleidung")), t("check"), t("heading", tr("Technik")),
            t("check", tr("Ladegerät")), t("check", tr("Kopfhörer")), t("heading", tr("Vor der Abreise")), t("check", tr("Pflanzen gießen")),
            t("check", tr("Fenster schließen")))),
        Triple("tagebuch", tr("Tagebuch"), listOf(t("title", tr("{{Wochentag}}, {{Datum}}")), t("body"))),
    )

    /** A copy of the blocks with {{Datum}}, {{Uhrzeit}}, {{Wochentag}} filled in; formatting spans move with the text. */
    fun fillTemplate(blocks: List<JSONObject>, now: java.time.LocalDateTime): List<JSONObject> {
        val values = mapOf("Datum" to "%02d.%02d.%d".format(now.dayOfMonth, now.monthValue, now.year),
            "Uhrzeit" to "%02d:%02d".format(now.hour, now.minute), "Wochentag" to WEEKDAY_NAMES[now.dayOfWeek.value - 1])
        return blocks.map { original ->
            val block = JSONObject(original.toString())
            val text = block.optString("x")
            val matches = PLACEHOLDER.findAll(text).toList()
            if (matches.isEmpty()) return@map block
            val out = StringBuilder()
            var last = 0
            val shifts = mutableListOf<Pair<Int, Int>>()   // (end of placeholder, change in length)
            for (match in matches) {
                out.append(text, last, match.range.first)
                val value = values.getValue(match.groupValues[1])
                out.append(value)
                shifts.add(match.range.last + 1 to value.length - match.value.length)
                last = match.range.last + 1
            }
            out.append(text.substring(last))
            block.put("x", out.toString())
            block.optJSONArray("s")?.let { spans ->
                for (i in 0 until spans.length()) {
                    val span = spans.optJSONArray(i) ?: continue
                    for (position in 0..1) {
                        val at = span.optInt(position)
                        span.put(position, at + shifts.filter { at >= it.first }.sumOf { it.second })
                    }
                }
            }
            block
        }
    }

    const val FOOTNOTE = "fn:"

    /** The text of a footnote span ("fn:<text>") – a Profi-Funktion – otherwise null. */
    fun footnoteText(name: String?): String? = if (name != null && name.startsWith(FOOTNOTE)) name.substring(FOOTNOTE.length) else null

    /** The footnote texts of a note in reading order (as numbered in the text) – the same as model.footnotes. */
    fun footnotes(blocks: List<org.json.JSONObject>): List<String> = blocks.flatMap { block ->
        val spans = block.optJSONArray("s") ?: return@flatMap emptyList<String>()
        (0 until spans.length()).mapNotNull { spans.optJSONArray(it) }.filter { it.length() == 3 }.sortedBy { it.optInt(0) }
            .mapNotNull { footnoteText(it.optString(2)) }
    }

    /** In the archive (notes, lists, boards, plans) – a mark on the object, so for everyone it is shared with. */
    fun archived(obj: SyncObject?): Boolean = obj?.data?.has("archived") == true

    fun setArchived(sync: SyncEngine, id: String, on: Boolean) {
        sync.update(id) { if (on) it.put("archived", now()) else it.remove("archived") }
    }

    /** Everything a card can be found by: id, title, notes, impact, verification, version, commits,
     *  file and evidence names, the person in charge – lower case (the same as model.card_search_text). */
    fun cardSearchText(card: SyncObject, userName: ((Int) -> String)? = null): String {
        val data = card.data
        val parts = mutableListOf(card.id)
        for (key in listOf("title", "notes", "impact", "verification", "version")) data.optString(key).takeIf { it.isNotEmpty() && it != "null" }?.let { parts.add(it) }
        data.optJSONArray("commits")?.let { list -> for (i in 0 until list.length()) list.optJSONObject(i)?.let { parts.add(it.optString("h") + " " + it.optString("m")) } }
        for (key in listOf("files", "evidence")) data.optJSONArray(key)?.let { list -> for (i in 0 until list.length()) list.optJSONObject(i)?.optString("n")?.let { parts.add(it) } }
        if (userName != null && data.has("assignee") && !data.isNull("assignee")) parts.add(userName(data.optInt("assignee")))
        return parts.joinToString(" ").lowercase()
    }

    /** Every word of the query is somewhere in the card. */
    fun cardMatches(card: SyncObject, query: String, userName: ((Int) -> String)? = null): Boolean {
        val words = query.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.isEmpty()) return true
        val text = cardSearchText(card, userName)
        return words.all { it in text }
    }


    private val tagPattern = Regex("(?<![\\w#])#(\\p{L}[\\p{L}\\p{N}_-]{0,40})")

    fun blocks(note: SyncObject): JSONArray = note.data.optJSONArray("body") ?: JSONArray()

    fun isLocked(note: SyncObject) = note.data.has("enc")

    fun blocksTitle(blocks: JSONArray): String {
        for (index in 0 until blocks.length()) {
            val text = blocks.optJSONObject(index)?.optString("x")?.trim().orEmpty()
            if (text.isNotEmpty()) return text.take(120)
        }
        return ""
    }

    fun title(note: SyncObject): String {
        // Locked notes keep their title visible, like in Apple's Notes.
        if (isLocked(note)) return note.data.optString("title").ifEmpty { tr("Gesperrte Notiz") }
        val body = blocks(note)
        for (index in 0 until body.length()) {
            val text = body.optJSONObject(index)?.optString("x")?.trim().orEmpty()
            if (text.isNotEmpty()) return text.take(120)
        }
        return note.data.optString("title").ifEmpty { tr("Neue Notiz") }
    }

    fun preview(note: SyncObject): String {
        if (isLocked(note)) return ""
        if (note.evicted) return note.data.optString("preview")
        val body = blocks(note)
        val lines = (0 until body.length()).mapNotNull { body.optJSONObject(it)?.optString("x")?.trim() }.filter { it.isNotEmpty() }
        return lines.drop(1).joinToString(" ").take(160)
    }

    fun image(note: SyncObject): String? {
        if (isLocked(note)) return null
        val body = blocks(note)
        for (index in 0 until body.length()) {
            val block = body.optJSONObject(index) ?: continue
            if (block.optString("t") == "image" && block.optString("f").isNotEmpty()) return block.optString("f")
        }
        return null
    }

    const val NOTE_LINK = "n:"

    /** The note id of a note link span ("n:<id>"), otherwise null. */
    fun linkTarget(spanName: String): String? = if (spanName.startsWith(NOTE_LINK)) spanName.substring(NOTE_LINK.length) else null

    /** Note links show the current title of the linked note (like Apple's Notes); a gone
     *  note (titleOf returns null) keeps the old text. Returns the block itself if nothing changed. */
    const val MENTION = "m:"

    /** The user id of an @-mention span ("m:<id>"), otherwise null. */
    fun mentionTarget(spanName: String): Int? = if (spanName.startsWith(MENTION)) spanName.substring(MENTION.length).toIntOrNull() else null

    /** How often [userId] is @-mentioned in the blocks (for notifications). */
    fun mentionsOf(blocks: JSONArray, userId: Int): Int {
        var count = 0
        for (index in 0 until blocks.length()) {
            val spans = blocks.optJSONObject(index)?.optJSONArray("s") ?: continue
            for (spanIndex in 0 until spans.length()) if (mentionTarget(spans.optJSONArray(spanIndex)?.optString(2).orEmpty()) == userId) count++
        }
        return count
    }

    fun refreshNoteLinks(block: JSONObject, titleOf: (String) -> String?, nameOf: (Int) -> String? = { null }): JSONObject {
        val spans = block.optJSONArray("s") ?: return block
        var text = block.optString("x")
        val links = mutableListOf<Triple<Int, Int, String>>()
        for (index in 0 until spans.length()) {
            val span = spans.optJSONArray(index) ?: continue
            val target = linkTarget(span.optString(2))
            val person = mentionTarget(span.optString(2))
            val start = span.optInt(0).coerceIn(0, text.length)
            val end = span.optInt(1).coerceIn(start, text.length)
            val title = when {
                target != null -> titleOf(target)
                person != null -> nameOf(person)?.takeIf { it != "?" }?.let { "@$it" }
                else -> null
            } ?: continue
            if (title != text.substring(start, end)) links.add(Triple(start, end, title))
        }
        if (links.isEmpty()) return block
        val list = (0 until spans.length()).mapNotNull { spans.optJSONArray(it) }.filter { it.length() == 3 }
            .map { arrayOf<Any>(it.optInt(0), it.optInt(1), it.optString(2)) }
        // Back to front, so the offsets of earlier links stay valid.
        for ((start, end, title) in links.sortedByDescending { it.first }) {
            text = text.substring(0, start) + title + text.substring(end)
            val delta = title.length - (end - start)
            for (span in list) {
                val from = span[0] as Int
                val to = span[1] as Int
                span[0] = if (from >= end) from + delta else if (from > start) start else from
                span[1] = if (to >= end) to + delta else if (to > start) start + title.length else to
            }
        }
        val result = JSONArray()
        list.filter { (it[0] as Int) < (it[1] as Int) }.sortedWith(compareBy({ it[0] as Int }, { it[1] as Int }))
            .forEach { result.put(JSONArray().put(it[0]).put(it[1]).put(it[2])) }
        return JSONObject(block.toString()).put("x", text).put("s", result)
    }

    /** Notes offered after typing ">>": newest first, filtered by the typed text. */
    fun linkChoices(notes: List<SyncObject>, exclude: String?, query: String, limit: Int = 8): List<SyncObject> {
        val needle = query.trim().lowercase()
        return notes.filter { it.id != exclude && !it.data.has("trashed") && (needle.isEmpty() || needle in title(it).lowercase()) }
            .sortedByDescending { modified(it) }.take(limit)
    }

    fun text(note: SyncObject): String {
        val body = blocks(note)
        return (0 until body.length()).joinToString("\n") { body.optJSONObject(it)?.optString("x").orEmpty() }
    }

    fun tags(note: SyncObject): Set<String> {
        if (isLocked(note)) return emptySet()
        return tagPattern.findAll(text(note)).map { it.groupValues[1].lowercase() }.toSet()
    }

    // --- tables (like Apple's): {"t": "table", "r": [["A", "B"], ["C", "D"]], "x": "A | B\nC | D"} ---
    // "x" is the same as plain text for search, previews and older versions. Same as Ubuntu's model.py.

    /** The cells as a rectangle of strings (missing cells filled in, at least 1×1). */
    fun tableRows(block: JSONObject): List<List<String>> {
        val array = block.optJSONArray("r") ?: JSONArray()
        val rows = (0 until array.length()).mapNotNull { index -> array.optJSONArray(index)?.let { row -> (0 until row.length()).map { row.optString(it) } } }
        val width = rows.maxOfOrNull { it.size }?.takeIf { it > 0 } ?: 1
        return rows.map { it + List(width - it.size) { "" } }.ifEmpty { listOf(listOf("")) }
    }

    fun tableText(rows: List<List<String>>) = rows.joinToString("\n") { it.joinToString(" | ") }

    fun tableBlock(rows: List<List<String>>): JSONObject {
        val clean = tableRows(JSONObject().put("r", JSONArray(rows.map { JSONArray(it) })))
        return JSONObject().put("t", "table").put("r", JSONArray(clean.map { JSONArray(it) })).put("x", tableText(clean))
    }

    fun newTable(columns: Int = 3, rows: Int = 3) = tableBlock(List(rows) { List(columns) { "" } })

    /** Nothing typed, no picture, file or divider (whitespace does not count). */
    fun isEmptyBody(blocks: JSONArray): Boolean = (0 until blocks.length()).all { index ->
        val block = blocks.optJSONObject(index) ?: return@all true
        block.optString("t", "body") !in setOf("image", "file", "divider", "table") && block.optString("x").isBlank()
    }

    /** One comparable string per block (text, or the kind and file for images and files). */
    fun blockLines(blocks: JSONArray): List<String> = (0 until blocks.length()).map { index ->
        val block = blocks.optJSONObject(index) ?: JSONObject()
        "${block.optString("t")}:${block.optString("x")}${block.optString("f")}"
    }

    /** Indices in [new] of lines that are new or changed compared to [old] (longest common
     *  subsequence, like a diff). Mirrors model.changed_lines on Ubuntu. */
    fun changedLines(old: List<String>, new: List<String>): List<Int> {
        val n = old.size
        val m = new.size
        val length = Array(n + 1) { IntArray(m + 1) }
        for (i in n - 1 downTo 0) for (j in m - 1 downTo 0) {
            length[i][j] = if (old[i] == new[j]) length[i + 1][j + 1] + 1 else maxOf(length[i + 1][j], length[i][j + 1])
        }
        val kept = mutableSetOf<Int>()
        var i = 0
        var j = 0
        while (i < n && j < m) {
            when {
                old[i] == new[j] -> { kept.add(j); i++; j++ }
                length[i + 1][j] >= length[i][j + 1] -> i++
                else -> j++
            }
        }
        return (0 until m).filter { it !in kept }
    }

    fun modified(obj: SyncObject): Double = obj.data.optDouble("modified", obj.updated).let { if (it.isNaN()) obj.updated else it }

    private val months = listOf(tr("Januar"), tr("Februar"), tr("März"), tr("April"), tr("Mai"), tr("Juni"), tr("Juli"), tr("August"),
        tr("September"), tr("Oktober"), tr("November"), tr("Dezember"))
    private val weekdays = listOf(tr("Montag"), tr("Dienstag"), tr("Mittwoch"), tr("Donnerstag"), tr("Freitag"), tr("Samstag"), tr("Sonntag"))

    private fun date(seconds: Double): LocalDate =
        Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault()).toLocalDate()

    fun created(obj: SyncObject): Double = obj.data.optDouble("created", Double.NaN).let { if (it.isNaN()) modified(obj) else it }

    val NOTE_SORTS = listOf("modified" to tr("Bearbeitungsdatum"), "created" to tr("Erstellungsdatum"), "title" to tr("Titel"))

    class Sorted(val note: SyncObject, val group: String, val stamp: Double)

    /** Like Apple (and linux/linotes/model.py sort_notes): pinned first, then edit date,
     *  creation date (newest first, grouped by day) or title (A–Z, no date groups). */
    fun sortNotes(notes: List<SyncObject>, order: String, pinnedFirst: Boolean = true): List<Sorted> {
        val stamp: (SyncObject) -> Double = if (order == "created") ::created else ::modified
        val pinned = if (pinnedFirst) notes.filter { it.data.optBoolean("pinned") && !it.data.has("trashed") } else emptyList()
        val others = notes - pinned.toSet()
        fun arrange(part: List<SyncObject>) =
            if (order == "title") part.sortedBy { title(it).lowercase() } else part.sortedByDescending(stamp)
        return arrange(pinned).map { Sorted(it, tr("Angeheftet"), stamp(it)) } + arrange(others).map {
            Sorted(it, if (order == "title") (if (pinned.isNotEmpty()) tr("Notizen") else "") else dateGroup(stamp(it)), stamp(it))
        }
    }

    fun dateGroup(seconds: Double): String {
        val today = LocalDate.now()
        val day = date(seconds)
        val delta = ChronoUnit.DAYS.between(day, today)
        return when {
            delta <= 0 -> tr("Heute")
            delta == 1L -> tr("Gestern")
            delta < 7 -> tr("Vorherige 7 Tage")
            delta < 30 -> tr("Vorherige 30 Tage")
            day.year == today.year -> months[day.monthValue - 1]
            else -> "${months[day.monthValue - 1]} ${day.year}"
        }
    }

    fun shortDate(seconds: Double): String {
        val moment = Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault())
        val delta = ChronoUnit.DAYS.between(moment.toLocalDate(), LocalDate.now())
        return when {
            delta <= 0 -> moment.format(DateTimeFormatter.ofPattern("HH:mm"))
            delta == 1L -> tr("Gestern")
            delta < 7 -> weekdays[moment.dayOfWeek.value - 1]
            else -> moment.format(DateTimeFormatter.ofPattern("dd.MM.yy"))
        }
    }

    fun longDate(seconds: Double): String {
        val moment = Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault())
        return tr("{dayOfMonth}. {value} {year} um {value2}", "dayOfMonth" to moment.dayOfMonth, "value" to (months[moment.monthValue - 1]), "year" to moment.year, "value2" to (moment.format(DateTimeFormatter.ofPattern("HH:mm"))))
    }

    fun now() = System.currentTimeMillis() / 1000.0

    // --- defaults (same stable ids as on Linux; everything starts private) ---

    fun privateFolder(userId: Int) = "notes-$userId"
    fun defaultList(userId: Int) = "list-$userId"
    fun defaultBoard(userId: Int) = "board-$userId"
    val defaultColumns = listOf("offen" to tr("Offen"), "arbeit" to tr("In Arbeit"), "fertig" to tr("Erledigt"))

    fun ensureDefaults(sync: SyncEngine) {
        val userId = sync.userId
        if (userId == 0) return
        if (!sync.exists(privateFolder(userId)))
            sync.put("folder", JSONObject().put("name", tr("Notizen")).put("order", 0), null, privateFolder(userId))
        if (!sync.exists(defaultList(userId)))
            sync.put("list", JSONObject().put("name", tr("Einkaufsliste")).put("grocery", true).put("order", 0), null, defaultList(userId))
        val board = defaultBoard(userId)
        if (!sync.exists(board)) {
            sync.put("board", JSONObject().put("name", tr("Aufgaben")).put("order", 0), null, board)
            defaultColumns.forEachIndexed { order, (key, name) ->
                sync.put("column", JSONObject().put("board", board).put("name", name).put("order", order), null, "$board-$key")
            }
        }
    }

    // --- groceries -------------------------------------------------

    private val groceries = listOf(
        "Obst & Gemüse" to listOf("apfel", "äpfel", "banane", "birne", "orange", "zitrone", "limette", "traube", "beere",
            "erdbeer", "himbeer", "heidelbeer", "kirsche", "pfirsich", "nektarine", "mango", "ananas", "kiwi", "melone",
            "pflaume", "tomate", "gurke", "salat", "paprika", "zwiebel", "knoblauch", "kartoffel", "möhre", "karotte",
            "zucchini", "aubergine", "brokkoli", "blumenkohl", "kohl", "spinat", "lauch", "porree", "sellerie", "pilz",
            "champignon", "avocado", "ingwer", "petersilie", "schnittlauch", "basilikum", "radieschen", "rucola", "mais",
            "kürbis", "obst", "gemüse", "kräuter", "fenchel", "spargel", "rote bete"),
        "Brot & Backwaren" to listOf("brot", "brötchen", "toast", "baguette", "croissant", "brezel", "kuchen", "zwieback",
            "knäcke", "semmel", "laugen", "wrap", "tortilla"),
        "Milchprodukte & Eier" to listOf("milch", "butter", "käse", "joghurt", "quark", "sahne", "schmand", "creme fraiche",
            "crème fraîche", "frischkäse", "mozzarella", "parmesan", "feta", "ei", "eier", "margarine", "kefir", "buttermilch",
            "skyr", "gouda"),
        "Fleisch & Fisch" to listOf("fleisch", "hähnchen", "huhn", "pute", "rind", "schwein", "hack", "wurst", "schinken",
            "salami", "speck", "bacon", "würstchen", "fisch", "lachs", "thunfisch", "garnele", "aufschnitt", "steak",
            "schnitzel", "leberwurst"),
        "Tiefkühl" to listOf("tk", "tiefkühl", "eis", "speiseeis", "vanilleeis", "schokoeis", "eiscreme", "eis am stiel",
            "pizza", "pommes", "fischstäbchen", "gefroren"),
        "Vorrat" to listOf("nudel", "spaghetti", "reis", "mehl", "zucker", "salz", "öl", "essig", "linsen", "bohnen",
            "kichererbsen", "dose", "konserve", "müsli", "haferflocken", "cornflakes", "honig", "marmelade", "nutella",
            "erdnussbutter", "backpulver", "hefe", "brühe", "tomatenmark", "passierte", "polenta", "couscous", "quinoa",
            "olivenöl", "rapsöl", "sonnenblumenöl"),
        "Gewürze & Soßen" to listOf("pfeffer", "gewürz", "paprikapulver", "curry", "ketchup", "senf", "mayo", "soße",
            "sauce", "sojasauce", "zimt", "oregano", "chili", "vanille"),
        "Getränke" to listOf("wasser", "saft", "cola", "limo", "bier", "wein", "sekt", "kaffee", "tee", "sprudel",
            "schorle", "kakao", "energy", "eistee", "milchshake"),
        "Süßes & Snacks" to listOf("schokolade", "chips", "keks", "gummibär", "bonbon", "nüsse", "nuss", "cracker",
            "riegel", "popcorn", "salzstangen", "süßigkeit"),
        "Drogerie" to listOf("zahnpasta", "zahnbürste", "shampoo", "duschgel", "seife", "deo", "creme", "rasier",
            "taschentuch", "toilettenpapier", "klopapier", "watte", "pflaster", "tampon", "binde", "windel",
            "sonnencreme", "spülung"),
        "Haushalt" to listOf("spülmittel", "waschmittel", "müllbeutel", "müllsack", "küchenrolle", "schwamm", "reiniger",
            "alufolie", "frischhaltefolie", "backpapier", "batterie", "glühbirne", "spültabs", "tabs", "weichspüler",
            "kerze", "servietten"),
        "Tierbedarf" to listOf("katzenfutter", "hundefutter", "futter", "katzenstreu", "leckerli"),
    )

    /** The same aisles for English and French lists (keys stay German) – generated from Ubuntu's model.GROCERY_WORDS;
     *  only the app language's words count ("pommes" are apples in French, chips in German). */
    val groceryWords: Map<String, Map<String, List<String>>> = mapOf(
        "en" to mapOf(
            "Obst & Gemüse" to listOf("apple", "banana", "pear", "orange", "lemon", "lime", "grape", "berry", "berries", "strawberr", "raspberr", "blueberr", "cherr", "peach", "nectarine", "mango", "pineapple", "kiwi", "melon", "plum", "tomato", "cucumber", "lettuce", "salad", "pepper", "onion", "garlic", "potato", "carrot", "courgette", "zucchini", "aubergine", "eggplant", "broccoli", "cauliflower", "cabbage", "spinach", "leek", "celery", "mushroom", "avocado", "ginger", "parsley", "chives", "basil", "radish", "rocket", "arugula", "sweetcorn", "corn", "pumpkin", "fruit", "veg", "herbs", "fennel", "asparagus", "beetroot"),
            "Brot & Backwaren" to listOf("bread", "roll", "toast", "baguette", "croissant", "pretzel", "cake", "bagel", "muffin", "crispbread", "wrap", "tortilla", "loaf", "wholemeal"),
            "Milchprodukte & Eier" to listOf("milk", "butter", "cheese", "yoghurt", "yogurt", "quark", "cream", "creme fraiche", "crème fraîche", "cream cheese", "mozzarella", "parmesan", "feta", "egg", "eggs", "margarine", "kefir", "buttermilk", "skyr", "cheddar"),
            "Fleisch & Fisch" to listOf("meat", "chicken", "turkey", "beef", "pork", "mince", "sausage", "ham", "salami", "bacon", "fish", "salmon", "tuna", "prawn", "shrimp", "cold cuts", "steak", "lamb"),
            "Tiefkühl" to listOf("frozen", "ice cream", "ice lolly", "pizza", "chips", "fries", "fish fingers", "peas"),
            "Vorrat" to listOf("pasta", "spaghetti", "noodle", "rice", "flour", "sugar", "salt", "oil", "vinegar", "lentil", "beans", "chickpea", "tin", "can", "cereal", "muesli", "oats", "porridge", "cornflakes", "honey", "jam", "peanut butter", "baking powder", "yeast", "stock", "tomato paste", "passata", "couscous", "quinoa", "olive oil"),
            "Gewürze & Soßen" to listOf("spice", "paprika", "curry", "ketchup", "mustard", "mayo", "sauce", "soy sauce", "cinnamon", "oregano", "chilli", "chili", "vanilla", "seasoning"),
            "Getränke" to listOf("water", "juice", "cola", "lemonade", "beer", "wine", "prosecco", "coffee", "tea", "sparkling", "cocoa", "energy drink", "iced tea", "smoothie", "squash"),
            "Süßes & Snacks" to listOf("chocolate", "crisps", "biscuit", "cookie", "sweets", "candy", "nuts", "cracker", "bar", "popcorn", "pretzels", "snack"),
            "Drogerie" to listOf("toothpaste", "toothbrush", "shampoo", "shower gel", "soap", "deodorant", "lotion", "razor", "tissues", "toilet paper", "toilet roll", "cotton", "plaster", "tampon", "pad", "nappies", "diaper", "sunscreen", "conditioner"),
            "Haushalt" to listOf("washing-up liquid", "dish soap", "detergent", "laundry", "bin bag", "trash bag", "kitchen roll", "paper towel", "sponge", "cleaner", "foil", "cling film", "baking paper", "battery", "batteries", "light bulb", "dishwasher", "tablets", "fabric softener", "candle", "napkins"),
            "Tierbedarf" to listOf("cat food", "dog food", "pet food", "cat litter", "treats")),
        "fr" to mapOf(
            "Obst & Gemüse" to listOf("pomme", "banane", "poire", "orange", "citron", "raisin", "fraise", "framboise", "myrtille", "cerise", "pêche", "nectarine", "mangue", "ananas", "kiwi", "melon", "prune", "tomate", "concombre", "salade", "laitue", "poivron", "oignon", "ail", "carotte", "courgette", "aubergine", "brocoli", "chou", "épinard", "poireau", "céleri", "champignon", "avocat", "gingembre", "persil", "ciboulette", "basilic", "radis", "roquette", "maïs", "potiron", "citrouille", "fruit", "légume", "herbes", "fenouil", "asperge", "betterave", "pomme de terre"),
            "Brot & Backwaren" to listOf("pain", "baguette", "croissant", "brioche", "gâteau", "biscotte", "tortilla", "viennoiserie", "pain de mie"),
            "Milchprodukte & Eier" to listOf("lait", "beurre", "fromage", "yaourt", "crème", "crème fraîche", "mozzarella", "parmesan", "feta", "œuf", "oeuf", "œufs", "oeufs", "margarine", "kéfir", "comté", "emmental", "camembert"),
            "Fleisch & Fisch" to listOf("viande", "poulet", "dinde", "bœuf", "boeuf", "porc", "haché", "saucisse", "jambon", "saucisson", "lardons", "bacon", "poisson", "saumon", "thon", "crevette", "steak", "agneau", "charcuterie"),
            "Tiefkühl" to listOf("surgelé", "glace", "pizza", "frites", "bâtonnets de poisson", "congelé"),
            "Vorrat" to listOf("pâtes", "spaghetti", "riz", "farine", "sucre", "sel", "huile", "vinaigre", "lentilles", "haricots", "pois chiches", "conserve", "boîte", "céréales", "muesli", "flocons d'avoine", "miel", "confiture", "levure", "bouillon", "concentré de tomate", "coulis", "semoule", "couscous", "quinoa", "huile d'olive"),
            "Gewürze & Soßen" to listOf("poivre", "épice", "paprika", "curry", "ketchup", "moutarde", "mayonnaise", "sauce", "sauce soja", "cannelle", "origan", "piment", "vanille"),
            "Getränke" to listOf("eau", "jus", "cola", "limonade", "bière", "vin", "champagne", "café", "thé", "eau gazeuse", "cacao", "sirop", "thé glacé"),
            "Süßes & Snacks" to listOf("chocolat", "chips", "biscuit", "gâteaux secs", "bonbon", "noix", "noisettes", "cacahuètes", "crackers", "barre", "pop-corn", "bretzels"),
            "Drogerie" to listOf("dentifrice", "brosse à dents", "shampooing", "gel douche", "savon", "déodorant", "crème", "rasoir", "mouchoirs", "papier toilette", "coton", "pansement", "tampon", "serviettes hygiéniques", "couches", "crème solaire", "après-shampooing"),
            "Haushalt" to listOf("liquide vaisselle", "lessive", "sacs poubelle", "essuie-tout", "éponge", "nettoyant", "papier alu", "film alimentaire", "papier cuisson", "pile", "piles", "ampoule", "lave-vaisselle", "tablettes", "adoucissant", "bougie", "serviettes"),
            "Tierbedarf" to listOf("croquettes", "pâtée", "litière", "friandises")))

    const val OTHER = "Sonstiges"
    val categoryOrder = groceries.map { it.first } + OTHER

    fun groceryCategory(text: String): String {
        val lowered = " ${text.lowercase()} "
        var best: Pair<String, Int>? = null
        val wordsFor = groceryWords[I18n.language()]
        for ((name, german) in groceries) {
            for (word in wordsFor?.get(name) ?: if (wordsFor != null) emptyList() else german) {
                val found = if (word.length <= 3) {
                    Regex("(?<![\\p{L}\\p{N}])" + Regex.escape(word) + "(?![\\p{L}\\p{N}])").containsMatchIn(lowered)
                } else {
                    lowered.contains(word)
                }
                if (found && (best == null || word.length > best.second)) best = name to word.length
            }
        }
        return best?.first ?: OTHER
    }
}
