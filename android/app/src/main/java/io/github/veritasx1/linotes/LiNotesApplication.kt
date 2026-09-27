package io.github.veritasx1.linotes

import android.app.Application
import io.github.veritasx1.linotes.data.BiometricStore
import io.github.veritasx1.linotes.data.SyncEngine
import io.github.veritasx1.linotes.ui.AppState

class LiNotesApplication : Application() {
    lateinit var state: AppState
        private set

    override fun onCreate() {
        super.onCreate()
        state = AppState(SyncEngine(this), BiometricStore(this))
    }
}
