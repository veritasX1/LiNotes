package io.github.veritasx1.linotes.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Colors after Apple's iOS system colors, with the warm yellow of Notes. */
data class Palette(
    val dark: Boolean,
    val background: Color,        // systemGroupedBackground
    val surface: Color,           // secondarySystemGroupedBackground
    val plain: Color,             // systemBackground (editor)
    val label: Color,
    val secondary: Color,
    val tertiary: Color,
    val separator: Color,
    val fill: Color,              // search fields, chips
    val accent: Color,
    val accentText: Color,        // accent for text buttons (contrast)
    val red: Color,
    val bar: Color,               // translucent bars
    val highlight: Color,
)

val LightPalette = Palette(
    dark = false,
    background = Color(0xFFF2F2F7),
    surface = Color.White,
    plain = Color.White,
    label = Color.Black,
    secondary = Color(0x993C3C43),
    tertiary = Color(0x4D3C3C43),
    separator = Color(0x4A3C3C43),
    fill = Color(0x1F767680),
    accent = Color(0xFFE6A200),
    accentText = Color(0xFFC98C00),
    red = Color(0xFFFF3B30),
    bar = Color(0xF2F9F9F9),
    highlight = Color(0x73FFD83D),
)

val DarkPalette = Palette(
    dark = true,
    background = Color.Black,
    surface = Color(0xFF1C1C1E),
    plain = Color(0xFF1C1C1E),
    label = Color.White,
    secondary = Color(0x99EBEBF5),
    tertiary = Color(0x4DEBEBF5),
    separator = Color(0x99545458),
    fill = Color(0x3D767680),
    accent = Color(0xFFFFCC00),
    accentText = Color(0xFFFFD60A),
    red = Color(0xFFFF453A),
    bar = Color(0xF01C1C1E),
    highlight = Color(0x80B38F00),
)

object Type {
    val largeTitle = TextStyle(fontSize = 34.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.3.sp)
    val title1 = TextStyle(fontSize = 28.sp, fontWeight = FontWeight.Bold)
    val title2 = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.Bold)
    val title3 = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
    val headline = TextStyle(fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
    val body = TextStyle(fontSize = 17.sp)
    val callout = TextStyle(fontSize = 16.sp)
    val subheadline = TextStyle(fontSize = 15.sp)
    val footnote = TextStyle(fontSize = 13.sp)
    val caption = TextStyle(fontSize = 12.sp)
    val sectionHeader = TextStyle(fontSize = 13.sp, letterSpacing = 0.2.sp)
}

val LocalPalette = staticCompositionLocalOf { LightPalette }

@Composable
fun LiNotesTheme(content: @Composable () -> Unit) {
    val palette = if (isSystemInDarkTheme()) DarkPalette else LightPalette
    CompositionLocalProvider(LocalPalette provides palette, content = content)
}

val palette: Palette @Composable get() = LocalPalette.current
