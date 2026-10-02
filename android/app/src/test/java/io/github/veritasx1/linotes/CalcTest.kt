package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Calc
import org.junit.Assert.assertEquals
import org.junit.Test

/** Karte de1319cf: same cases as linux/tests/test_calc.py. */
class CalcTest {
    private fun check(line: String, earlier: List<String>, expected: String?) =
        assertEquals(line, expected, Calc.resultFor(line, earlier))

    @Test
    fun sameResultsAsUbuntu() {
        check("2+2=", listOf(), "4")
        check("12,5 * 4 =", listOf(), "50")
        check("√12 =", listOf(), "3,464101615")
        check("x*y=", listOf("x = 64", "y=2"), "128")
        check("Summe 450 + 120 =", listOf(), "570")
        check("Miete * 12 =", listOf("Miete = 450 + 120"), "6840")
        check("10 / 3 =", listOf(), "3,333333333")
        check("2^10 =", listOf(), "1024")
        check("19% * 200 =", listOf(), "38")
        check("(1+2)*3 =", listOf(), "9")
        check("2 × 3 · 4 ÷ 6 =", listOf(), "4")
        check("-5 + 2 =", listOf(), "-3")
        check("sin(0) =", listOf(), "0")
        check("π * 2 =", listOf(), "6,283185307")
        check("0,1 + 0,2 =", listOf(), "0,3")
        check("1000000 * 3 =", listOf(), "3000000")
        check("5 =", listOf(), null)
        check("x = 3 =", listOf(), null)
        check("1/0 =", listOf(), null)
        check("Hallo =", listOf(), null)
        check("Termin am 3.10. =", listOf(), null)
    }
}
