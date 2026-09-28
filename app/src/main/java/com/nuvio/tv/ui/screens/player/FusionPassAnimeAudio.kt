package com.nuvio.tv.ui.screens.player

import com.nuvio.tv.data.local.AudioLanguageOption

// Fusion Pass: the "Auto" audio default plays anime in Japanese (English subtitles follow from the
// subtitle default) and everything else in English. Written by fusionpass/rebrand.py.

internal fun PlayerRuntimeController.fpIsAnime(): Boolean {
    val id = currentVideoId.orEmpty()
    if (listOf("kitsu:", "mal:", "anilist:", "anidb:").any { id.startsWith(it) }) return true
    if (metaGenres.any { it.equals("anime", ignoreCase = true) }) return true
    val animation = metaGenres.any { it.equals("animation", ignoreCase = true) }
    return animation && (metaCountry?.contains("Japan", ignoreCase = true) == true || contentLanguage == "ja")
}

/** Re-applies the audio preference once the genres arrive, if the title turns out to be anime. */
internal fun PlayerRuntimeController.fpApplyAnimeAudio() {
    val settings = currentPlayerSettingsForReport
    if (settings.preferredAudioLanguage != AudioLanguageOption.FP_AUTO) return
    if (persistedTrackPreference?.audio != null || !fpIsAnime()) return
    val resolved = resolvePreferredAudioLanguages(
        preferredAudioLanguage = settings.preferredAudioLanguage,
        secondaryPreferredAudioLanguage = settings.secondaryPreferredAudioLanguage,
        deviceLanguages = emptyList(),
        contentOriginalLanguage = contentLanguage,
        isAnime = true
    )
    if (resolved == mpvPreferredAudioLanguages) return
    mpvPreferredAudioLanguages = resolved
    _exoPlayer?.let { player ->
        player.trackSelectionParameters = player.trackSelectionParameters
            .buildUpon()
            .setPreferredAudioLanguages(*resolved.toTypedArray())
            .build()
    }
    if (isUsingMpvEngine()) mpvView?.applyAudioLanguagePreferences(resolved)
}
