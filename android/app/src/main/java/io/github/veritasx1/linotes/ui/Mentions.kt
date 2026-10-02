package io.github.veritasx1.linotes.ui

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import io.github.veritasx1.linotes.MainActivity
import io.github.veritasx1.linotes.R
import io.github.veritasx1.linotes.data.Model

/** Someone @-mentioned me in a shared note: a system notification (once per mention),
 *  tapping it opens the note. Mirrors notify_mentions in linux/linotes/window.py. */
object Mentions {
    private const val CHANNEL = "mentions"

    fun check(context: Context, state: AppState) {
        val sync = state.sync
        val me = sync.userId
        val seen = sync.mentionsSeen
        var changed = false
        for (note in sync.all("note")) {
            if (note.share == null || note.evicted || note.data.has("enc") || note.data.has("trashed")) continue
            val count = Model.mentionsOf(Model.blocks(note), me)
            val known = seen.optInt(note.id, 0)
            if (count == known) continue
            // Without permission nothing counts as reported – it comes once notifications are allowed.
            if (count > known && note.updatedBy != 0 && note.updatedBy != me &&
                !notify(context, note.id, sync.userName(note.updatedBy), Model.title(note))) continue
            seen.put(note.id, count)
            changed = true
        }
        if (changed) sync.mentionsSeen = seen
    }

    private fun notify(context: Context, noteId: String, who: String, title: String): Boolean {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return false
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "Erwähnungen", NotificationManager.IMPORTANCE_DEFAULT))
        }
        val open = Intent(context, MainActivity::class.java).setAction(MainActivity.ACTION_OPEN_NOTE)
            .putExtra(MainActivity.EXTRA_NOTE, noteId).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pending = PendingIntent.getActivity(context, noteId.hashCode(), open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_new_note)
            .setContentTitle("$who hat dich erwähnt")
            .setContentText("in „$title“")
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(context).notify("mention-$noteId".hashCode(), notification)
        return true
    }
}
