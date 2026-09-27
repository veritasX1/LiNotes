package io.github.veritasx1.linotes.data

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/** Helpers shared by the screens, mirroring linux/linotes/model.py. */
object Model {

    private val tagPattern = Regex("(?<![\\w#])#(\\p{L}[\\p{L}\\p{N}_-]{0,40})")

    fun blocks(note: SyncObject): JSONArray = note.data.optJSONArray("body") ?: JSONArray()

    fun isLocked(note: SyncObject) = note.data.has("enc")

    fun title(note: SyncObject): String {
        if (isLocked(note)) return "Gesperrte Notiz"
        val body = blocks(note)
        for (index in 0 until body.length()) {
            val text = body.optJSONObject(index)?.optString("x")?.trim().orEmpty()
            if (text.isNotEmpty()) return text.take(120)
        }
        return "Neue Notiz"
    }

    fun preview(note: SyncObject): String {
        if (isLocked(note)) return ""
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

    fun text(note: SyncObject): String {
        val body = blocks(note)
        return (0 until body.length()).joinToString("\n") { body.optJSONObject(it)?.optString("x").orEmpty() }
    }

    fun tags(note: SyncObject): Set<String> {
        if (isLocked(note)) return emptySet()
        return tagPattern.findAll(text(note)).map { it.groupValues[1].lowercase() }.toSet()
    }

    fun modified(obj: SyncObject): Double = obj.data.optDouble("modified", obj.updated).let { if (it.isNaN()) obj.updated else it }

    private val months = listOf("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
        "September", "Oktober", "November", "Dezember")
    private val weekdays = listOf("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")

    private fun date(seconds: Double): LocalDate =
        Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault()).toLocalDate()

    fun dateGroup(seconds: Double): String {
        val today = LocalDate.now()
        val day = date(seconds)
        val delta = ChronoUnit.DAYS.between(day, today)
        return when {
            delta <= 0 -> "Heute"
            delta == 1L -> "Gestern"
            delta < 7 -> "Vorherige 7 Tage"
            delta < 30 -> "Vorherige 30 Tage"
            day.year == today.year -> months[day.monthValue - 1]
            else -> "${months[day.monthValue - 1]} ${day.year}"
        }
    }

    fun shortDate(seconds: Double): String {
        val moment = Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault())
        val delta = ChronoUnit.DAYS.between(moment.toLocalDate(), LocalDate.now())
        return when {
            delta <= 0 -> moment.format(DateTimeFormatter.ofPattern("HH:mm"))
            delta == 1L -> "Gestern"
            delta < 7 -> weekdays[moment.dayOfWeek.value - 1]
            else -> moment.format(DateTimeFormatter.ofPattern("dd.MM.yy"))
        }
    }

    fun longDate(seconds: Double): String {
        val moment = Instant.ofEpochMilli((seconds * 1000).toLong()).atZone(ZoneId.systemDefault())
        return "${moment.dayOfMonth}. ${months[moment.monthValue - 1]} ${moment.year} um ${moment.format(DateTimeFormatter.ofPattern("HH:mm"))}"
    }

    fun now() = System.currentTimeMillis() / 1000.0

    // --- defaults (same stable ids as on Linux; everything starts private) ---

    fun privateFolder(userId: Int) = "notes-$userId"
    fun defaultList(userId: Int) = "list-$userId"
    fun defaultBoard(userId: Int) = "board-$userId"
    val defaultColumns = listOf("offen" to "Offen", "arbeit" to "In Arbeit", "fertig" to "Erledigt")

    fun ensureDefaults(sync: SyncEngine) {
        val userId = sync.userId
        if (userId == 0) return
        if (!sync.exists(privateFolder(userId)))
            sync.put("folder", JSONObject().put("name", "Notizen").put("order", 0), null, privateFolder(userId))
        if (!sync.exists(defaultList(userId)))
            sync.put("list", JSONObject().put("name", "Einkaufsliste").put("grocery", true).put("order", 0), null, defaultList(userId))
        val board = defaultBoard(userId)
        if (!sync.exists(board)) {
            sync.put("board", JSONObject().put("name", "Aufgaben").put("order", 0), null, board)
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

    const val OTHER = "Sonstiges"
    val categoryOrder = groceries.map { it.first } + OTHER

    fun groceryCategory(text: String): String {
        val lowered = " ${text.lowercase()} "
        var best: Pair<String, Int>? = null
        for ((name, words) in groceries) {
            for (word in words) {
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
