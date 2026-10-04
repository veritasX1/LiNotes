package io.github.veritasx1.linotes.ui

import android.graphics.Bitmap
import android.view.ViewGroup
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import io.github.veritasx1.linotes.data.Keep
import io.github.veritasx1.linotes.data.LinkPreview
import io.github.veritasx1.linotes.data.Model
import io.github.veritasx1.linotes.data.SyncObject
import io.github.veritasx1.linotes.data.Vault
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

@Composable
fun EditorScreen(state: AppState, noteId: String, revision: Long) {
    val colors = palette
    val sync = state.sync
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val note = remember(revision, noteId) { sync.get(noteId) }
    var unlockedRevision by remember { mutableIntStateOf(0) }
    var showFormat by remember { mutableStateOf(false) }
    var showMenu by remember { mutableStateOf(false) }
    var moving by remember { mutableStateOf(false) }
    var locking by remember { mutableStateOf<Boolean?>(null) }
    var styleTick by remember { mutableIntStateOf(0) }
    var sortChecked by remember { mutableStateOf(false) }
    var keepChoice by remember { mutableStateOf(false) }
    var loadFailed by remember { mutableStateOf(false) }
    var photoMenu by remember { mutableStateOf(false) }
    var linkMenu by remember { mutableStateOf<JSONObject?>(null) }
    var recording by remember { mutableStateOf(false) }
    // The table being edited (its block as it is in the note).
    var tableEditing by remember { mutableStateOf<JSONObject?>(null) }
    val player = remember(noteId) { AudioPlayer() }
    DisposableEffect(noteId) { onDispose { player.stop() } }
    // Text typed after ">>" while the note choice is shown (null: no choice open).
    var linkQuery by remember { mutableStateOf<String?>(null) }
    val scrollState = rememberScrollState()
    var viewportHeight by remember { mutableIntStateOf(0) }
    var editorTop by remember { mutableStateOf(0f) }
    val density = androidx.compose.ui.platform.LocalDensity.current

    // Content that only lives on the server is fetched when the note opens.
    DisposableEffect(noteId) {
        sync.openNote = noteId
        sync.markOpened(noteId)
        onDispose { if (sync.openNote == noteId) sync.openNote = null; sync.markOpened(noteId) }
    }
    LaunchedEffect(noteId, note?.evicted) {
        if (note?.evicted == true) {
            loadFailed = withContext(Dispatchers.IO) { try { sync.fetchNote(noteId) == null } catch (error: Exception) { true } }
        }
    }

    // Leaving the note (back arrow, back gesture, tab switch) closes the keyboard; the
    // editor is a platform EditText, so Compose would leave it open on the list.
    val hostView = LocalView.current
    DisposableEffect(noteId) {
        onDispose {
            val input = context.getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            input.hideSoftInputFromWindow(hostView.windowToken, 0)
        }
    }

    if (note == null) {
        LaunchedEffect(Unit) { state.pop() }
        return
    }
    val folder = sync.get(note.data.optString("folder"))
    val backLabel = folder?.data?.optString("name") ?: "Notizen"
    val locked = note.data.has("enc")
    val trashed = note.data.has("trashed")

    val editorColors = EditorColors(
        label = colors.label.toArgb(), secondary = colors.secondary.toArgb(), tertiary = colors.tertiary.toArgb(),
        accent = colors.accent.toArgb(), highlight = colors.highlight.toArgb(),
    )
    val editor = remember(noteId, colors.dark) {
        RichEditor(context, editorColors) { fileId, done ->
            scope.launch {
                val bitmap: Bitmap? = withContext(Dispatchers.IO) {
                    try {
                        val bytes = sync.fetchFile(fileId, sync.get(noteId)?.share).readBytes()
                        RichEditor.decodeImage(bytes).also { if (it == null) android.util.Log.w("LiNotes", "Bild nicht lesbar: $fileId (${bytes.size} Bytes)") }
                    } catch (error: Exception) {
                        android.util.Log.w("LiNotes", "Bild nicht geladen: $fileId", error)
                        null
                    }
                }
                done(bitmap)
            }
        }.apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            // Text size from the settings (per device), on top of the system font size.
            setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 17f * io.github.veritasx1.linotes.data.TEXT_SIZES[sync.textSize].first)
            // Justified text and German hyphenation, per device (settings → Darstellung).
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                justificationMode = if (sync.justify) android.text.Layout.JUSTIFICATION_MODE_INTER_WORD else android.text.Layout.JUSTIFICATION_MODE_NONE
            }
            justified = sync.justify
            textLocale = java.util.Locale.getDefault()
            hyphenationFrequency = if (sync.hyphenate) android.text.Layout.HYPHENATION_FREQUENCY_FULL else android.text.Layout.HYPHENATION_FREQUENCY_NONE
            breakStrategy = if (sync.justify || sync.hyphenate) android.text.Layout.BREAK_STRATEGY_HIGH_QUALITY else android.text.Layout.BREAK_STRATEGY_SIMPLE
        }
    }
    val loadedBlocks = remember(noteId) { mutableStateOf<String?>(null) }
    // "Claude hat geändert · 05:45 – die Änderungen sind markiert." (changes by others)
    var activityNote by remember(noteId) { mutableStateOf<String?>(null) }

    fun currentBody(): JSONArray? {
        val current = sync.get(noteId) ?: return null
        if (current.evicted) return null
        if (current.data.has("enc")) {
            val key = state.vaultKey ?: return null
            return try { Vault.openBody(key, current.data.getJSONObject("enc")) } catch (error: Exception) { null }
        }
        return Model.blocks(current)
    }

    fun save() {
        val current = sync.get(noteId) ?: return
        if (current.data.has("trashed") || current.evicted) return
        if (current.data.has("enc") && state.vaultKey == null) return
        val blocks = JSONArray(editor.toBlocks())
        val serialized = blocks.toString()
        if (serialized == loadedBlocks.value) return
        loadedBlocks.value = serialized
        val data = JSONObject(current.data.toString()).put("modified", Model.now())
        if (data.has("enc")) {
            val key = state.vaultKey ?: return
            data.put("enc", Vault.sealBody(key, blocks)).put("title", Model.blocksTitle(blocks))
            state.touchVault()
        } else {
            data.put("body", blocks)
        }
        sync.put("note", data, current.share, current.id)
        sync.get(noteId)?.let { sync.rememberSeen(it, blocks) }
    }

    // Locking (timeout, app in background, "lock now") saves the open note first.
    DisposableEffect(noteId) {
        state.flushLocked = { if (sync.get(noteId)?.data?.has("enc") == true) save() }
        onDispose { state.flushLocked = null }
    }

    // Load the note (and reload it when it changes on another device).
    val body = remember(revision, noteId, unlockedRevision, state.vaultKey) { currentBody() }
    LaunchedEffect(body?.toString(), colors.dark) {
        val text = body?.toString() ?: return@LaunchedEffect
        if (locked && note.data.optString("title").isEmpty() && Model.blocksTitle(body).isNotEmpty()) {
            // Notes locked before titles stayed visible get theirs now.
            sync.update(noteId) { it.put("title", Model.blocksTitle(body)) }
        }
        if (text != loadedBlocks.value) {
            val firstLoad = loadedBlocks.value == null
            val before = loadedBlocks.value
            loadedBlocks.value = text
            editor.load((0 until body.length()).map { body.getJSONObject(it) })
            // Someone else's changes: since my last view when opening, right away while open.
            sync.get(noteId)?.let { current ->
                val changes = when {
                    firstLoad -> sync.changesSinceSeen(current, body)
                    before != null && sync.changedByOther(current) ->
                        Model.changedLines(Model.blockLines(JSONArray(before)), Model.blockLines(body)).ifEmpty { null }
                    else -> null
                }
                if (changes != null) {
                    editor.markChanged(changes)
                    activityNote = "${sync.userName(current.updatedBy)} hat geändert · ${Model.shortDate(Model.modified(current))} – die Änderungen sind markiert."
                }
                sync.rememberSeen(current, body)
            }
            // A new, empty note starts with the keyboard open, like in Notes.
            if (firstLoad && body.length() <= 1 && body.optJSONObject(0)?.optString("x").isNullOrEmpty() && !trashed) {
                editor.post {
                    editor.requestFocus()
                    val input = context.getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                    input.showSoftInput(editor, android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT)
                }
            }
        }
    }
    DisposableEffect(editor) {
        var job: kotlinx.coroutines.Job? = null
        editor.onEdited = {
            job?.cancel()
            job = scope.launch { delay(700); save() }
        }
        editor.onStyleChanged = {
            styleTick++
            if (linkQuery != null) {
                val query = editor.pendingLinkQuery()
                if (query == null) { editor.finishLink(null, null); linkQuery = null } else linkQuery = query
            }
        }
        // Links between notes (">>", like Apple's Notes).
        editor.noteTitle = { id -> sync.get(id)?.takeIf { !it.data.has("trashed") }?.let { Model.title(it) } }
        // @-mentions: the people the note is shared with (like Apple, only in shared notes).
        editor.userName = { id -> sync.userName(id).takeIf { it != "?" } }
        editor.mentionPeople = {
            sync.get(noteId)?.share?.let { share -> sync.shareMembers(share).filter { it != sync.userId }.map { it to sync.userName(it) } } ?: emptyList()
        }
        editor.onLinkRequested = { linkQuery = editor.pendingLinkQuery() ?: "" }
        // Attachments: decrypt under their own name and open with the app for the type.
        // A web address alone on a line → preview card, only if switched on (Settings → Link-Vorschau)
        // and never in locked notes. Only this phone fetches the page; picture and card are stored
        // encrypted in the note. Fails quietly: the address simply stays a link.
        editor.onLinkLine = { url ->
            val current = sync.get(noteId)
            if (sync.linkPreviews && current != null && !current.data.has("enc") && !trashed) sync.launch {
                try {
                    val found = LinkPreview.fetch(url)
                    val reference = found.picture?.let { sync.uploadFile(it, current.share) }
                    val block = LinkPreview.block(url, found, reference)
                    withContext(Dispatchers.Main) { if (editor.isAttachedToWindow) editor.replaceUrlLine(url, block) }
                } catch (error: Exception) {
                    android.util.Log.i("LiNotes", "keine Link-Vorschau: $error")
                }
            }
        }
        editor.onOpenFile = { block ->
            // Recordings play inside the note (like Apple), other files open in their app.
            if (block.optString("t") == "link") {
                linkMenu = block
            } else if (block.optString("t") == "table") {
                if (!trashed) tableEditing = block
            } else if (AudioNotes.isAudio(block)) {
                val fileId = block.getString("f")
                if (player.playing == fileId) player.stop()
                else scope.launch {
                    try {
                        val file = withContext(Dispatchers.IO) { sync.fetchFile(fileId, sync.get(noteId)?.share) }
                        player.play(fileId, file)
                    } catch (error: Exception) {
                        state.showToast(errorText(error))
                    }
                }
            } else scope.launch {
                try {
                    val file = withContext(Dispatchers.IO) {
                        val source = sync.fetchFile(block.getString("f"), sync.get(noteId)?.share)
                        val folder = java.io.File(context.cacheDir, "attachments/" + block.getString("f").substringAfter(":").take(12)).apply { mkdirs() }
                        java.io.File(folder, java.io.File(block.optString("n", "Datei")).name).also { source.copyTo(it, overwrite = true) }
                    }
                    state.quickLook = LookFile(file, block.optString("m", "application/octet-stream"))
                } catch (error: Exception) {
                    state.showToast(errorText(error))
                }
            }
        }
        editor.loadFilePreview = { block, done ->
            scope.launch {
                done(withContext(Dispatchers.IO) {
                    try {
                        val source = sync.fetchFile(block.getString("f"), sync.get(noteId)?.share)
                        android.graphics.pdf.PdfRenderer(android.os.ParcelFileDescriptor.open(source, android.os.ParcelFileDescriptor.MODE_READ_ONLY)).use { pdf ->
                            pdf.openPage(0).use { page ->
                                val scale = 160f / maxOf(page.width, page.height)
                                Bitmap.createBitmap((page.width * scale).toInt().coerceAtLeast(1), (page.height * scale).toInt().coerceAtLeast(1), Bitmap.Config.ARGB_8888).also {
                                    it.eraseColor(android.graphics.Color.WHITE)
                                    page.render(it, null, null, android.graphics.pdf.PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                                }
                            }
                        }
                    } catch (error: Exception) {
                        android.util.Log.w("LiNotes", "PDF-Vorschau nicht möglich", error)
                        null
                    }
                })
            }
        }
        editor.onOpenNote = { id ->
            val target = sync.get(id)
            if (target == null || target.data.has("trashed")) state.toastLater("Die verlinkte Notiz gibt es nicht mehr.")
            else { save(); state.push(Route.Editor(id)) }
        }
        onDispose {
            job?.cancel()
            save()
            // A new note left without anything in it is not kept (Apple: no stray "Neue Notiz").
            if (state.freshNotes.remove(noteId)) {
                val current = sync.get(noteId)
                if (current != null && !current.data.has("enc") && !current.data.has("trashed") && Model.isEmptyBody(Model.blocks(current))) {
                    sync.delete(noteId)
                }
            }
        }
    }
    editor.isEnabled = !trashed
    editor.autoSortChecked = sortChecked

    BackHandler { save(); state.pop() }

    Column(Modifier.fillMaxSize().background(colors.plain)) {
        NavBar(
            title = "", backLabel = backLabel, onBack = { save(); state.pop() }, background = colors.plain,
            actions = {
                if (!trashed && !locked) BarButton(Glyph.Share, "Teilen") { save(); state.push(Route.Share(note.id)) }
                // Like Apple: the open lock in an unlocked note locks it again right away.
                if (locked && state.vaultKey != null) BarButton(Glyph.LockOpen, "Jetzt sperren") { state.lockAll() }
                BarButton(Glyph.More, "Mehr") { save(); showMenu = true }
            },
        )
        if (trashed) {
            Row(Modifier.fillMaxWidth().background(colors.fill).padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Diese Notiz liegt in „Zuletzt gelöscht“.", style = Type.footnote, color = colors.label, modifier = Modifier.weight(1f))
                TextButton("Wiederherstellen") { restoreNote(state, note) }
            }
        }
        if (note.evicted) {
            Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                GlyphIcon(if (loadFailed) Glyph.CloudOff else Glyph.Cloud, colors.secondary, 56.dp)
                Spacer(Modifier.height(16.dp))
                Text(if (loadFailed) "Die Notiz liegt nur auf dem Server" else "Wird vom Server geladen …", style = Type.title3, color = colors.label)
                if (loadFailed) {
                    Spacer(Modifier.height(6.dp))
                    Text("Sie kann geöffnet werden, sobald eine Verbindung besteht.", style = Type.subheadline, color = colors.secondary)
                }
            }
            return@Column
        }
        if (locked && body == null) {
            LockedPlaceholder(state) { unlockedRevision++ }
            return@Column
        }
        // Keep the cursor line visible above the keyboard: the editor is a platform EditText inside a
        // Compose scroll column, which does not follow the cursor by itself.
        fun keepCaretVisible() {
            val layout = editor.layout ?: return
            if (!editor.hasFocus() || viewportHeight <= 0) return
            val line = layout.getLineForOffset(editor.selectionEnd.coerceAtLeast(0))
            val margin = (32 * density.density).toInt()
            val top = (editorTop + editor.totalPaddingTop + layout.getLineTop(line)).toInt()
            val bottom = (editorTop + editor.totalPaddingTop + layout.getLineBottom(line)).toInt()
            val target = when {
                bottom + margin > scrollState.value + viewportHeight -> bottom + margin - viewportHeight
                top - margin < scrollState.value -> (top - margin).coerceAtLeast(0)
                else -> return
            }
            scope.launch { scrollState.animateScrollTo(target) }
        }
        DisposableEffect(editor) {
            editor.onCaretMoved = { keepCaretVisible() }
            onDispose { editor.onCaretMoved = null }
        }
        val imeBottom = WindowInsets.ime.getBottom(density)
        LaunchedEffect(imeBottom) { if (imeBottom > 0) { kotlinx.coroutines.delay(50); keepCaretVisible() } }
        // The format panel takes room below the text: keep the selection above it, without the
        // system's selection menu on top of the panel's buttons.
        LaunchedEffect(showFormat) {
            editor.selectionMenuSuppressed = showFormat
            if (showFormat) { kotlinx.coroutines.delay(80); keepCaretVisible() }
        }
        Column(Modifier.weight(1f).imePadding()) {
            Column(Modifier.weight(1f).onSizeChanged { viewportHeight = it.height }.verticalScroll(scrollState)) {
                Text(Model.longDate(Model.modified(note)), style = Type.footnote, color = colors.secondary,
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 6.dp), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                activityNote?.let { message ->
                    Text(message, style = Type.footnote, color = colors.label,
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 6.dp)
                            .background(colors.accent.copy(alpha = 0.16f), androidx.compose.foundation.shape.RoundedCornerShape(8.dp))
                            .padding(horizontal = 10.dp, vertical = 6.dp))
                }
                AndroidView({ editor }, Modifier.fillMaxWidth().onGloballyPositioned { editorTop = it.positionInParent().y })
            }
            PlayerBar(player)
            linkQuery?.let { query ->
                val mention = editor.linkKind == "mention"
                val choices = if (mention) editor.mentionPeople().filter { it.second.contains(query, ignoreCase = true) }
                    .map { (id, name) -> Triple(id.toString(), name, "@$name") }
                else Model.linkChoices(sync.all("note"), noteId, query).map { Triple(it.id, Model.title(it), Model.title(it)) }
                LinkPanel(if (mention) "Person erwähnen" else "Mit Notiz verlinken", if (mention) Glyph.Person else Glyph.Notes,
                    if (mention) "Keine passende Person" else "Keine passende Notiz", choices, onPick = { (id, title, _) ->
                    linkQuery = null
                    editor.finishLink(id, title)
                }) { linkQuery = null; editor.finishLink(null, null) }
            }
            if (showFormat) FormatPanel(editor, styleTick, pro = sync.proFeatures) { showFormat = false }
            if (!trashed) EditorToolbar(
                onFormat = { showFormat = !showFormat },
                onChecklist = { editor.applyParagraph("check") },
                // Like Apple: a 3×3 table, editing starts right away.
                onTable = { Model.newTable().let { block -> editor.insertTable(block); tableEditing = block } },
                onPhoto = {
                    if (locked) state.toastLater("In gesperrten Notizen sind keine Fotos und Anhänge möglich.")
                    else photoMenu = true
                },
                // Like Apple: record audio into the note (encrypted like every attachment).
                onRecord = {
                    if (locked) state.toastLater("In gesperrten Notizen sind keine Aufnahmen möglich.")
                    else state.requestMicrophone { granted -> if (granted) recording = true else state.toastLater("Ohne Mikrofon-Erlaubnis keine Aufnahme.") }
                },
                onCompose = { save(); state.pop(); newNote(state, note.data.optString("folder").let { "folder:$it" }) },
            )
        }
    }

    /** Like Apple: the open note as PDF, to the share sheet or the print dialog. */
    fun exportPdf(print: Boolean) {
        val blocks = editor.toBlocks()
        val title = blocks.firstOrNull { it.optString("x").isNotBlank() }?.optString("x")?.trim()?.take(120) ?: "Notiz"
        val header = "$title · ${Model.longDate(Model.modified(note))}"
        val share = note.share
        scope.launch {
            val file = withContext(Dispatchers.IO) {
                val folder = java.io.File(context.cacheDir, "reports").apply { mkdirs() }
                java.io.File(folder, NotePdf.fileName(title)).also { file ->
                    NotePdf.write(blocks, header, file) { reference ->
                        runCatching { RichEditor.decodeImage(sync.fetchFile(reference, share).readBytes()) }.getOrNull()
                    }
                }
            }
            if (print) NotePdf.print(context, file, title) else state.shareFile(file, "application/pdf", title)
        }
    }

    if (showMenu) {
        ActionSheet(null, buildList {
            if (trashed) {
                add(SheetAction("Wiederherstellen") { restoreNote(state, note) })
                add(SheetAction("Endgültig löschen", destructive = true) { sync.delete(note.id); state.pop() })
            } else {
                add(SheetAction(if (note.data.optBoolean("pinned")) "Lösen" else "Anheften") { sync.update(note.id) { it.put("pinned", !it.optBoolean("pinned")) } })
                add(SheetAction("Verschieben …") { moving = true })
                add(archiveAction(state, note))
                if (!locked) add(SheetAction("Teilen …") { state.push(Route.Share(note.id)) })
                add(SheetAction("Als PDF senden …") { exportPdf(print = false) })
                add(SheetAction("Drucken …") { exportPdf(print = true) })
                add(SheetAction(if (locked) "Sperre entfernen" else "Notiz sperren") { locking = !locked })
                if (!sync.isLocal) add(SheetAction("Auf dem Gerät behalten: " + Keep.label(sync.keepOf(note))) { keepChoice = true })
                add(SheetAction(if (sortChecked) "Abgehakte nicht mehr sortieren" else "Abgehakte nach unten sortieren") { sortChecked = !sortChecked })
                add(SheetAction("Löschen", destructive = true) { trashNote(state, note); state.pop() })
            }
        }) { showMenu = false }
    }
    if (moving) MoveSheet(state, note) { moving = false }
    if (keepChoice) {
        val current = note.data.optString("keep")
        ActionSheet("Wie lange soll diese Notiz auf dem Handy bleiben?",
            listOf(SheetAction("Wie in den Einstellungen (${Keep.label(sync.keepDefault())})" + if (current.isEmpty()) " ✓" else "") {
                sync.update(note.id) { it.remove("keep") }
            }) + Keep.choices.map { (value, label) ->
                SheetAction(label + if (value == current) " ✓" else "") { sync.update(note.id) { it.put("keep", value) } }
            }) { keepChoice = false }
    }
    locking?.let { lock -> LockFlow(state, note, lock) { locking = null; unlockedRevision++ } }
    linkMenu?.let { block ->
        ActionSheet(block.optString("dm").ifEmpty { block.optString("u") }, listOf(
            SheetAction("Im Browser öffnen") {
                runCatching { context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(block.optString("u")))) }
            },
            SheetAction("Nur als Adresse zeigen") { editor.unlinkPreview(block) },
        )) { linkMenu = null }
    }
    if (photoMenu) {
        // Like Notes: take a photo or choose one.
        fun insert(bytes: ByteArray, @Suppress("UNUSED_PARAMETER") mime: String) {
            state.upload("Foto", bytes, note.share) { id ->
                if (editor.isAttachedToWindow) editor.insertImage(id) else appendBlock(state, noteId, JSONObject().put("t", "image").put("f", id))
            }
        }
        ActionSheet(null, listOf(
            SheetAction("Foto aufnehmen") { state.takePhoto(::insert) },
            SheetAction("Aus Fotos wählen") { state.pickImage(::insert) },
            // Like Apple: attach a PDF or any other file (encrypted like photos).
            SheetAction("Datei anhängen …") {
                state.pickFile { name, mime, bytes ->
                    state.upload(name, bytes, note.share) { id ->
                        val block = JSONObject().put("t", "file").put("f", id).put("n", name).put("m", mime).put("b", bytes.size)
                        if (editor.isAttachedToWindow) editor.insertFile(block) else appendBlock(state, noteId, block)
                    }
                }
            },
        )) { photoMenu = false }
    }
    tableEditing?.let { block ->
        TableEditor(block) { changed ->
            editor.replaceTable(block, changed)
            tableEditing = null
        }
    }
    if (recording) {
        RecordDialog(
            onDone = { file, length ->
                recording = false
                scope.launch {
                    val bytes = try {
                        withContext(Dispatchers.IO) { file.readBytes().also { file.delete() } }
                    } catch (error: Exception) {
                        state.showToast(errorText(error))
                        return@launch
                    }
                    state.upload(file.name, bytes, note.share) { id ->
                        val block = JSONObject().put("t", "file").put("f", id).put("n", file.name).put("m", AudioNotes.mime)
                            .put("b", bytes.size).put("d", Math.round(length * 10) / 10.0)
                        if (editor.isAttachedToWindow) editor.insertFile(block) else appendBlock(state, noteId, block)
                    }
                }
            },
            onFailed = { message -> recording = false; state.toastLater(message) },
            onCancel = { recording = false },
        )
    }
}

@Composable
private fun LockedPlaceholder(state: AppState, onUnlocked: () -> Unit) {
    val colors = palette
    var asking by remember { mutableStateOf(false) }
    fun unlock() {
        if (state.biometricEnabled) state.unlockWithBiometric { ok -> if (ok) onUnlocked() else asking = true }
        else asking = true
    }
    LaunchedEffect(Unit) { if (state.biometricEnabled) unlock() }
    Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        GlyphIcon(Glyph.Lock, colors.secondary, 56.dp)
        Spacer(Modifier.height(16.dp))
        Text("Diese Notiz ist gesperrt", style = Type.title3, color = colors.label)
        Spacer(Modifier.height(6.dp))
        Text(if (state.biometricEnabled) "Entsperre sie mit Fingerabdruck, PIN oder Muster." else "Gib dein Notizen-Passwort ein, um sie anzusehen.", style = Type.subheadline, color = colors.secondary)
        Spacer(Modifier.height(24.dp))
        PrimaryButton("Notiz anzeigen", modifier = Modifier.width(220.dp)) { unlock() }
    }
    if (asking) UnlockDialog(state, onDismiss = { asking = false }) { asking = false; onUnlocked() }
}

@Composable
fun UnlockDialog(state: AppState, reason: String = "Gib dein Notizen-Passwort ein.", onDismiss: () -> Unit, onUnlocked: () -> Unit) {
    val scope = rememberCoroutineScope()
    val hint = state.vaultObject()?.data?.optString("hint").orEmpty()
    AlertDialog(
        "Gesperrte Notizen", reason + if (hint.isNotEmpty()) "\nMerkhilfe: $hint" else "", "OK",
        fields = listOf(AlertField("Passwort", password = true)), onDismiss = onDismiss,
    ) { values ->
        scope.launch {
            val ok = withContext(Dispatchers.Default) {
                try { state.unlock(values[0]); true } catch (error: Exception) { false }
            }
            if (ok) onUnlocked() else state.showToast("Falsches Passwort.")
        }
    }
}

/** Lock or unlock a note, creating the notes password first if needed. */
@Composable
fun LockFlow(state: AppState, note: SyncObject, lock: Boolean, onDone: () -> Unit) {
    val sync = state.sync
    val scope = rememberCoroutineScope()

    fun perform() {
        val current = sync.get(note.id) ?: return onDone()
        val key = state.vaultKey ?: return onDone()
        val data = JSONObject(current.data.toString())
        if (lock) {
            val body = data.optJSONArray("body") ?: JSONArray()
            data.remove("body")
            data.put("enc", Vault.sealBody(key, body)).put("title", Model.blocksTitle(body)).put("modified", Model.now())
            sync.put("note", data, current.share, current.id)
            state.toastLater("Notiz gesperrt")
            // Locking hides the content right away.
            state.lockAll()
        } else {
            val body = Vault.openBody(key, data.getJSONObject("enc"))
            data.remove("enc")
            data.remove("title")
            data.put("body", body)
            sync.put("note", data, current.share, current.id)
            state.toastLater("Sperre entfernt")
        }
        onDone()
    }

    when {
        lock && note.share != null -> {
            LaunchedEffect(Unit) { state.showToast("Geteilte Notizen können nicht gesperrt werden."); onDone() }
        }
        state.vaultKey != null -> LaunchedEffect(Unit) { state.touchVault(); perform() }
        !state.hasVault() -> AlertDialog(
            "Notizen-Passwort festlegen",
            "Gesperrte Notizen werden auf dem Gerät mit diesem Passwort verschlüsselt – nicht einmal der Server kann sie lesen. " +
                "Vergisst du es, lassen sich gesperrte Notizen nicht wiederherstellen.",
            "Festlegen",
            fields = listOf(AlertField("Passwort", password = true), AlertField("Bestätigen", password = true), AlertField("Merkhilfe")),
            onDismiss = onDone,
        ) { values ->
            when {
                values[0].length < 6 -> state.toastLater("Mindestens 6 Zeichen.")
                values[0] != values[1] -> state.toastLater("Die Passwörter stimmen nicht überein.")
                else -> scope.launch {
                    withContext(Dispatchers.Default) { state.createVault(values[0], values[2]) }
                    perform()
                }
            }
        }
        else -> VaultUnlock(state, onDismiss = onDone) { perform() }
    }
}

/** Fingerprint / PIN / pattern if switched on, otherwise (or as fallback) the notes password. */
@Composable
fun VaultUnlock(state: AppState, onDismiss: () -> Unit, onUnlocked: () -> Unit) {
    var password by remember { mutableStateOf(!state.biometricEnabled) }
    if (!password) LaunchedEffect(Unit) { state.unlockWithBiometric { ok -> if (ok) onUnlocked() else password = true } }
    else UnlockDialog(state, onDismiss = onDismiss, onUnlocked = onUnlocked)
}

@Composable
private fun EditorToolbar(onFormat: () -> Unit, onChecklist: () -> Unit, onTable: () -> Unit, onPhoto: () -> Unit, onRecord: () -> Unit, onCompose: () -> Unit) {
    val colors = palette
    Column(Modifier.fillMaxWidth().background(colors.bar)) {
        HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
        Row(Modifier.fillMaxWidth().navigationBarsPadding().height(48.dp).padding(horizontal = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            BarButton(Glyph.Format, "Format", onClick = onFormat)
            BarButton(Glyph.Checklist, "Checkliste", onClick = onChecklist)
            BarButton(Glyph.Table, "Tabelle", onClick = onTable)
            BarButton(Glyph.Photo, "Foto", onClick = onPhoto)
            BarButton(Glyph.Mic, "Audio aufnehmen", onClick = onRecord)
            BarButton(Glyph.Compose, "Neue Notiz", onClick = onCompose)
        }
    }
}

/** After ">>": notes to link to, above the keyboard. Typing on filters the list. */
@Composable
private fun LinkPanel(heading: String, glyph: Glyph, empty: String, choices: List<Triple<String, String, String>>,
                      onPick: (Triple<String, String, String>) -> Unit, onClose: () -> Unit) {
    val colors = palette
    Column(Modifier.fillMaxWidth().background(colors.background)) {
        HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
        Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 10.dp, top = 8.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(heading, style = Type.footnote, color = colors.secondary, modifier = Modifier.weight(1f))
            Box(Modifier.size(26.dp).clip(RoundedCornerShape(13.dp)).background(colors.fill).clickable(onClick = onClose), contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Close, colors.secondary, 10.dp)
            }
        }
        Column(Modifier.fillMaxWidth().heightIn(max = 200.dp).verticalScroll(rememberScrollState())) {
            if (choices.isEmpty()) Text(empty, style = Type.subheadline, color = colors.tertiary,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp))
            choices.forEachIndexed { index, choice ->
                GroupRow(choice.third, glyph = glyph, chevron = false, divider = index < choices.lastIndex) { onPick(choice) }
            }
        }
    }
}

@Composable
private fun FormatPanel(editor: RichEditor, tick: Int, pro: Boolean, onClose: () -> Unit) {
    val colors = palette
    val current = remember(tick) { editor.currentStyle() }
    val inline = remember(tick) { editor.activeInline() }
    Column(Modifier.fillMaxWidth().background(colors.background).padding(horizontal = 14.dp, vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Format", style = Type.headline, color = colors.label, modifier = Modifier.weight(1f))
            Box(Modifier.size(30.dp).clip(RoundedCornerShape(15.dp)).background(colors.fill).clickable(onClick = onClose), contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Close, colors.secondary, 12.dp)
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((type, label, size, weight) in listOf(
                Quad("title", "Titel", 20, FontWeight.Bold), Quad("heading", "Überschrift", 17, FontWeight.Bold),
                Quad("subheading", "Unterüberschrift", 15, FontWeight.SemiBold), Quad("body", "Text", 15, FontWeight.Normal),
            )) {
                val active = current == type
                Text(label, fontSize = size.sp, fontWeight = weight, color = if (active) Color.White else colors.label, maxLines = 1,
                    modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(if (active) colors.accent else colors.surface)
                        .clickable { editor.applyParagraph(type) }.padding(horizontal = 10.dp, vertical = 8.dp))
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Row(Modifier.clip(RoundedCornerShape(8.dp)).background(colors.surface)) {
                for ((name, label) in listOf("b" to "B", "i" to "I", "u" to "U", "s" to "S")) {
                    val active = name in inline
                    Text(label, fontSize = 18.sp,
                        fontWeight = if (name == "b") FontWeight.Bold else FontWeight.Normal,
                        fontStyle = if (name == "i") FontStyle.Italic else FontStyle.Normal,
                        textDecoration = when (name) { "u" -> TextDecoration.Underline; "s" -> TextDecoration.LineThrough; else -> null },
                        color = if (active) Color.White else colors.label,
                        modifier = Modifier.background(if (active) colors.accent else Color.Transparent)
                            .clickable { editor.toggleInline(name) }.padding(horizontal = 14.dp, vertical = 8.dp))
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        // Highlight colors like in Apple's Notes; the active color is ringed, tapping it again removes it.
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Markieren", fontSize = 15.sp, color = colors.label, modifier = Modifier.padding(end = 4.dp))
            for ((name, rgb) in HIGHLIGHTS) {
                val active = name in inline
                Box(Modifier.size(30.dp).clip(RoundedCornerShape(15.dp))
                    .background(if (active) colors.label else Color.Transparent).padding(if (active) 2.dp else 0.dp)
                    .clip(RoundedCornerShape(15.dp)).background(Color(0xFF000000 or rgb.toLong()))
                    .clickable { editor.setHighlight(name) })
            }
            Box(Modifier.size(30.dp).clip(RoundedCornerShape(15.dp)).background(colors.surface).clickable { editor.setHighlight(null) },
                contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Close, colors.secondary, 10.dp)
            }
        }
        Spacer(Modifier.height(8.dp))
        // Text color (like Apple: purple, pink, orange, mint, blue).
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Textfarbe", fontSize = 15.sp, color = colors.label, modifier = Modifier.padding(end = 4.dp))
            for ((name, rgb) in TEXT_COLORS) {
                val active = name in inline
                Box(Modifier.size(30.dp).clip(RoundedCornerShape(15.dp)).background(if (active) colors.fill else colors.surface)
                    .clickable { editor.setTextColorStyle(name) }, contentAlignment = Alignment.Center) {
                    Text("A", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Color(0xFF000000 or rgb.toLong()))
                }
            }
            Box(Modifier.size(30.dp).clip(RoundedCornerShape(15.dp)).background(colors.surface).clickable { editor.setTextColorStyle(null) },
                contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Close, colors.secondary, 10.dp)
            }
        }
        Spacer(Modifier.height(8.dp))
        // Font and paragraph alignment.
        val align = remember(tick) { editor.currentAlignment() }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((name, label, family) in listOf(Triple(null, "Standard", FontFamily.Default), Triple("f:serif", "Serif", FontFamily.Serif),
                Triple("f:mono", "Mono", FontFamily.Monospace))) {
                val active = if (name == null) FONTS.keys.none { it in inline } else name in inline
                Text(label, fontSize = 14.sp, fontFamily = family, color = if (active) Color.White else colors.label,
                    modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(if (active) colors.accent else colors.surface)
                        .clickable { editor.setFont(name) }.padding(horizontal = 9.dp, vertical = 8.dp))
            }
            for ((name, label) in listOf(null to "Links", "center" to "Mitte", "right" to "Rechts")) {
                val active = align == name
                Text(label, fontSize = 14.sp, color = if (active) Color.White else colors.label,
                    modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(if (active) colors.accent else colors.surface)
                        .clickable { editor.setAlignment(name) }.padding(horizontal = 9.dp, vertical = 8.dp))
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((type, label) in listOf("bullet" to "• Liste", "dash" to "– Liste", "number" to "1. Liste", "mono" to "Mono", "quote" to "Zitat")) {
                val active = current == type
                Text(label, fontSize = 14.sp, color = if (active) Color.White else colors.label,
                    fontFamily = if (type == "mono") FontFamily.Monospace else FontFamily.Default,
                    modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(if (active) colors.accent else colors.surface)
                        .clickable { editor.applyParagraph(type) }.padding(horizontal = 9.dp, vertical = 8.dp))
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Ausrücken", fontSize = 14.sp, color = colors.label,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(colors.surface).clickable { editor.indent(-1) }.padding(horizontal = 10.dp, vertical = 8.dp))
            Text("Einrücken", fontSize = 14.sp, color = colors.label,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(colors.surface).clickable { editor.indent(1) }.padding(horizontal = 10.dp, vertical = 8.dp))
            // Also: "---" and Enter on an empty line.
            Text("Trennlinie", fontSize = 14.sp, color = colors.label,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(colors.surface).clickable { editor.insertDivider() }.padding(horizontal = 10.dp, vertical = 8.dp))
        }
        // Profi-Funktionen only when switched on (Settings) – Tante Erna sees a calm panel.
        if (pro) {
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Code", fontSize = 15.sp, color = colors.label, fontFamily = FontFamily.Monospace, modifier = Modifier.padding(end = 4.dp))
                for ((lang, label) in io.github.veritasx1.linotes.data.Syntax.LANGUAGES) {
                    Text(label, fontSize = 14.sp, color = colors.label, fontFamily = FontFamily.Monospace,
                        modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(colors.surface).clickable { editor.makeCode(lang) }
                            .padding(horizontal = 9.dp, vertical = 8.dp))
                }
            }
        }
    }
}

private data class Quad(val type: String, val label: String, val size: Int, val weight: FontWeight)

/** An upload that finished after the note was closed: its block goes to the end of the note. */
private fun appendBlock(state: AppState, noteId: String, block: JSONObject) {
    val sync = state.sync
    val current = sync.get(noteId) ?: return
    if (current.data.has("enc") || current.data.has("trashed")) return
    val data = JSONObject(current.data.toString())
    val body = data.optJSONArray("body") ?: JSONArray()
    body.put(block)
    data.put("body", body).put("modified", Model.now())
    sync.put("note", data, current.share, current.id)
}
