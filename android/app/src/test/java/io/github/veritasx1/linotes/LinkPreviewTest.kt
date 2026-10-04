package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.LinkPreview
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Link previews – the same cases as tests/test_link_preview.py (fetching is tested on the device). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LinkPreviewTest {
    private val og = """<html><head><meta charset="utf-8"><title>Fallback</title>
<meta property="og:title" content="Gartenhaus &amp; Werkzeug">
<meta property="og:description" content="  Alles   für den Garten  ">
<meta property="og:image" content="/bild.png"><meta property="og:site_name" content="Baumarkt">
</head><body>…</body></html>"""
    private val plain = "<html><head><title>  Nur   ein Titel </title><meta name=description content='Kurz'></head></html>"

    @Test
    fun preview() {
        assertEquals("https://example.org/a?b=1", LinkPreview.loneUrl("https://example.org/a?b=1"))
        assertEquals("http://x.de", LinkPreview.loneUrl("  http://x.de  "))
        assertNull(LinkPreview.loneUrl("siehe https://x.de")); assertNull(LinkPreview.loneUrl("www.x.de"))
        assertNull(LinkPreview.loneUrl("ftp://x.de")); assertNull(LinkPreview.loneUrl(""))
        assertEquals("example.org", LinkPreview.domain("https://www.Example.org/x"))

        assertEquals(LinkPreview.Found("Gartenhaus & Werkzeug", "Alles für den Garten", "https://shop.example.org/bild.png", "Baumarkt"),
            LinkPreview.parse(og, "https://shop.example.org/gartenhaus"))
        assertEquals(LinkPreview.Found("Nur ein Titel", "Kurz", "", "x.de"), LinkPreview.parse(plain, "https://www.x.de/"))
        assertEquals("x.de", LinkPreview.parse("<<kaputt", "https://x.de").site)

        val found = LinkPreview.parse(og, "https://shop.example.org/gartenhaus")
        assertEquals("""{"t":"link","x":"https:\/\/x.de\/s","u":"https:\/\/x.de\/s","n":"Gartenhaus & Werkzeug","dm":"Baumarkt","ds":"Alles für den Garten","f":"f1:n1"}""",
            LinkPreview.block("https://x.de/s", found, "f1:n1").toString())
        assertEquals("x.de", LinkPreview.block("https://x.de", LinkPreview.Found("", "", "", "")).getString("n"))
    }
}
