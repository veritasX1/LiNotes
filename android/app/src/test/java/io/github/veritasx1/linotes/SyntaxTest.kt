package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Syntax
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Code colors – the same cases as tests/test_syntax.py. */
class SyntaxTest {
    private fun words(line: String, lang: String) = Syntax.tokens(line, lang).map { line.substring(it.start, it.end) to it.kind }

    @Test
    fun tokens() {
        assertEquals(listOf("def" to "keyword", "2" to "number", "# sum" to "comment"), words("def add(a, b=2):  # sum", "python"))
        assertEquals(listOf("'it\\'s'" to "string", "\"#no comment\"" to "string"), words("x = 'it\\'s' + \"#no comment\"", "python"))
        assertEquals(listOf("val" to "keyword", "3.5" to "number", "// count" to "comment"), words("val total = items.size * 3.5 // count", "kotlin"))
        assertEquals(listOf("if" to "keyword", "\"\$1\"" to "string", "\"-v\"" to "string", "then" to "keyword", "echo" to "keyword", "fi" to "keyword"),
            words("if [ \"\$1\" = \"-v\" ]; then echo \$# fi", "shell"))
        assertEquals(listOf("\"name\"" to "string", "\"LiNotes\"" to "string", "\"pro\"" to "string", "true" to "keyword", "\"n\"" to "string", "2" to "number"),
            words("{\"name\": \"LiNotes\", \"pro\": true, \"n\": 2}", "json"))
        assertEquals(listOf("\"offen" to "string"), words("print(\"offen", "python"))
        assertEquals(listOf("# Liste" to "comment"), words("ls a#b  # Liste", "shell"))
        assertTrue(Syntax.tokens("anything", "cobol").isEmpty() && Syntax.tokens("", "python").isEmpty())
        assertEquals(listOf("10" to "number"), words("variable2 = 10", "python"))
    }
}
