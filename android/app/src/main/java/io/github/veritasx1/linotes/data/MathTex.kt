package io.github.veritasx1.linotes.data

/** Formulas in LaTeX notation, set the way TeX does it – a small, offline part of TeX: fractions,
 *  roots, indices, Greek letters, sums and integrals with limits, growing brackets, matrices, cases,
 *  aligned equations, accents and the usual symbols. No library: the layout gives drawing steps
 *  (text, rules, lines) that a Canvas draws in the editor and the PDF. Twin of Ubuntu's mathtex.py –
 *  MathTexTest checks both against linux/tests/data/math-cases.json; keep them in step.
 *
 *  A formula block in a note: {"t": "math", "x": "<LaTeX>"}. Older LiNotes versions show the source. */
object MathTex {
    const val AXIS = 0.26
    const val ASCENT = 0.72
    const val DESCENT = 0.22
    private val SCALES = doubleArrayOf(1.0, 1.0, 0.7, 0.5)
    private const val MAX_DEPTH = 40

    private val GREEK = mapOf(
        "alpha" to "α", "beta" to "β", "gamma" to "γ", "delta" to "δ", "epsilon" to "ϵ", "varepsilon" to "ε", "zeta" to "ζ",
        "eta" to "η", "theta" to "θ", "vartheta" to "ϑ", "iota" to "ι", "kappa" to "κ", "lambda" to "λ", "mu" to "μ", "nu" to "ν",
        "xi" to "ξ", "pi" to "π", "varpi" to "ϖ", "rho" to "ρ", "varrho" to "ϱ", "sigma" to "σ", "varsigma" to "ς", "tau" to "τ",
        "upsilon" to "υ", "phi" to "ϕ", "varphi" to "φ", "chi" to "χ", "psi" to "ψ", "omega" to "ω",
    )
    private val GREEK_UPPER = mapOf(
        "Gamma" to "Γ", "Delta" to "Δ", "Theta" to "Θ", "Lambda" to "Λ", "Xi" to "Ξ", "Pi" to "Π", "Sigma" to "Σ",
        "Upsilon" to "Υ", "Phi" to "Φ", "Psi" to "Ψ", "Omega" to "Ω",
    )
    private val SYMBOLS = mapOf(
        "pm" to ("±" to "bin"), "mp" to ("∓" to "bin"), "times" to ("×" to "bin"), "div" to ("÷" to "bin"), "cdot" to ("⋅" to "bin"),
        "ast" to ("∗" to "bin"), "star" to ("⋆" to "bin"), "circ" to ("∘" to "bin"), "bullet" to ("∙" to "bin"), "oplus" to ("⊕" to "bin"),
        "ominus" to ("⊖" to "bin"), "otimes" to ("⊗" to "bin"), "cup" to ("∪" to "bin"), "cap" to ("∩" to "bin"), "setminus" to ("∖" to "bin"),
        "wedge" to ("∧" to "bin"), "land" to ("∧" to "bin"), "vee" to ("∨" to "bin"), "lor" to ("∨" to "bin"),
        "leq" to ("≤" to "rel"), "le" to ("≤" to "rel"), "geq" to ("≥" to "rel"), "ge" to ("≥" to "rel"), "neq" to ("≠" to "rel"), "ne" to ("≠" to "rel"),
        "approx" to ("≈" to "rel"), "equiv" to ("≡" to "rel"), "sim" to ("∼" to "rel"), "simeq" to ("≃" to "rel"), "cong" to ("≅" to "rel"),
        "propto" to ("∝" to "rel"), "ll" to ("≪" to "rel"), "gg" to ("≫" to "rel"), "in" to ("∈" to "rel"), "notin" to ("∉" to "rel"),
        "ni" to ("∋" to "rel"), "subset" to ("⊂" to "rel"), "supset" to ("⊃" to "rel"), "subseteq" to ("⊆" to "rel"), "supseteq" to ("⊇" to "rel"),
        "to" to ("→" to "rel"), "rightarrow" to ("→" to "rel"), "leftarrow" to ("←" to "rel"), "gets" to ("←" to "rel"),
        "leftrightarrow" to ("↔" to "rel"), "Rightarrow" to ("⇒" to "rel"), "Leftarrow" to ("⇐" to "rel"), "Leftrightarrow" to ("⇔" to "rel"),
        "implies" to ("⟹" to "rel"), "iff" to ("⟺" to "rel"), "mapsto" to ("↦" to "rel"), "perp" to ("⊥" to "rel"), "parallel" to ("∥" to "rel"),
        "mid" to ("∣" to "rel"), "colon" to (":" to "punct"),
        "infty" to ("∞" to "ord"), "partial" to ("∂" to "ord"), "nabla" to ("∇" to "ord"), "forall" to ("∀" to "ord"), "exists" to ("∃" to "ord"),
        "nexists" to ("∄" to "ord"), "emptyset" to ("∅" to "ord"), "varnothing" to ("∅" to "ord"), "neg" to ("¬" to "ord"), "lnot" to ("¬" to "ord"),
        "angle" to ("∠" to "ord"), "triangle" to ("△" to "ord"), "hbar" to ("ℏ" to "ord"), "ell" to ("ℓ" to "ord"), "Re" to ("ℜ" to "ord"),
        "Im" to ("ℑ" to "ord"), "aleph" to ("ℵ" to "ord"), "prime" to ("′" to "ord"), "degree" to ("°" to "ord"), "dagger" to ("†" to "ord"),
        "ldots" to ("…" to "inner"), "dots" to ("…" to "inner"), "cdots" to ("⋯" to "inner"), "vdots" to ("⋮" to "ord"), "ddots" to ("⋱" to "ord"),
        "langle" to ("⟨" to "open"), "rangle" to ("⟩" to "close"), "lfloor" to ("⌊" to "open"), "rfloor" to ("⌋" to "close"),
        "lceil" to ("⌈" to "open"), "rceil" to ("⌉" to "close"), "vert" to ("|" to "ord"), "Vert" to ("‖" to "ord"),
        "{" to ("{" to "open"), "}" to ("}" to "close"), "|" to ("‖" to "ord"), "_" to ("_" to "ord"), "%" to ("%" to "ord"),
        "&" to ("&" to "ord"), "#" to ("#" to "ord"), "$" to ("$" to "ord"),
    )
    private val CHARACTERS = mapOf(
        "+" to ("+" to "bin"), "-" to ("−" to "bin"), "*" to ("∗" to "bin"), "=" to ("=" to "rel"), "<" to ("<" to "rel"),
        ">" to (">" to "rel"), ":" to (":" to "rel"), "," to ("," to "punct"), ";" to (";" to "punct"), "(" to ("(" to "open"),
        "[" to ("[" to "open"), ")" to (")" to "close"), "]" to ("]" to "close"), "!" to ("!" to "close"), "?" to ("?" to "close"),
        "/" to ("/" to "ord"), "|" to ("|" to "ord"), "." to ("." to "ord"),
    )
    private val BIG_OPERATORS = mapOf("sum" to "∑", "prod" to "∏", "coprod" to "∐", "int" to "∫", "iint" to "∬", "iiint" to "∭", "oint" to "∮",
        "bigcup" to "⋃", "bigcap" to "⋂", "bigoplus" to "⨁", "bigotimes" to "⨂", "bigvee" to "⋁", "bigwedge" to "⋀")
    private val INTEGRALS = setOf("int", "iint", "iiint", "oint")
    private const val INTEGRAL_SIGNS = "∫∬∭∮"
    private val FUNCTIONS = setOf("sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "coth",
        "log", "ln", "lg", "exp", "det", "dim", "ker", "deg", "gcd", "min", "max", "sup", "inf", "lim", "liminf",
        "limsup", "Pr", "arg", "hom", "mod")
    private val LIMIT_FUNCTIONS = setOf("det", "gcd", "min", "max", "sup", "inf", "lim", "liminf", "limsup", "Pr")
    private val SPACES = mapOf("," to 3.0 / 18, ":" to 4.0 / 18, ">" to 4.0 / 18, ";" to 5.0 / 18, "!" to -3.0 / 18, " " to 6.0 / 18,
        "quad" to 1.0, "qquad" to 2.0, "enspace" to 0.5, "thinspace" to 3.0 / 18)
    private val FONTS = mapOf("mathrm" to "rm", "mathbf" to "bf", "mathit" to "it", "mathsf" to "rm", "mathtt" to "rm", "mathbb" to "bb",
        "mathcal" to "it", "boldsymbol" to "bf", "bm" to "bf")
    private val TEXTS = mapOf("text" to "rm", "textrm" to "rm", "mbox" to "rm", "textbf" to "bf", "textit" to "it", "textsf" to "rm", "texttt" to "rm")
    private val ACCENTS = setOf("hat", "widehat", "bar", "overline", "underline", "vec", "overrightarrow", "dot", "ddot", "tilde", "widetilde")
    private val DELIMITERS = mapOf("(" to "(", ")" to ")", "[" to "[", "]" to "]", "\\{" to "{", "\\}" to "}", "|" to "|", "\\|" to "‖",
        "\\vert" to "|", "\\Vert" to "‖", "\\langle" to "⟨", "\\rangle" to "⟩", "." to "", "<" to "⟨", ">" to "⟩", "\\lfloor" to "⌊",
        "\\rfloor" to "⌋", "\\lceil" to "⌈", "\\rceil" to "⌉", "\\lbrace" to "{", "\\rbrace" to "}")
    private val BIG_SIZES = mapOf("big" to 1.2, "Big" to 1.8, "bigg" to 2.4, "Bigg" to 3.0)
    private val ENVIRONMENTS = mapOf("matrix" to ("" to ""), "pmatrix" to ("(" to ")"), "bmatrix" to ("[" to "]"), "Bmatrix" to ("{" to "}"),
        "vmatrix" to ("|" to "|"), "Vmatrix" to ("‖" to "‖"), "cases" to ("{" to ""), "aligned" to ("" to ""),
        "align" to ("" to ""), "align*" to ("" to ""), "gathered" to ("" to ""), "gather" to ("" to ""), "array" to ("" to ""),
        "split" to ("" to ""))
    private val ALIGNED = setOf("aligned", "align", "align*", "split")
    private val PLAIN = setOf("aligned", "align", "align*", "gathered", "gather", "split")
    private val DOUBLE_STRUCK = mapOf('C' to "ℂ", 'H' to "ℍ", 'N' to "ℕ", 'P' to "ℙ", 'Q' to "ℚ", 'R' to "ℝ", 'Z' to "ℤ")

    private fun doubleStruck(code: Int): String {
        if (code < 0x10000 && code.toChar() in DOUBLE_STRUCK) return DOUBLE_STRUCK.getValue(code.toChar())
        val mapped = when (code) {
            in 'A'.code..'Z'.code -> 0x1D538 + code - 'A'.code
            in 'a'.code..'z'.code -> 0x1D552 + code - 'a'.code
            in '0'.code..'9'.code -> 0x1D7D8 + code - '0'.code
            else -> code
        }
        return String(Character.toChars(mapped))
    }

    private fun isLetter(code: Int) = code in 'a'.code..'z'.code || code in 'A'.code..'Z'.code
    private fun firstCode(text: String) = if (text.isEmpty()) 0 else text.codePointAt(0)
    private fun codePoints(text: String): List<String> {
        val result = mutableListOf<String>()
        var index = 0
        while (index < text.length) {
            val code = text.codePointAt(index)
            result.add(String(Character.toChars(code)))
            index += Character.charCount(code)
        }
        return result
    }
    private fun isSpace(code: Int) = Character.isWhitespace(code) || Character.isSpaceChar(code)

    // ============================================================
    // READING (source → tree)
    // ============================================================

    /** Commands (\frac, \, …), single characters, and " " for any run of white space. */
    fun tokens(source: String): List<String> {
        val chars = codePoints(source)
        val result = mutableListOf<String>()
        var index = 0
        while (index < chars.size) {
            val char = chars[index]
            val code = firstCode(char)
            if (char == "\\") {
                var end = index + 1
                if (end < chars.size && isLetter(firstCode(chars[end]))) {
                    while (end < chars.size && isLetter(firstCode(chars[end]))) end++
                    result.add(chars.subList(index, end).joinToString(""))
                    index = end
                } else {
                    result.add(chars.subList(index, minOf(end + 1, chars.size)).joinToString(""))
                    index = end + 1
                }
            } else if (isSpace(code)) {
                while (index < chars.size && isSpace(firstCode(chars[index]))) index++
                result.add(" ")
            } else if (char == "%") {
                while (index < chars.size && chars[index] != "\n") index++
            } else {
                result.add(char)
                index++
            }
        }
        return result
    }

    /** A node of the formula tree (the fields used depend on the kind, as in mathtex.py's lists). */
    class Node(
        val kind: String, var s: String = "", var cls: String = "", var flag: Boolean = false,
        var a: Node? = null, var b: Node? = null, var c: Node? = null, var list: MutableList<Node> = mutableListOf(),
        var t: String = "", var number: Double = 0.0, var rows: List<List<MutableList<Node>>> = emptyList(),
    )

    private fun sym(char: String, cls: String, italic: Boolean) = Node("sym", s = char, cls = cls, flag = italic)
    private fun error(text: String) = Node("error", s = text)
    private fun group(nodes: MutableList<Node>) = Node("group", list = nodes)

    private class Parser(source: String) {
        val tokens = tokens(source)
        var index = 0
        var depth = 0

        fun peek(skip: Boolean = true): String? {
            if (skip) while (index < tokens.size && tokens[index] == " ") index++
            return if (index < tokens.size) tokens[index] else null
        }

        fun take(skip: Boolean = true): String? {
            val token = peek(skip)
            if (token != null) index++
            return token
        }

        fun rows(inside: Boolean = false): List<List<MutableList<Node>>> {
            val rows = mutableListOf(mutableListOf<MutableList<Node>>())
            while (true) {
                rows.last().add(list(setOf("&", "\\\\", "}", "\\right", "\\end")))
                val token = peek()
                if (token == null || (inside && token == "\\end")) return rows
                index++
                if (token == "\\\\") rows.add(mutableListOf())
                else if (token != "&") rows.last().last().add(error(token))
            }
        }

        fun list(stops: Set<String>): MutableList<Node> {
            val nodes = mutableListOf<Node>()
            depth++
            if (depth > MAX_DEPTH) {
                depth--
                index = tokens.size
                return mutableListOf(error("…"))
            }
            while (true) {
                val token = peek()
                if (token == null || token in stops) break
                index++
                if (token == "^" || token == "_") {
                    attach(nodes, if (token == "^") "sup" else "sub", argument())
                } else if (token == "'") {
                    var primes = "′"
                    while (peek(false) == "'") {
                        index++
                        primes += "′"
                    }
                    attach(nodes, "sup", sym(primes, "ord", false))
                } else if (token == "\\limits" || token == "\\nolimits") {
                    var target = nodes.lastOrNull()
                    if (target != null && target.kind == "scripts") target = target.a
                    if (target != null && (target.kind == "bigop" || target.kind == "op")) target.flag = token == "\\limits"
                } else {
                    nodes.add(atom(token))
                }
            }
            depth--
            return nodes
        }

        fun attach(nodes: MutableList<Node>, where: String, argument: Node) {
            val last = nodes.lastOrNull()
            if (last != null && last.kind == "scripts" && (if (where == "sup") last.b else last.c) == null) {
                if (where == "sup") last.b = argument else last.c = argument
                return
            }
            val base = if (last != null && last.kind != "scripts") nodes.removeAt(nodes.lastIndex) else group(mutableListOf())
            nodes.add(Node("scripts", a = base, b = if (where == "sup") argument else null, c = if (where == "sub") argument else null))
        }

        fun argument(): Node {
            val token = take() ?: return group(mutableListOf())
            if (token in setOf("}", "&", "\\\\", "^", "_")) {
                index--
                return error("{}")
            }
            return atom(token)
        }

        fun group(): Node {
            if (peek() == "{") {
                index++
                val nodes = list(setOf("}"))
                if (take() != "}") nodes.add(error("}"))
                return group(nodes)
            }
            return argument()
        }

        fun rawGroup(): String {
            if (peek() != "{") return take() ?: ""
            index++
            val text = StringBuilder()
            var depth = 0
            while (index < tokens.size) {
                val token = tokens[index]
                index++
                if (token == "{") depth++
                else if (token == "}") {
                    if (depth == 0) return text.toString()
                    depth--
                }
                val parts = codePoints(token)
                text.append(if (parts.size == 2 && parts[0] == "\\" && !isLetter(firstCode(parts[1]))) parts[1] else token)
            }
            return text.toString()
        }

        fun delimiter(): String? {
            val token = take() ?: return ""
            return DELIMITERS[token]
        }

        fun atom(token: String): Node {
            if (token == "{") {
                val nodes = list(setOf("}"))
                if (take() != "}") nodes.add(error("}"))
                return group(nodes)
            }
            if (token == "}") return error("}")
            if (!token.startsWith("\\")) {
                CHARACTERS[token]?.let { (char, kind) -> return sym(char, kind, false) }
                if (token == "~") return Node("space", number = 6.0 / 18)
                if (token == "&") return error("&")
                return sym(token, "ord", Character.isLetter(firstCode(token)))
            }
            val name = token.substring(1)
            GREEK[name]?.let { return sym(it, "ord", true) }
            GREEK_UPPER[name]?.let { return sym(it, "ord", false) }
            SYMBOLS[name]?.let { (char, kind) -> return sym(char, kind, false) }
            SPACES[name]?.let { return Node("space", number = it) }
            when (name) {
                "frac", "dfrac", "tfrac", "cfrac" -> {
                    val top = group()
                    val bottom = group()
                    return Node("frac", a = top, b = bottom, flag = true)
                }
                "binom", "dbinom", "tbinom" -> {
                    val top = group()
                    val bottom = group()
                    return Node("leftright", s = "(", list = mutableListOf(Node("frac", a = top, b = bottom, flag = false)), t = ")")
                }
                "sqrt" -> {
                    var rootIndex: Node? = null
                    if (peek() == "[") {
                        index++
                        rootIndex = group(list(setOf("]")))
                        take()
                    }
                    return Node("sqrt", a = group(), b = rootIndex)
                }
            }
            BIG_OPERATORS[name]?.let { return Node("bigop", s = it, flag = name !in INTEGRALS) }
            if (name in FUNCTIONS) return Node("op", s = name, flag = name in LIMIT_FUNCTIONS)
            if (name == "operatorname") return Node("op", s = rawGroup(), flag = false)
            TEXTS[name]?.let { return Node("text", s = rawGroup(), cls = it) }
            FONTS[name]?.let { return Node("font", cls = it, a = group()) }
            if (name in ACCENTS) return Node("accent", s = name, a = group())
            if (name == "left") {
                val left = delimiter()
                val body = list(setOf("\\right"))
                var right: String? = ""
                if (peek() == "\\right") {
                    index++
                    right = delimiter()
                }
                if (left == null || right == null) return error("\\left")
                return Node("leftright", s = left, list = body, t = right)
            }
            if (name == "right") return error(token)
            val bigName = name.trimEnd('l', 'r', 'm')
            if (bigName in BIG_SIZES && name != "bigcup" && name != "bigcap") {
                val size = BIG_SIZES.getValue(bigName)
                val char = delimiter()
                return if (char != null) Node("bigdelim", s = char, number = size) else error(token)
            }
            if (name == "begin") {
                val environment = rawGroup()
                if (environment == "array" && peek() == "{") rawGroup()
                val rows = rows(inside = true)
                if (take() != "\\end" || rawGroup() != environment || environment !in ENVIRONMENTS) return error("\\begin{$environment}")
                return Node("matrix", s = environment, rows = rows)
            }
            return error(token)
        }
    }

    fun parse(source: String) = Parser(source).rows()

    // ============================================================
    // SETTING (tree → boxes → drawing steps)
    // ============================================================

    sealed class Item
    class TextItem(val x: Double, val y: Double, val text: String, val size: Double, val style: String) : Item()
    class RuleItem(val x: Double, val y: Double, val w: Double, val h: Double) : Item()
    class PathItem(val points: List<Pair<Double, Double>>, val thick: Double) : Item()
    class BoxItem(val x: Double, val y: Double, val box: Box) : Item()

    class Box(var width: Double = 0.0, var ascent: Double = 0.0, var descent: Double = 0.0,
              val items: MutableList<Item> = mutableListOf(), var kind: String? = "ord")

    private class Setter(val size: Double, val measure: (String, Double, String) -> Double) {
        fun text(text: String, size: Double, style: String, kind: String = "ord") =
            Box(measure(text, size, style), ASCENT * size, DESCENT * size, mutableListOf(TextItem(0.0, 0.0, text, size, style)), kind)

        fun space(left: String?, right: String?, level: Int, size: Double): Double {
            if (left == null || right == null) return 0.0
            val mu = size / 18
            if ((left == "op" || right == "op") && left !in setOf("open", "punct") && right !in setOf("close", "punct", "rel", "bin")) return 3 * mu
            if (level >= 2) return 0.0
            if (left == "rel" || right == "rel") return if (left == right || left == "open" || right in setOf("close", "punct")) 0.0 else 5 * mu
            if (left == "bin" || right == "bin") return 4 * mu
            if (left == "punct" || (left == "inner" && right !in setOf("close", "punct")) || (right == "inner" && left != "open")) return 3 * mu
            return 0.0
        }

        fun row(nodes: List<Node>, level: Int, font: String?): Box {
            val size = this.size * SCALES[level]
            val boxes = nodes.map { node(it, level, font) }
            var previous: String? = null
            boxes.forEachIndexed { index, box ->
                if (box.kind == null) return@forEachIndexed
                if (box.kind == "bin") {
                    val following = boxes.drop(index + 1).firstOrNull { it.kind != null }?.kind
                    if (previous in setOf(null, "bin", "rel", "open", "punct", "op") || following in setOf(null, "rel", "close", "punct")) box.kind = "ord"
                }
                previous = box.kind
            }
            val result = Box()
            previous = null
            var x = 0.0
            for (box in boxes) {
                if (box.kind != null) {
                    x += space(previous, box.kind, level, size)
                    previous = box.kind
                }
                result.items.add(BoxItem(x, 0.0, box))
                x += box.width
                result.ascent = maxOf(result.ascent, box.ascent)
                result.descent = maxOf(result.descent, box.descent)
            }
            result.width = x
            if (boxes.size == 1) result.kind = boxes[0].kind
            return result
        }

        fun node(node: Node, level: Int, font: String?): Box {
            val size = this.size * SCALES[level]
            return when (node.kind) {
                "sym" -> {
                    var char = node.s
                    var style = if (node.flag) "it" else "rm"
                    val first = firstCode(char)
                    if (font == "bb") {
                        char = codePoints(char).joinToString("") { doubleStruck(firstCode(it)) }
                        style = "rm"
                    } else if ((font == "rm" || font == "bf") && (isLetter(first) || Character.isDigit(first) || node.flag)) {
                        style = font
                    } else if (font == "it" && isLetter(first)) {
                        style = "it"
                    } else if (font == "bf") {
                        style = "bf"
                    }
                    text(char, size, style, node.cls)
                }
                "group" -> row(node.list, level, font)
                "font" -> node(node.a!!, level, node.cls)
                "text" -> text(node.s.ifEmpty { " " }, size, node.cls)
                "space" -> Box(node.number * size, kind = null)
                "error" -> text(node.s, size, "err")
                "frac" -> fraction(node.a!!, node.b!!, node.flag, level, font)
                "sqrt" -> root(node.a!!, node.b, level, font)
                "scripts" -> scripts(node.a!!, node.b, node.c, level, font)
                "bigop" -> bigOperator(node.s, level)
                "op" -> text(node.s, size, "rm", "op")
                "leftright" -> fence(node.s, row(node.list, level, font), node.t, level)
                "bigdelim" -> {
                    val box = delimiter(node.s, node.number * size, size)
                    box.kind = if ("([{⟨⌊⌈".contains(node.s)) "open" else if (")]}⟩⌋⌉".contains(node.s)) "close" else "ord"
                    box
                }
                "accent" -> accent(node.s, node.a!!, level, font)
                "matrix" -> matrix(node.s, node.rows, level, font)
                else -> Box()
            }
        }

        fun fraction(top: Node, bottom: Node, rule: Boolean, level: Int, font: String?): Box {
            val size = this.size * SCALES[level]
            val inner = minOf(level + 1, 3)
            val num = node(top, inner, font)
            val den = node(bottom, inner, font)
            val thick = if (rule) 0.06 * size else 0.0
            val gap = (if (level == 0) 0.14 else 0.08) * size
            val pad = 0.12 * size
            val width = maxOf(num.width, den.width) + 2 * pad
            val axis = AXIS * size
            val up = axis + thick / 2 + gap + num.descent
            val down = axis - thick / 2 - gap - den.ascent
            val items = mutableListOf<Item>(BoxItem((width - num.width) / 2, up, num), BoxItem((width - den.width) / 2, down, den))
            if (rule) items.add(RuleItem(pad / 2, axis - thick / 2, width - pad, thick))
            return Box(width, up + num.ascent, den.descent - down, items, "inner")
        }

        fun root(bodyNode: Node, indexNode: Node?, level: Int, font: String?): Box {
            val size = this.size * SCALES[level]
            val body = node(bodyNode, level, font)
            val thick = 0.06 * size
            val gap = (if (level == 0) 0.12 else 0.08) * size
            val top = maxOf(body.ascent, ASCENT * size * 0.9) + gap
            val bottom = maxOf(body.descent, DESCENT * size * 0.5)
            val height = top + bottom
            val sign = 0.55 * size
            var shift = 0.0
            var index: Box? = null
            if (indexNode != null) {
                index = node(indexNode, 3, font)
                shift = maxOf(0.0, index.width - 0.28 * size)
            }
            val x = shift
            val points = listOf(x to -bottom + 0.42 * height, x + 0.14 * size to -bottom + 0.5 * height, x + 0.32 * size to -bottom,
                x + sign to top + thick / 2, x + sign + body.width + 0.1 * size to top + thick / 2)
            val items = mutableListOf<Item>(PathItem(points, thick), BoxItem(x + sign, 0.0, body))
            var ascent = top + thick
            if (index != null) {
                val indexUp = -bottom + 0.62 * height + index.descent
                items.add(BoxItem(x + 0.3 * size - index.width, indexUp, index))
                ascent = maxOf(ascent, indexUp + index.ascent)
            }
            return Box(x + sign + body.width + 0.12 * size, ascent, bottom + thick, items)
        }

        fun bigOperator(char: String, level: Int): Box {
            val size = this.size * SCALES[level]
            var glyph = (if (level == 0) 1.55 else 1.15) * size
            if (INTEGRAL_SIGNS.contains(char)) glyph = (if (level == 0) 1.8 else 1.25) * size
            val base = AXIS * size - 0.27 * glyph
            val width = measure(char, glyph, "rm")
            return Box(width, base + 0.78 * glyph, 0.26 * glyph - base, mutableListOf(TextItem(0.0, base, char, glyph, "rm")), "op")
        }

        fun scripts(baseNode: Node, supNode: Node?, subNode: Node?, level: Int, font: String?): Box {
            val size = this.size * SCALES[level]
            val base = node(baseNode, level, font)
            val inner = if (level < 2) 2 else 3
            val sup = supNode?.let { node(it, inner, font) }
            val sub = subNode?.let { node(it, inner, font) }
            val limits = (baseNode.kind == "bigop" || baseNode.kind == "op") && level == 0 && baseNode.flag
            if (limits) {
                val gap = 0.12 * size
                val width = maxOf(base.width, sup?.width ?: 0.0, sub?.width ?: 0.0)
                val items = mutableListOf<Item>(BoxItem((width - base.width) / 2, 0.0, base))
                var ascent = base.ascent
                var descent = base.descent
                if (sup != null) {
                    val up = base.ascent + gap + sup.descent
                    items.add(BoxItem((width - sup.width) / 2, up, sup))
                    ascent = up + sup.ascent
                }
                if (sub != null) {
                    val down = base.descent + gap + sub.ascent
                    items.add(BoxItem((width - sub.width) / 2, -down, sub))
                    descent = down + sub.descent
                }
                return Box(width, ascent, descent, items, "op")
            }
            val up = if (sup != null) maxOf(base.ascent - 0.38 * size, 0.38 * size) else 0.0
            var down = if (sub != null) maxOf(base.descent - 0.1 * size, 0.18 * size) else 0.0
            if (sup != null && sub != null) {
                down = maxOf(down, 0.26 * size)
                val gap = (up - sup.descent) - (sub.ascent - down)
                if (gap < 0.12 * size) down += 0.12 * size - gap
            }
            val items = mutableListOf<Item>(BoxItem(0.0, 0.0, base))
            var width = 0.0
            var ascent = base.ascent
            var descent = base.descent
            val integral = baseNode.kind == "bigop" && INTEGRAL_SIGNS.contains(baseNode.s)
            var x = base.width + (if (baseNode.kind == "sym" && baseNode.flag) 0.03 * size else 0.0)
            if (integral) x -= 0.1 * size
            if (sup != null) {
                items.add(BoxItem(x, up, sup))
                width = maxOf(width, sup.width)
                ascent = maxOf(ascent, up + sup.ascent)
            }
            if (sub != null) {
                val subX = if (!integral) base.width else base.width - 0.25 * size
                items.add(BoxItem(subX, -down, sub))
                width = maxOf(width, subX - x + sub.width)
                descent = maxOf(descent, down + sub.descent)
            }
            return Box(x + width + 0.04 * size, ascent, descent, items, base.kind)
        }

        fun fence(left: String, body: Box, right: String, level: Int): Box {
            val size = this.size * SCALES[level]
            val axis = AXIS * size
            val half = maxOf(body.ascent - axis, body.descent + axis)
            val height = maxOf(2 * half + 0.16 * size, 1.1 * size)
            val leftBox = delimiter(left, height, size)
            val rightBox = delimiter(right, height, size)
            val items = mutableListOf<Item>(BoxItem(0.0, 0.0, leftBox), BoxItem(leftBox.width, 0.0, body),
                BoxItem(leftBox.width + body.width, 0.0, rightBox))
            return Box(leftBox.width + body.width + rightBox.width, maxOf(body.ascent, leftBox.ascent),
                maxOf(body.descent, leftBox.descent), items, "inner")
        }

        /** A bracket of any height, drawn as lines (fonts only have a few sizes). */
        fun delimiter(char: String, height: Double, size: Double): Box {
            if (char.isEmpty()) return Box(0.1 * size, kind = "ord")
            val axis = AXIS * size
            val top = axis + height / 2
            val bottom = axis - height / 2
            val middle = axis
            val thick = 0.06 * size
            val pad = 0.08 * size
            val width = when {
                "()".contains(char) -> minOf(0.28 * size + 0.06 * height, 0.7 * size)
                "{}".contains(char) -> 0.5 * size
                "|‖".contains(char) -> (if (char == "|") 0.3 else 0.45) * size
                else -> 0.36 * size
            }
            val inner = pad
            val outer = width - pad
            val opening = "(⟨[{⌊⌈".contains(char)
            val near = if (opening) inner else outer
            val far = if (opening) outer else inner
            val paths = mutableListOf<List<Pair<Double, Double>>>()
            when {
                "()".contains(char) -> {
                    val control = 2 * near - far
                    paths.add((0..12).map { step ->
                        val t = step / 12.0
                        val y = (1 - t) * (1 - t) * top + 2 * (1 - t) * t * middle + t * t * bottom
                        val x = (1 - t) * (1 - t) * far + 2 * (1 - t) * t * control + t * t * far
                        x to y
                    })
                }
                "[]".contains(char) -> paths.add(listOf(far to top, near to top, near to bottom, far to bottom))
                "⌊⌋".contains(char) -> paths.add(listOf(near to top, near to bottom, far to bottom))
                "⌈⌉".contains(char) -> paths.add(listOf(far to top, near to top, near to bottom))
                "⟨⟩".contains(char) -> paths.add(listOf(far to top, near to middle, far to bottom))
                "{}".contains(char) -> {
                    val centre = width / 2
                    paths.add(listOf(far to top, centre to top - 0.06 * height, centre to middle + 0.06 * height, near to middle,
                        centre to middle - 0.06 * height, centre to bottom + 0.06 * height, far to bottom))
                }
                char == "|" -> paths.add(listOf(width / 2 to top, width / 2 to bottom))
                char == "‖" -> {
                    paths.add(listOf(width / 2 - 0.08 * size to top, width / 2 - 0.08 * size to bottom))
                    paths.add(listOf(width / 2 + 0.08 * size to top, width / 2 + 0.08 * size to bottom))
                }
            }
            return Box(width, top + thick, thick - bottom, paths.map { PathItem(it, thick) }.toMutableList(), "ord")
        }

        fun accent(name: String, bodyNode: Node, level: Int, font: String?): Box {
            val size = this.size * SCALES[level]
            val body = node(bodyNode, level, font)
            val thick = 0.05 * size
            val top = maxOf(body.ascent, ASCENT * size * 0.85) + 0.06 * size
            val slant = if (bodyNode.kind == "sym" && bodyNode.flag) 0.08 * size else 0.0
            val items = mutableListOf<Item>(BoxItem(0.0, 0.0, body))
            var ascent = body.ascent
            var descent = body.descent
            val middle = body.width / 2 + slant
            when (name) {
                "bar", "overline" -> {
                    val inset = if (name == "bar") 0.04 * size else 0.0
                    items.add(RuleItem(inset + slant, top, body.width - 2 * inset, thick))
                    ascent = top + thick
                }
                "underline" -> {
                    val down = body.descent + 0.08 * size
                    items.add(RuleItem(0.0, -down - thick, body.width, thick))
                    descent = down + thick
                }
                "hat", "widehat" -> {
                    val half = if (name == "widehat") body.width / 2 else minOf(body.width / 2, 0.22 * size)
                    items.add(PathItem(listOf(middle - half to top, middle to top + 0.2 * size, middle + half to top), thick))
                    ascent = top + 0.2 * size + thick
                }
                "vec", "overrightarrow" -> {
                    val half = if (name == "overrightarrow") maxOf(body.width / 2, 0.22 * size) else maxOf(minOf(body.width / 2, 0.3 * size), 0.22 * size)
                    val y = top + 0.1 * size
                    items.add(PathItem(listOf(middle - half to y, middle + half to y), thick))
                    items.add(PathItem(listOf(middle + half - 0.13 * size to y + 0.1 * size, middle + half to y,
                        middle + half - 0.13 * size to y - 0.1 * size), thick))
                    ascent = y + 0.1 * size + thick
                }
                "tilde", "widetilde" -> {
                    val half = if (name == "widetilde") body.width / 2 else minOf(body.width / 2, 0.24 * size)
                    val y = top + 0.08 * size
                    val wave = 0.06 * size
                    items.add(PathItem(listOf(middle - half to y - wave, middle - half / 2 to y + wave, middle + half / 2 to y - wave,
                        middle + half to y + wave), thick))
                    ascent = y + wave + thick
                }
                "dot", "ddot" -> {
                    val dot = 0.1 * size
                    val spots = if (name == "dot") listOf(middle) else listOf(middle - 0.12 * size, middle + 0.12 * size)
                    for (spot in spots) items.add(RuleItem(spot - dot / 2, top + 0.02 * size, dot, dot))
                    ascent = top + 0.02 * size + dot
                }
            }
            return Box(body.width, ascent, descent, items, body.kind)
        }

        fun matrix(environment: String, rows: List<List<List<Node>>>, level: Int, font: String?, centred: Boolean = true): Box {
            val size = this.size * SCALES[level]
            val inner = if (environment !in PLAIN) maxOf(level, 1) else level
            val aligned = environment in ALIGNED
            val cells = rows.map { row ->
                row.mapIndexed { column, nodes ->
                    val cell = if (aligned && column % 2 == 1) listOf(group(mutableListOf())) + nodes else nodes
                    row(cell, inner, font)
                }
            }
            val columns = cells.maxOf { it.size }
            val widths = (0 until columns).map { c -> cells.filter { c < it.size }.maxOfOrNull { it[c].width } ?: 0.0 }
            val gaps: List<Double>
            val sides: List<String>
            if (aligned) {
                gaps = (0 until columns).map { if (it % 2 == 0) 0.0 else 1.0 * size }
                sides = (0 until columns).map { if (it % 2 == 0) "right" else "left" }
            } else if (environment == "cases") {
                gaps = List(columns) { 1.0 * size }
                sides = List(columns) { "left" }
            } else {
                gaps = List(columns) { 0.9 * size }
                sides = List(columns) { "centre" }
            }
            val rowGap = (if (aligned || environment == "gathered" || environment == "gather") 0.3 else 0.22) * size
            val heights = cells.map { line ->
                maxOf(ASCENT * size, line.maxOfOrNull { it.ascent } ?: 0.0) to maxOf(DESCENT * size, line.maxOfOrNull { it.descent } ?: 0.0)
            }
            val total = heights.sumOf { it.first + it.second } + rowGap * (cells.size - 1)
            val axis = if (centred) AXIS * size else 0.0
            val top = if (centred) axis + total / 2 else heights[0].first
            val width = if (columns > 0) widths.sum() + gaps.dropLast(1).sum() else 0.0
            val items = mutableListOf<Item>()
            var y = top
            cells.forEachIndexed { rowIndex, line ->
                val (ascent, descent) = heights[rowIndex]
                val baseline = y - ascent
                var x = 0.0
                line.forEachIndexed { column, cell ->
                    val offset = when (sides[column]) {
                        "left" -> 0.0
                        "right" -> widths[column] - cell.width
                        else -> (widths[column] - cell.width) / 2
                    }
                    items.add(BoxItem(x + offset, baseline, cell))
                    x += widths[column] + gaps[column]
                }
                y = baseline - descent - rowGap
            }
            val body = Box(width, top, total - top, items, "inner")
            val (left, right) = ENVIRONMENTS[environment] ?: ("" to "")
            if (left.isEmpty() && right.isEmpty()) {
                val pad = if (environment !in PLAIN) 0.1 * size else 0.0
                return Box(width + 2 * pad, top, total - top, mutableListOf(BoxItem(pad, 0.0, body)), "inner")
            }
            val height = total + 0.2 * size
            val leftBox = delimiter(left, height, size)
            val rightBox = delimiter(right, height, size)
            val outer = mutableListOf<Item>(BoxItem(0.0, 0.0, leftBox), BoxItem(leftBox.width + 0.08 * size, 0.0, body),
                BoxItem(leftBox.width + 0.16 * size + width, 0.0, rightBox))
            return Box(leftBox.width + rightBox.width + width + 0.16 * size, maxOf(top, leftBox.ascent),
                maxOf(total - top, leftBox.descent), outer, "inner")
        }
    }

    /** Drawing steps with the top left corner at (0, 0), y downwards. */
    sealed class Op
    data class Text(val x: Double, val y: Double, val text: String, val size: Double, val style: String) : Op()
    data class Rule(val x: Double, val y: Double, val w: Double, val h: Double) : Op()
    data class Path(val points: List<Pair<Double, Double>>, val thick: Double) : Op()

    class Formula(val width: Double, val ascent: Double, val descent: Double, val ops: List<Op>, val error: Boolean) {
        val height get() = ascent + descent
    }

    private fun flatten(box: Box, x: Double, baseline: Double, ops: MutableList<Op>) {
        for (item in box.items) when (item) {
            is BoxItem -> flatten(item.box, x + item.x, baseline - item.y, ops)
            is TextItem -> ops.add(Text(x + item.x, baseline - item.y, item.text, item.size, item.style))
            is RuleItem -> ops.add(Rule(x + item.x, baseline - item.y - item.h, item.w, item.h))
            is PathItem -> ops.add(Path(item.points.map { (px, py) -> x + px to baseline - py }, item.thick))
        }
    }

    /** Set [source] at font size [size] (display style). [measure] gives a text's width – the only
     *  thing that differs between Android (Paint) and Ubuntu (Pango). */
    fun layout(source: String, size: Double, measure: (String, Double, String) -> Double): Formula {
        val setter = Setter(size, measure)
        val rows = parse(source)
        val box = if (rows.size == 1 && rows[0].size == 1) setter.row(rows[0][0], 0, null)
        else setter.matrix(if (rows.all { it.size == 1 }) "gathered" else "aligned", rows, 0, null, centred = false)
        val ops = mutableListOf<Op>()
        flatten(box, 0.0, box.ascent, ops)
        return Formula(box.width, box.ascent, box.descent, ops, ops.any { it is Text && it.style == "err" })
    }
}
