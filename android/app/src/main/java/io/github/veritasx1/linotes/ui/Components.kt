package io.github.veritasx1.linotes.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.selection.toggleable
import androidx.compose.ui.draw.shadow
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text

// ================================================================
// SCREEN WITH LARGE TITLE (like UINavigationBar with prefersLargeTitles)
// ================================================================

@Composable
fun LargeTitleScreen(
    title: String,
    backLabel: String? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    background: Color = palette.background,
    state: LazyListState = rememberLazyListState(),
    subtitle: String? = null,
    content: LazyListScope.() -> Unit,
) {
    val colors = palette
    val collapsed by remember { derivedStateOf { state.firstVisibleItemIndex > 0 || state.firstVisibleItemScrollOffset > 60 } }
    Column(Modifier.fillMaxSize().background(background)) {
        NavBar(title = if (collapsed) title else "", backLabel = backLabel, onBack = onBack, actions = actions,
            showDivider = collapsed)
        LazyColumn(state = state, modifier = Modifier.weight(1f)) {
            item(key = "large-title") {
                Column(Modifier.padding(start = 16.dp, end = 16.dp, top = 2.dp, bottom = 8.dp)) {
                    Text(title, style = Type.largeTitle, color = colors.label, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    if (subtitle != null) Text(subtitle, style = Type.subheadline, color = colors.secondary)
                }
            }
            content()
            item { Spacer(Modifier.height(24.dp)) }
        }
        bottomBar()
    }
}

@Composable
fun NavBar(
    title: String,
    backLabel: String? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    showDivider: Boolean = false,
    background: Color = palette.background,
) {
    val colors = palette
    Column(Modifier.background(if (showDivider) colors.bar else background).statusBarsPadding()) {
        // Back button and actions keep their width; the title gets the space between them,
        // centered on the screen as long as it fits (like UINavigationBar).
        Layout(
            modifier = Modifier.fillMaxWidth().height(44.dp),
            content = {
                Box {
                    if (onBack != null) {
                        Row(
                            Modifier.clip(RoundedCornerShape(8.dp)).clickable(onClick = onBack, onClickLabel = "Zurück", role = Role.Button)
                                .padding(start = 6.dp, end = 10.dp, top = 8.dp, bottom = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            GlyphIcon(Glyph.Back, colors.accentText, 22.dp)
                            if (backLabel != null) Text(backLabel, style = Type.body, color = colors.accentText, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
                Box {
                    androidx.compose.animation.AnimatedVisibility(visible = title.isNotEmpty(), enter = fadeIn(), exit = fadeOut()) {
                        Text(title, style = Type.headline, color = colors.label, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                    }
                }
                Row(Modifier.padding(end = 6.dp), verticalAlignment = Alignment.CenterVertically, content = actions)
            },
        ) { measurables, constraints ->
            val width = constraints.maxWidth
            val height = constraints.maxHeight
            val loose = constraints.copy(minWidth = 0, minHeight = 0)
            val actionsPlaceable = measurables[2].measure(loose.copy(maxWidth = width / 2))
            val backPlaceable = measurables[0].measure(loose.copy(maxWidth = (width - actionsPlaceable.width) * 2 / 3))
            val gap = 8.dp.roundToPx()
            val side = maxOf(backPlaceable.width, actionsPlaceable.width) + gap
            val centered = width - 2 * side
            val titleWidth = if (centered >= width / 3) centered else (width - backPlaceable.width - actionsPlaceable.width - 2 * gap).coerceAtLeast(0)
            val titlePlaceable = measurables[1].measure(loose.copy(minWidth = titleWidth, maxWidth = titleWidth))
            val titleX = if (centered >= width / 3) side else backPlaceable.width + gap
            layout(width, height) {
                backPlaceable.place(0, (height - backPlaceable.height) / 2)
                titlePlaceable.place(titleX, (height - titlePlaceable.height) / 2)
                actionsPlaceable.place(width - actionsPlaceable.width, (height - actionsPlaceable.height) / 2)
            }
        }
        if (showDivider) HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
    }
}

@Composable
fun BarButton(glyph: Glyph, description: String, tint: Color = palette.accentText, enabled: Boolean = true, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(RoundedCornerShape(22.dp))
            .clickable(enabled = enabled, onClickLabel = description, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        GlyphIcon(glyph, if (enabled) tint else tint.copy(alpha = 0.35f), 22.dp)
    }
}

/** On/off switch in the shape of UISwitch, tinted with the accent color. */
@Composable
fun IosSwitch(checked: Boolean, description: String, onToggle: () -> Unit) {
    val colors = palette
    val offset by androidx.compose.animation.core.animateDpAsState(if (checked) 20.dp else 0.dp, label = "switch")
    Box(
        Modifier.size(51.dp, 31.dp).clip(RoundedCornerShape(16.dp))
            .background(if (checked) colors.accent else colors.fill.copy(alpha = if (colors.dark) 0.32f else 0.16f))
            .toggleable(value = checked, role = Role.Switch, onValueChange = { onToggle() })
            .semantics { contentDescription = description }
            .padding(2.dp),
    ) {
        Box(Modifier.padding(start = offset).size(27.dp).shadow(2.dp, CircleShape).clip(CircleShape).background(Color.White))
    }
}

@Composable
fun TextButton(label: String, color: Color = palette.accentText, bold: Boolean = false, onClick: () -> Unit) {
    Text(
        label,
        style = if (bold) Type.headline else Type.body,
        color = color,
        modifier = Modifier.clip(RoundedCornerShape(8.dp)).clickable(onClick = onClick).padding(horizontal = 10.dp, vertical = 10.dp),
    )
}

// ================================================================
// INSET GROUPED LISTS
// ================================================================

fun LazyListScope.section(
    key: String,
    header: String? = null,
    footer: String? = null,
    compact: Boolean = false,
    headerDrop: Pair<(String) -> Boolean, (String) -> Unit>? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    item(key = key) {
        val colors = palette
        Column(Modifier.padding(horizontal = 16.dp).padding(top = if (header != null) 18.dp else 10.dp)) {
            if (header != null && compact) {
                // Small grey header of grouped settings, same as FormSection.
                Text(header, style = Type.footnote, color = colors.secondary,
                    modifier = Modifier.padding(start = 16.dp, bottom = 6.dp).semantics { heading() })
            } else if (header != null) {
                Text(header, style = Type.title3.copy(fontWeight = FontWeight.Bold), color = colors.label,
                    modifier = Modifier.fillMaxWidth()
                        .then(if (headerDrop != null) Modifier.dropZone(headerDrop.first, headerDrop.second) else Modifier)
                        .padding(start = 4.dp, bottom = 8.dp).semantics { heading() })
            }
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colors.surface), content = content)
            if (footer != null) {
                Text(footer, style = Type.footnote, color = colors.secondary, modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 6.dp))
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun GroupRow(
    title: String,
    glyph: Glyph? = null,
    tint: Color = palette.accent,
    detail: String? = null,
    subtitle: String? = null,
    chevron: Boolean = true,
    divider: Boolean = true,
    titleColor: Color = palette.label,
    indent: Dp = 0.dp,
    modifier: Modifier = Modifier,
    dragPayload: String? = null,
    onLongClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
    onClick: (() -> Unit)? = null,
) {
    val colors = palette
    Column(
        Modifier.fillMaxWidth().then(modifier).combinedClickable(
            enabled = onClick != null || onLongClick != null,
            onClick = { onClick?.invoke() }, onLongClick = if (dragPayload == null) onLongClick else null,
        ).then(if (dragPayload != null) Modifier.holdToDrag(dragPayload, onLongClick) else Modifier),
    ) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 44.dp).padding(start = 16.dp + indent, end = 16.dp, top = 10.dp, bottom = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (glyph != null) {
                GlyphIcon(glyph, tint, 24.dp)
                Spacer(Modifier.width(14.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(title, style = Type.body, color = titleColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (subtitle != null) Text(subtitle, style = Type.subheadline, color = colors.secondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            if (detail != null) Text(detail, style = Type.body, color = colors.secondary)
            trailing?.invoke()
            if (chevron) {
                Spacer(Modifier.width(6.dp))
                GlyphIcon(Glyph.Chevron, colors.tertiary, 14.dp)
            }
        }
        if (divider) HorizontalDivider(Modifier.padding(start = indent + if (glyph != null) 54.dp else 16.dp), 0.5.dp, colors.separator)
    }
}

// ================================================================
// SEARCH, TEXT INPUT
// ================================================================

@Composable
fun SearchField(value: String, onChange: (String) -> Unit, placeholder: String = "Suchen", modifier: Modifier = Modifier) {
    val colors = palette
    Row(
        modifier.fillMaxWidth().height(36.dp).clip(RoundedCornerShape(10.dp)).background(colors.fill).padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        GlyphIcon(Glyph.Search, colors.secondary, 16.dp)
        Spacer(Modifier.width(6.dp))
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) Text(placeholder, style = Type.body, color = colors.secondary)
            BasicTextField(value, onChange, singleLine = true, textStyle = Type.body.copy(color = colors.label),
                cursorBrush = SolidColor(colors.accent), modifier = Modifier.fillMaxWidth())
        }
        if (value.isNotEmpty()) {
            Box(Modifier.size(28.dp).clickable { onChange("") }, contentAlignment = Alignment.Center) {
                GlyphIcon(Glyph.Close, colors.secondary, 12.dp)
            }
        }
    }
}

@Composable
fun InputRow(
    value: String,
    onChange: (String) -> Unit,
    placeholder: String,
    password: Boolean = false,
    divider: Boolean = true,
    keyboard: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Next,
    onDone: () -> Unit = {},
    focusRequester: FocusRequester? = null,
) {
    val colors = palette
    Column {
        Box(Modifier.fillMaxWidth().heightIn(min = 46.dp).padding(horizontal = 16.dp), contentAlignment = Alignment.CenterStart) {
            if (value.isEmpty()) Text(placeholder, style = Type.body, color = colors.tertiary)
            BasicTextField(
                value, onChange, singleLine = true,
                textStyle = Type.body.copy(color = colors.label),
                cursorBrush = SolidColor(colors.accent),
                visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
                keyboardOptions = KeyboardOptions(keyboardType = if (password) KeyboardType.Password else keyboard, imeAction = imeAction),
                keyboardActions = KeyboardActions(onDone = { onDone() }, onGo = { onDone() }),
                modifier = Modifier.fillMaxWidth().let { if (focusRequester != null) it.focusRequester(focusRequester) else it },
            )
        }
        if (divider) HorizontalDivider(Modifier.padding(start = 16.dp), 0.5.dp, colors.separator)
    }
}

@Composable
fun PrimaryButton(label: String, enabled: Boolean = true, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val colors = palette
    Box(
        modifier.fillMaxWidth().height(50.dp).clip(RoundedCornerShape(12.dp))
            .background(if (enabled) colors.accent else colors.fill)
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = Type.headline, color = if (enabled) Color.White else colors.secondary)
    }
}

// ================================================================
// TAB BAR
// ================================================================

data class TabItem(val glyph: Glyph, val label: String, val badge: Int = 0)

@Composable
fun TabBar(items: List<TabItem>, selected: Int, onSelect: (Int) -> Unit) {
    val colors = palette
    Column(Modifier.fillMaxWidth().background(colors.bar)) {
        HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
        Row(Modifier.fillMaxWidth().navigationBarsPadding().height(54.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
            items.forEachIndexed { index, item ->
                val active = index == selected
                Column(
                    Modifier.weight(1f).clickable(
                        interactionSource = remember { MutableInteractionSource() }, indication = null,
                    ) { onSelect(index) }.padding(top = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Box {
                        GlyphIcon(item.glyph, if (active) colors.accent else colors.secondary, 26.dp)
                        if (item.badge > 0) {
                            Box(
                                Modifier.align(Alignment.TopEnd).padding(start = 18.dp).clip(RoundedCornerShape(9.dp))
                                    .background(colors.red).padding(horizontal = 5.dp),
                            ) { Text("${item.badge}", style = Type.caption.copy(fontWeight = FontWeight.SemiBold), color = Color.White) }
                        }
                    }
                    Text(item.label, style = Type.caption.copy(fontSize = Type.caption.fontSize * 0.85f, fontWeight = FontWeight.Medium),
                        color = if (active) colors.accent else colors.secondary)
                }
            }
        }
    }
}

// ================================================================
// ALERTS AND ACTION SHEETS (iOS style)
// ================================================================

@Composable
fun AlertDialog(
    title: String,
    message: String? = null,
    confirm: String,
    destructive: Boolean = false,
    fields: List<AlertField> = emptyList(),
    onDismiss: () -> Unit,
    onConfirm: (List<String>) -> Unit,
) {
    val colors = palette
    val values = remember { fields.map { mutableStateOf(it.initial) } }
    val focus = remember { FocusRequester() }
    Dialog(onDismissRequest = onDismiss) {
        Column(
            Modifier.width(290.dp).clip(RoundedCornerShape(14.dp)).background(if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2)),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(title, style = Type.headline, color = colors.label, textAlign = TextAlign.Center)
                if (message != null) {
                    Spacer(Modifier.height(4.dp))
                    Text(message, style = Type.footnote, color = colors.label, textAlign = TextAlign.Center)
                }
                fields.forEachIndexed { index, field ->
                    Spacer(Modifier.height(10.dp))
                    Box(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(7.dp)).background(colors.surface).padding(horizontal = 8.dp, vertical = 8.dp),
                    ) {
                        if (values[index].value.isEmpty()) Text(field.placeholder, style = Type.subheadline, color = colors.tertiary)
                        BasicTextField(
                            values[index].value, { values[index].value = it }, singleLine = true,
                            textStyle = Type.subheadline.copy(color = colors.label),
                            cursorBrush = SolidColor(colors.accent),
                            visualTransformation = if (field.password) PasswordVisualTransformation() else VisualTransformation.None,
                            keyboardOptions = KeyboardOptions(keyboardType = if (field.password) KeyboardType.Password else KeyboardType.Text),
                            modifier = Modifier.fillMaxWidth().let { if (index == 0) it.focusRequester(focus) else it },
                        )
                    }
                }
            }
            HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
            Row(Modifier.fillMaxWidth().height(46.dp)) {
                Box(Modifier.weight(1f).fillMaxSize().clickable(onClick = onDismiss), contentAlignment = Alignment.Center) {
                    Text("Abbrechen", style = Type.body, color = colors.accentText)
                }
                Box(Modifier.width(0.5.dp).fillMaxSize().background(colors.separator))
                Box(
                    Modifier.weight(1f).fillMaxSize().clickable { onConfirm(values.map { it.value }) },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(confirm, style = Type.headline, color = if (destructive) colors.red else colors.accentText)
                }
            }
        }
    }
    if (fields.isNotEmpty()) LaunchedEffect(Unit) { focus.requestFocus() }
}

/** Full-screen dialogs are sized for the whole display but placed below the
 *  status bar and camera cutout – their bottom would be cut off. Let them
 *  cover the whole screen instead. */
@Composable
fun UseWholeScreen() {
    val window = (androidx.compose.ui.platform.LocalView.current.parent as? androidx.compose.ui.window.DialogWindowProvider)?.window
    androidx.compose.runtime.SideEffect {
        if (window != null && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            window.attributes = window.attributes.apply {
                layoutInDisplayCutoutMode = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R)
                    android.view.WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
                else android.view.WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
                // Do not keep clear of the status bar either; the content pads itself.
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) fitInsetsTypes = 0
            }
        }
    }
}

data class AlertField(val placeholder: String, val initial: String = "", val password: Boolean = false)

data class SheetAction(val label: String, val destructive: Boolean = false, val onClick: () -> Unit)

@Composable
fun ActionSheet(title: String?, actions: List<SheetAction>, onDismiss: () -> Unit) {
    val colors = palette
    val sheet = if (colors.dark) Color(0xFF2C2C2E) else Color(0xFFF7F7F7)
    // Draw behind the system bars ourselves so navigationBarsPadding() gets real insets.
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        UseWholeScreen()
        Box(Modifier.fillMaxSize().clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onDismiss)) {
            Column(Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(8.dp)) {
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(sheet)) {
                    if (title != null) {
                        Text(title, style = Type.footnote.copy(fontWeight = FontWeight.SemiBold), color = colors.secondary,
                            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(14.dp))
                        HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
                    }
                    actions.forEachIndexed { index, action ->
                        Box(
                            Modifier.fillMaxWidth().height(56.dp).clickable { onDismiss(); action.onClick() },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(action.label, style = Type.body.copy(fontSize = Type.body.fontSize * 1.1f),
                                color = if (action.destructive) colors.red else colors.accentText)
                        }
                        if (index < actions.lastIndex) HorizontalDivider(thickness = 0.5.dp, color = colors.separator)
                    }
                }
                Spacer(Modifier.height(8.dp))
                Box(
                    Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(14.dp)).background(sheet).clickable(onClick = onDismiss),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("Abbrechen", style = Type.headline.copy(fontSize = Type.body.fontSize * 1.1f), color = colors.accentText)
                }
            }
        }
    }
}

@Composable
fun EmptyState(title: String, message: String? = null, glyph: Glyph = Glyph.Notes) {
    val colors = palette
    Column(Modifier.fillMaxWidth().padding(top = 80.dp, start = 32.dp, end = 32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        GlyphIcon(glyph, colors.tertiary, 56.dp)
        Spacer(Modifier.height(14.dp))
        Text(title, style = Type.title3, color = colors.secondary, textAlign = TextAlign.Center)
        if (message != null) {
            Spacer(Modifier.height(6.dp))
            Text(message, style = Type.subheadline, color = colors.tertiary, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun Toast(text: String?) {
    val colors = palette
    AnimatedVisibility(text != null, enter = fadeIn(), exit = fadeOut()) {
        Box(Modifier.fillMaxSize().padding(bottom = 90.dp), contentAlignment = Alignment.BottomCenter) {
            Text(
                text.orEmpty(), style = Type.subheadline, color = if (colors.dark) Color.Black else Color.White,
                modifier = Modifier.clip(RoundedCornerShape(20.dp)).background(if (colors.dark) Color.White else Color(0xE6222222))
                    .padding(horizontal = 16.dp, vertical = 10.dp),
            )
        }
    }
}

val HairlineWidth: Dp = 0.5.dp
