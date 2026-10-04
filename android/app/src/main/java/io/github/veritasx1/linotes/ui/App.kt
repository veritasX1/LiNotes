package io.github.veritasx1.linotes.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.StateFlow

@Composable
fun <T> StateFlow<T>.collectAsStateCompat(): State<T> = collectAsState()

@Composable
fun LiNotesApp(state: AppState) {
    LiNotesTheme {
        val colors = palette
        val revision by state.sync.revision.collectAsState()
        val signedOut by state.sync.signedOut.collectAsState()
        LaunchedEffect(signedOut) {
            if (signedOut && state.signedIn) {
                state.sync.signOut()
                state.signedIn = false
                state.showToast("Bitte melde dich erneut an.")
            }
        }
        // Unlocked notes lock again after a few minutes without use (like Apple).
        LaunchedEffect(Unit) {
            while (true) { kotlinx.coroutines.delay(30_000); state.checkAutoLock() }
        }
        // @-mentions by others in shared notes become notifications.
        val context = androidx.compose.ui.platform.LocalContext.current
        LaunchedEffect(revision) { if (state.signedIn) Mentions.check(context, state) }
        LaunchedEffect(Unit) {
            state.sync.requests.collect { request -> if (state.incoming.none { it.optString("channel") == request.optString("channel") }) state.incoming.add(request) }
        }
        Box(Modifier.fillMaxSize().background(colors.background)) {
            if (!state.signedIn) {
                OnboardingScreen(state)
            } else {
                BackHandler(enabled = state.stack.size > 1) { state.pop() }
                val route = state.route
                val depth = state.stack.size
                val onEditor = route is Route.Editor || route is Route.ListDetail || route is Route.Board || route is Route.Settings ||
                    route is Route.People || route is Route.Verify || route is Route.Share || route is Route.Help || route is Route.Connect
                Column(Modifier.fillMaxSize()) {
                    Box(Modifier.weight(1f)) {
                        AnimatedContent(
                            targetState = Triple(state.tab, depth, route),
                            transitionSpec = {
                                if (initialState.first != targetState.first) fadeIn(tween(120)) togetherWith fadeOut(tween(120))
                                else if (targetState.second > initialState.second)
                                    slideInHorizontally(tween(260)) { it } togetherWith slideOutHorizontally(tween(260)) { -it / 3 }
                                else slideInHorizontally(tween(260)) { -it / 3 } togetherWith slideOutHorizontally(tween(260)) { it }
                            },
                            label = "navigation",
                        ) { (_, _, current) ->
                            when (current) {
                                Route.Folders -> FoldersScreen(state, revision)
                                is Route.NoteList -> NoteListScreen(state, current.key, revision)
                                is Route.Editor -> EditorScreen(state, current.noteId, revision)
                                Route.Lists -> ListsScreen(state, revision)
                                is Route.ListDetail -> ListDetailScreen(state, current.listId, revision)
                                Route.Boards -> BoardsScreen(state, revision)
                                is Route.Board -> BoardScreen(state, current.boardId, revision)
                                Route.Plans -> PlansScreen(state, revision)
                                is Route.Plan -> PlanScreen(state, current.planId, revision)
                                Route.Settings -> SettingsScreen(state, revision)
                                Route.People -> PeopleScreen(state, revision)
                                is Route.Verify -> VerifyScreen(state, current.userId)
                                is Route.Share -> ShareScreen(state, current.objectId, revision)
                                Route.Help -> HelpScreen(state)
                                Route.Connect -> OnboardingScreen(state, connecting = true)
                            }
                        }
                    }
                    if (!onEditor) {
                        // Only news from others, like a message badge – gone once the lists were looked at.
                        if (state.tab == 1) LaunchedEffect(revision) { state.sync.listsSeen = io.github.veritasx1.linotes.data.Model.now() + 1 }
                        val openItems = if (state.tab == 1) 0 else state.sync.newListItems()
                        TabBar(listOf(
                            TabItem(Glyph.Notes, "Notizen"),
                            TabItem(Glyph.Cart, "Listen", openItems),
                            TabItem(Glyph.Board, "Aufgaben"),
                            TabItem(Glyph.Table, "Pläne"),
                        ), state.tab) { state.openTab(it) }
                    }
                }
            }
            if (state.signedIn) {
                IncomingRequests(state)
                // Above the tab bar or the editor's toolbar (and the keyboard).
                UploadBanner(state, Modifier.align(Alignment.BottomCenter).imePadding().navigationBarsPadding().padding(bottom = 64.dp))
                QuickLookOverlay(state)
            }
            QrScannerOverlay(state)
            Toast(state.toast)
        }
    }
}
