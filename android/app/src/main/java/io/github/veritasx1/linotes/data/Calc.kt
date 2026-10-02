package io.github.veritasx1.linotes.data

import kotlin.math.abs

/** Math in notes, like Apple's Math Notes: "12,5 * 4 =" gets its result, lines such as
 *  "x = 64" define variables for the lines below. Mirrors linux/linotes/calc.py. */
object Calc {
    class CalcError(message: String) : Exception(message)

    private val functions: Map<String, (Double) -> Double> = mapOf(
        "sqrt" to Math::sqrt, "√" to Math::sqrt, "sin" to Math::sin, "cos" to Math::cos, "tan" to Math::tan,
        "ln" to Math::log, "log" to Math::log10, "abs" to { x: Double -> abs(x) },
    )
    private val constants = mapOf("pi" to Math.PI, "π" to Math.PI, "e" to Math.E)
    private const val NAME = "[A-Za-zÄÖÜäöüßπ_][A-Za-zÄÖÜäöüß_0-9]*"
    private val token = Regex("""\s*(?:(\d+(?:[.,]\d+)?)|($NAME)|(√)|([-+*/×·÷^%()−]))""")
    private val assignment = Regex("""^\s*($NAME)\s*=\s*(.+?)\s*$""")

    private sealed class Token {
        data class Num(val value: Double) : Token()
        data class Name(val name: String) : Token()
        data class Op(val op: String) : Token()
    }

    private fun tokenize(input: String): List<Token> {
        val text = input.trimEnd()
        val tokens = mutableListOf<Token>()
        var position = 0
        while (position < text.length) {
            val match = token.matchAt(text, position) ?: throw CalcError(text.substring(position))
            if (match.range.last + 1 == position) throw CalcError(text.substring(position))
            val (number, name, root, op) = match.destructured
            tokens += when {
                number.isNotEmpty() -> Token.Num(number.replace(',', '.').toDouble())
                name.isNotEmpty() -> Token.Name(name)
                root.isNotEmpty() -> Token.Name("√")
                else -> Token.Op(mapOf("×" to "*", "·" to "*", "÷" to "/", "−" to "-")[op] ?: op)
            }
            position = match.range.last + 1
        }
        return tokens
    }

    private class Parser(val tokens: List<Token>, val variables: Map<String, Double>) {
        var index = 0
        var used = false

        fun peek(): Token? = tokens.getOrNull(index)
        fun isOp(op: String) = (peek() as? Token.Op)?.op == op
        fun take(): Token = tokens.getOrNull(index++) ?: throw CalcError("unexpected end")

        fun parse(): Double {
            val value = expression()
            if (index != tokens.size) throw CalcError("trailing")
            return value
        }

        fun expression(): Double {
            var value = term()
            while (isOp("+") || isOp("-")) {
                val op = (take() as Token.Op).op
                used = true
                value = if (op == "+") value + term() else value - term()
            }
            return value
        }

        fun term(): Double {
            var value = power()
            while (isOp("*") || isOp("/")) {
                val op = (take() as Token.Op).op
                used = true
                val right = power()
                if (op == "/" && right == 0.0) throw CalcError("division by zero")
                value = if (op == "*") value * right else value / right
            }
            return value
        }

        fun power(): Double {
            val value = unary()
            if (isOp("^")) {
                take()
                used = true
                return Math.pow(value, power())
            }
            return value
        }

        fun unary(): Double {
            if (isOp("-")) { take(); return -unary() }
            if (isOp("+")) { take(); return unary() }
            var value = atom()
            if (isOp("%")) { take(); used = true; value /= 100 }
            return value
        }

        fun atom(): Double = when (val next = take()) {
            is Token.Num -> next.value
            is Token.Op -> if (next.op == "(") expression().also { if (!isOp(")")) throw CalcError("missing )"); take() } else throw CalcError(next.op)
            is Token.Name -> when {
                next.name in functions -> { used = true; functions.getValue(next.name)(atom()) }
                next.name in variables -> { used = true; variables.getValue(next.name) }
                next.name in constants -> { used = true; constants.getValue(next.name) }
                else -> throw CalcError("unknown ${next.name}")
            }
        }
    }

    /** Value and whether an operator, function or variable was used (a plain number is no calculation). */
    fun evaluate(text: String, variables: Map<String, Double> = emptyMap()): Pair<Double, Boolean> {
        val parser = Parser(tokenize(text), variables)
        val value = parser.parse()
        if (value.isNaN() || value.isInfinite()) throw CalcError("no real number")
        return value to parser.used
    }

    fun variablesOf(lines: List<String>): Map<String, Double> {
        val variables = mutableMapOf<String, Double>()
        for (line in lines) {
            val match = assignment.matchEntire(line) ?: continue
            if (match.groupValues[2].endsWith("=")) continue
            try { variables[match.groupValues[1]] = evaluate(match.groupValues[2], variables).first } catch (error: CalcError) { }
        }
        return variables
    }

    /** For a line ending in "=": the formatted result of the longest calculation before it, or null. */
    fun resultFor(line: String, earlier: List<String> = emptyList()): String? {
        val trimmed = line.trimEnd()
        if (!trimmed.endsWith("=")) return null
        val before = trimmed.dropLast(1)
        if ('=' in before || before.isBlank()) return null
        val variables = variablesOf(earlier)
        val starts = listOf(0) + before.indices.filter { before[it] == ' ' }.map { it + 1 }
        for (start in starts) {
            val candidate = before.substring(start).trim()
            if (candidate.isEmpty()) continue
            try {
                val (value, used) = evaluate(candidate, variables)
                if (used) return format(value)
            } catch (error: CalcError) {
            } catch (error: NumberFormatException) {
            }
        }
        return null
    }

    /** German style: decimal comma, at most 10 significant digits, no trailing zeros. */
    fun format(value: Double): String {
        if (abs(value) >= 1e15 || (value != 0.0 && abs(value) < 1e-9)) return "%.6g".format(java.util.Locale.ROOT, value).replace('.', ',')
        var text = java.math.BigDecimal(value).round(java.math.MathContext(10)).stripTrailingZeros().toPlainString()
        if (text == "-0") text = "0"
        return text.replace('.', ',')
    }
}
