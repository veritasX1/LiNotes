package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.ui.RichEditor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Hochformatfotos: Pixel quer gespeichert, Drehung im EXIF (Orientation 6). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class ImageOrientationTest {

    @Test
    fun portraitPhotoIsRotatedUpright() {
        val bytes = javaClass.classLoader!!.getResourceAsStream("portrait_exif6.jpg").readBytes()
        val bitmap = RichEditor.decodeImage(bytes)!!
        assertEquals(200, bitmap.width)
        assertEquals(400, bitmap.height)
        // Der rote Streifen links im Rohbild liegt nach 90° im Uhrzeigersinn oben.
        val top = bitmap.getPixel(100, 20)
        val bottom = bitmap.getPixel(100, 380)
        assertTrue("oben rot", android.graphics.Color.red(top) > 180 && android.graphics.Color.green(top) < 90)
        assertTrue("unten weiß", android.graphics.Color.green(bottom) > 200)
    }
}
