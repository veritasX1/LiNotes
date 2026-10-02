package io.github.veritasx1.linotes

import io.github.veritasx1.linotes.data.Model
import org.junit.Assert.assertEquals
import org.junit.Test

/** Karte a5105a40: same cases as linux/tests/test_activity.py. */
class ActivityTest {
    private fun check(old: List<String>, new: List<String>, expected: List<Int>) =
        assertEquals("$old → $new", expected, Model.changedLines(old, new))

    @Test
    fun sameLinesAsUbuntu() {
        check(listOf("a", "b", "c"), listOf("a", "b", "c"), listOf())
        check(listOf("a", "b", "c"), listOf("a", "x", "b", "c"), listOf(1))
        check(listOf("a", "b", "c"), listOf("a", "B", "c"), listOf(1))
        check(listOf("a", "b", "c"), listOf("a", "c"), listOf())
        check(listOf(), listOf("a", "b"), listOf(0, 1))
        check(listOf("a", "b"), listOf("b", "a", "neu"), listOf(1, 2))
        check(listOf("Titel", "eins", "zwei"), listOf("Titel", "eins", "zwei", "drei", "vier"), listOf(3, 4))
    }
}
