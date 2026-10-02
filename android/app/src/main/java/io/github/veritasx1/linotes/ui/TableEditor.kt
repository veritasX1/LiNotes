package io.github.veritasx1.linotes.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.github.veritasx1.linotes.data.Model
import org.json.JSONObject

/** Edit a table (like Apple's): cells in a grid; rows and columns are added or removed next to
 *  the selected cell. "Fertig" saves, deleting removes the table from the note. */
@Composable
fun TableEditor(block: JSONObject, onDone: (JSONObject?) -> Unit) {
    val colors = palette
    var rows by remember { mutableStateOf(Model.tableRows(block)) }
    var selected by remember { mutableStateOf(0 to 0) }
    var focusAfterChange by remember { mutableStateOf<Pair<Int, Int>?>(0 to 0) }
    var confirmDelete by remember { mutableStateOf(false) }
    fun save() = onDone(Model.tableBlock(rows))
    fun change(new: List<List<String>>, focus: Pair<Int, Int>) {
        rows = new
        selected = focus.first.coerceIn(0, new.lastIndex) to focus.second.coerceIn(0, new[0].lastIndex)
        focusAfterChange = selected
    }
    val (r, c) = selected

    Dialog(onDismissRequest = { save() }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        UseWholeScreen()
        Column(Modifier.fillMaxSize().background(colors.background).navigationBarsPadding().imePadding()) {
            NavBar("Tabelle", null, null, actions = { TextButton("Fertig", bold = true) { save() } })
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).horizontalScroll(rememberScrollState()).padding(16.dp)) {
                rows.forEachIndexed { rowIndex, row ->
                    Row {
                        row.forEachIndexed { columnIndex, value ->
                            val focus = remember(rowIndex, columnIndex, rows.size, row.size) { FocusRequester() }
                            val isSelected = selected == rowIndex to columnIndex
                            BasicTextField(
                                value, { text -> rows = rows.mapIndexed { i, line -> if (i == rowIndex) line.mapIndexed { j, old -> if (j == columnIndex) text else old } else line } },
                                textStyle = Type.body.copy(color = colors.label), cursorBrush = SolidColor(colors.accent), singleLine = true,
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                                keyboardActions = KeyboardActions(onNext = {
                                    // Like Tab on Ubuntu: next cell, a new row after the last one.
                                    val columns = row.size
                                    val index = rowIndex * columns + columnIndex + 1
                                    if (index >= rows.size * columns) change(rows + listOf(List(columns) { "" }), rows.size to 0)
                                    else change(rows, index / columns to index % columns)
                                }),
                                modifier = Modifier.width(120.dp).heightIn(min = 44.dp)
                                    .border(if (isSelected) 1.5.dp else 0.5.dp, if (isSelected) colors.accent else colors.separator)
                                    .padding(horizontal = 8.dp, vertical = 11.dp)
                                    .focusRequester(focus)
                                    .onFocusChanged { if (it.isFocused) selected = rowIndex to columnIndex },
                            )
                            if (focusAfterChange == rowIndex to columnIndex) {
                                androidx.compose.runtime.LaunchedEffect(focusAfterChange) { focus.requestFocus(); focusAfterChange = null }
                            }
                        }
                    }
                }
            }
            // Actions for the selected cell.
            Column(Modifier.fillMaxWidth().background(colors.bar).padding(vertical = 4.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                    TableAction("Zeile darüber") { change(rows.take(r) + listOf(List(rows[0].size) { "" }) + rows.drop(r), r to c) }
                    TableAction("Zeile darunter") { change(rows.take(r + 1) + listOf(List(rows[0].size) { "" }) + rows.drop(r + 1), r + 1 to c) }
                    TableAction("Zeile löschen", enabled = rows.size > 1) { change(rows.filterIndexed { i, _ -> i != r }, r to c) }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                    TableAction("Spalte links") { change(rows.map { it.take(c) + "" + it.drop(c) }, r to c) }
                    TableAction("Spalte rechts") { change(rows.map { it.take(c + 1) + "" + it.drop(c + 1) }, r to c + 1) }
                    TableAction("Spalte löschen", enabled = rows[0].size > 1) { change(rows.map { line -> line.filterIndexed { j, _ -> j != c } }, r to c) }
                }
                Box(Modifier.fillMaxWidth().clickable { confirmDelete = true }.padding(12.dp)) {
                    Text("Tabelle löschen", style = Type.body, color = colors.red, modifier = Modifier.align(androidx.compose.ui.Alignment.Center))
                }
            }
        }
        if (confirmDelete) {
            AlertDialog("Tabelle löschen?", "Die Tabelle wird aus der Notiz entfernt.", "Löschen", destructive = true,
                onDismiss = { confirmDelete = false }) { onDone(null) }
        }
    }
}

@Composable
private fun TableAction(label: String, enabled: Boolean = true, onClick: () -> Unit) {
    val colors = palette
    Text(label, style = Type.subheadline, color = if (enabled) colors.accentText else colors.tertiary,
        modifier = Modifier.clickable(enabled = enabled, onClick = onClick).padding(horizontal = 8.dp, vertical = 12.dp))
}
