package io.github.veritasx1.linotes.data

/** Code with syntax colors (a Profi-Funktion): a small line-by-line tokenizer – keywords, strings,
 *  comments and numbers. Only for display, never stored. The same rules as Ubuntu's syntax.py
 *  (SyntaxTest has the same cases as tests/test_syntax.py). */
object Syntax {
    val LANGUAGES = linkedMapOf("python" to "Python", "kotlin" to "Kotlin", "shell" to "Shell", "json" to "JSON")
    private val KEYWORDS = mapOf(
        "python" to setOf("False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda",
            "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield", "self"),
        "kotlin" to setOf("as", "break", "class", "continue", "do", "else", "false", "for", "fun", "if", "in", "interface", "is",
            "null", "object", "package", "return", "super", "this", "throw", "true", "try", "typealias", "val", "var",
            "when", "while", "import", "private", "override", "data", "enum", "sealed", "companion", "const",
            "lateinit", "by", "catch", "finally", "internal", "open", "suspend"),
        "shell" to setOf("if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac", "in",
            "function", "return", "export", "local", "echo", "cd", "exit", "set", "unset", "read", "source", "sudo"),
        "json" to setOf("true", "false", "null"),
    )
    private val COMMENT = mapOf("python" to "#", "shell" to "#", "kotlin" to "//")
    private val TOKEN = Regex("""(?<string>"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?)|(?<number>\b\d+(?:\.\d+)?\b)|(?<word>[A-Za-z_$][\w$]*)""")

    data class Token(val start: Int, val end: Int, val kind: String)

    fun tokens(line: String, lang: String?): List<Token> {
        if (lang == null || lang !in LANGUAGES) return emptyList()
        val marker = COMMENT[lang]
        val result = mutableListOf<Token>()
        var position = 0
        while (position < line.length) {
            if (lang == "shell" && line[position] == '$') { position += 2; continue }  // "$#", "$1" are variables
            // In shell scripts "#" starts a comment only at the start of a word.
            val wordStart = lang != "shell" || position == 0 || line[position - 1].isWhitespace()
            if (marker != null && wordStart && line.startsWith(marker, position)) {
                result.add(Token(position, line.length, "comment"))
                break
            }
            val match = TOKEN.matchAt(line, position)
            if (match == null) { position++; continue }
            when {
                match.groups["string"] != null -> result.add(Token(match.range.first, match.range.last + 1, "string"))
                match.groups["number"] != null -> result.add(Token(match.range.first, match.range.last + 1, "number"))
                match.value in KEYWORDS.getValue(lang) -> result.add(Token(match.range.first, match.range.last + 1, "keyword"))
            }
            position = match.range.last + 1
        }
        return result
    }
}
