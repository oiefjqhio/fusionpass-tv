#!/usr/bin/env python3
"""Apply the Fusion Pass branding and lock-down to a NuvioTV checkout. Idempotent: run it after
every upstream sync (git merge upstream/dev, then python3 fusionpass/rebrand.py, then commit).

GPL-3.0: this fork's source stays public; the About/licenses screen keeps a credit to Nuvio.
"""
import glob, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = f'{ROOT}/app/src/main/res'
OUT = f'{ROOT}/fusionpass/brand/out'
BACKEND = 'https://sync.fusionpass.shop'
changed = []

def edit(path, pairs, required=True):
    s = open(path, encoding='utf8').read()
    orig = s
    for a, b in pairs:
        if a in b and b in s:
            continue  # already applied; b extends a, so replacing again would repeat it
        if a not in s and b not in s and required:
            sys.exit(f'rebrand: anchor not found in {path}: {a[:80]!r} (upstream changed; update rebrand.py)')
        s = s.replace(a, b)
    if s != orig:
        open(path, 'w', encoding='utf8').write(s)
        changed.append(os.path.relpath(path, ROOT))

# 1. Images: every launcher icon, TV banner and logo variant becomes ours.
for d, name in [('mdpi', 'ic_launcher-mdpi'), ('hdpi', 'ic_launcher-hdpi'), ('xhdpi', 'ic_launcher-xhdpi'), ('xxhdpi', 'ic_launcher-xxhdpi'), ('xxxhdpi', 'ic_launcher-xxxhdpi')]:
    for f in glob.glob(f'{RES}/mipmap-{d}/ic_launcher*.png'):
        shutil.copyfile(f'{OUT}/{name}.png', f)
for f in glob.glob(f'{RES}/mipmap-xhdpi/banner*.png'):
    shutil.copyfile(f'{OUT}/banner-xhdpi.png', f)
for f in glob.glob(f'{RES}/drawable/app_logo_wordmark*.png'):
    shutil.copyfile(f'{OUT}/app_logo_wordmark.png', f)
shutil.copyfile(f'{OUT}/app_logo_mark.png', f'{RES}/drawable/app_logo_mark.png')
shutil.copyfile(f'{OUT}/brand_text.png', f'{RES}/drawable/nuvio_text.png')
shutil.copyfile(f'{OUT}/tv_banner.png', f'{RES}/drawable/tv_banner.png')

# 2. Visible text: Nuvio -> Fusion Pass in every language, except the attribution credit.
CREDIT = '<string name="licenses_attributions_nuvio_title">Based on Nuvio TV (GPL-3.0)</string>'
for path in glob.glob(f'{RES}/values*/strings.xml'):
    s = open(path, encoding='utf8').read()
    out = []
    for line in s.split('\n'):
        if 'name="licenses_attributions_nuvio_title"' in line:
            line = re.sub(r'<string name="licenses_attributions_nuvio_title">.*?</string>', CREDIT, line)
        elif '<string' in line or '<item' in line:
            # only the text between tags, never resource names
            line = re.sub(r'>([^<]*)<', lambda m: '>' + m.group(1).replace('Nuvio TV', 'Fusion Pass').replace('Nuvio', 'Fusion Pass') + '<', line)
        out.append(line)
    n = '\n'.join(out)
    if n != s:
        open(path, 'w', encoding='utf8').write(n)
        changed.append(os.path.relpath(path, ROOT))

# English overrides for text that still describes Nuvio features we removed (Trakt, plugins, web panel).
SHORT = {
    'account_sign_in_description': 'Sign in with your Fusion Pass email and password.',
    'profile_pin_overlay_forgot_hint': 'Forgot PIN? Reset it from your account.',
    'cd_nuvio_logo': 'Fusion Pass',
    'playback_player_internal_desc': 'Use the built-in player',
}
p = f'{RES}/values/strings.xml'
s = open(p, encoding='utf8').read()
n = s
for k, v in SHORT.items():
    n, c = re.subn(rf'(<string name="{k}"[^>]*>)[^<]*(</string>)', lambda m: m.group(1) + v + m.group(2), n)
    if not c:
        sys.exit(f'rebrand: string {k} not found (upstream changed; update rebrand.py)')
if n != s:
    open(p, 'w', encoding='utf8').write(n)
    changed.append(os.path.relpath(p, ROOT))

# 3. Build config: our app id, our backend defaults, our update channel, locked-down flavor.
G = f'{ROOT}/app/build.gradle.kts'
edit(G, [
    ('        applicationId = "com.nuvio.tv"\n', '        applicationId = "shop.fusionpass.tv"\n'),
    ('buildConfigField("String", "GITHUB_OWNER", "\\"NuvioMedia\\"")', 'buildConfigField("String", "GITHUB_OWNER", "\\"oiefjqhio\\"")'),
    ('buildConfigField("String", "GITHUB_REPO", "\\"NuvioTV\\"")', 'buildConfigField("String", "GITHUB_REPO", "\\"fusionpass-tv\\"")'),
    ('"https://nuvio.tv/tv-login"', f'"{BACKEND}/tv-login"'),
    ('"https://nuvio.tv/link"', f'"{BACKEND}/link"'),
    ('"https://nuvio.tv/support"', '"https://fusionpass.shop/setup"'),
])
s = open(G, encoding='utf8').read()
full = re.search(r'create\("full"\) \{.*?\n        \}', s, re.S)
if not full:
    sys.exit('rebrand: full flavor block not found')
block = full.group(0)
nb = block.replace('"FEATURE_PLUGINS_ENABLED", "true"', '"FEATURE_PLUGINS_ENABLED", "false"').replace(
    '"FEATURE_CUSTOM_SERVER_CONNECTIONS_ENABLED", "true"', '"FEATURE_CUSTOM_SERVER_CONNECTIONS_ENABLED", "false"')
if nb != block:
    open(G, 'w', encoding='utf8').write(s.replace(block, nb))
    changed.append('app/build.gradle.kts (full flavor)')

# 4. Our backend is the built-in one, with email + password sign-in on the TV.
edit(f'{ROOT}/app/src/main/java/com/nuvio/tv/data/local/ServerConfigurationStore.kt', [
    ('''        capabilities = ServerCapabilities(
            emailPasswordAuth = false,
            tvLogin = true
        ),
        isCustom = false,''', '''        capabilities = ServerCapabilities(
            emailPasswordAuth = true, // Fusion Pass: built-in backend is our self-host
            tvLogin = true
        ),
        isCustom = false,'''),
])
edit(f'{ROOT}/app/src/main/java/com/nuvio/tv/ui/screens/account/AccountViewModel.kt', [
    ('get() = serverConfiguration.isCustom && serverConfiguration.capabilities.emailPasswordAuth',
     'get() = serverConfiguration.capabilities.emailPasswordAuth // Fusion Pass'),
])

# 5. Lock-down: never play torrents (owner rule: debrid, Usenet, HTTP only), no plugins, no
#    donation screens for another project under our name, no addon/integration setup (the
#    account comes fully configured), our own legal links.
J = f'{ROOT}/app/src/main/java/com/nuvio/tv'
edit(f'{J}/data/repository/StreamRepositoryImpl.kt', [
    ("                    it.toDomain(addonName, addonLogo) \n                } ?: emptyList()",
     "                    it.toDomain(addonName, addonLogo) \n                }?.filterNot { it.isTorrent() } ?: emptyList() // Fusion Pass: no P2P"),
    ("                        ?.mapNotNull { it.toDomain(addon.displayName, addon.logo) }\n                        ?: emptyList()",
     "                        ?.mapNotNull { it.toDomain(addon.displayName, addon.logo) }\n                        ?.filterNot { it.isTorrent() } // Fusion Pass: no P2P\n                        ?: emptyList()"),
])
edit(f'{ROOT}/app/src/full/java/com/nuvio/tv/core/build/AppFeaturePolicy.kt', [
    ('val pluginsEnabled: Boolean = true', 'val pluginsEnabled: Boolean = false'),
    ('val supportNuvioEnabled: Boolean = true', 'val supportNuvioEnabled: Boolean = false'),
])
edit(f'{J}/ui/screens/settings/SettingsScreen.kt', [
    ('                SettingsCategory.CONTENT_DISCOVERY -> true\n                SettingsCategory.INTEGRATION -> true\n',
     '                SettingsCategory.CONTENT_DISCOVERY -> false // Fusion Pass: addons come with the account\n'
     '                SettingsCategory.INTEGRATION -> false // Fusion Pass: no debrid/metadata setup\n'),
])
# No tracking services (Trakt/Simkl need our own API apps; owner chose to hide them).
edit(f'{J}/ui/screens/settings/SettingsScreen.kt', [
    ('                SettingsCategory.INTEGRATION -> false // Fusion Pass: no debrid/metadata setup\n                SettingsCategory.ADVANCED',
     '                SettingsCategory.INTEGRATION -> false // Fusion Pass: no debrid/metadata setup\n'
     '                SettingsCategory.TRACKING -> false // Fusion Pass: no Trakt/Simkl\n                SettingsCategory.ADVANCED'),
])
edit(f'{J}/ui/screens/settings/AboutScreen.kt', [('"https://nuvio.tv/privacy-policy"', '"https://fusionpass.shop/privacy"')])
edit(f'{J}/ui/screens/account/AuthQrSignInScreen.kt', [('"https://nuvio.tv/terms"', '"https://fusionpass.shop/terms"')])

# 6. Names a user can see outside the string resources.
edit(f'{J}/core/auth/DeviceSessionRegistration.kt', [('CLIENT_NAME = "Nuvio TV"', 'CLIENT_NAME = "Fusion Pass TV"')])

# Audio and subtitles (owner decision 2026-09-28): by default English audio, or Japanese for anime, with English
# subtitles on. The default is a setting of its own ("Auto"), so a language the user picks still wins.
P = f'{J}/ui/screens/player'
edit(f'{J}/data/local/PlayerSettingsDataStore.kt', [
    ('    const val ORIGINAL = "original"  // Use content\'s original language (from TMDB)\n',
     '    const val ORIGINAL = "original"  // Use content\'s original language (from TMDB)\n    const val FP_AUTO = "fpauto" // Fusion Pass: English, Japanese for anime (same value in every app: settings sync)\n'),
    ('    val preferredAudioLanguage: String = AudioLanguageOption.DEVICE,', '    val preferredAudioLanguage: String = AudioLanguageOption.FP_AUTO, // Fusion Pass'),
    ('                    prefs[preferredAudioLanguageKey] ?: AudioLanguageOption.DEVICE\n', '                    prefs[preferredAudioLanguageKey] ?: AudioLanguageOption.FP_AUTO // Fusion Pass\n'),
    ('        if (preferred == null || preferred == SubtitleLanguageOption.DEVICE) {\n            return ResolvedSubtitlePreferredLanguage(resolveDeviceSubtitleLanguage(), isSystemDefault = true)',
     '        // Fusion Pass: English subtitles unless the user picks a language\n        if (preferred == null) return ResolvedSubtitlePreferredLanguage("en", isSystemDefault = false)\n        if (preferred == SubtitleLanguageOption.DEVICE) {\n            return ResolvedSubtitlePreferredLanguage(resolveDeviceSubtitleLanguage(), isSystemDefault = true)'),
])
edit(f'{P}/PlayerRuntimeControllerInitialization.kt', [
    ('    contentOriginalLanguage: String? = null\n): List<String> {', '    contentOriginalLanguage: String? = null,\n    isAnime: Boolean = false // Fusion Pass\n): List<String> {'),
    ('    return when (preferredAudioLanguage.trim().lowercase()) {\n',
     '    return when (preferredAudioLanguage.trim().lowercase()) {\n        AudioLanguageOption.FP_AUTO -> listOfNotNull(\n            "ja".takeIf { isAnime }, "en", normalize(secondaryPreferredAudioLanguage)\n        ).distinct() // Fusion Pass\n'),
    ('                contentOriginalLanguage = contentLanguage\n            )\n            mpvPreferredAudioLanguages = preferredAudioLanguages',
     '                contentOriginalLanguage = contentLanguage,\n                isAnime = fpIsAnime()\n            )\n            mpvPreferredAudioLanguages = preferredAudioLanguages'),
])
edit(f'{P}/PlayerRuntimeControllerObservers.kt', [
    ('                contentOriginalLanguage = contentLanguage\n            )\n            if (resolvedAudioLanguages != mpvPreferredAudioLanguages) {',
     '                contentOriginalLanguage = contentLanguage,\n                isAnime = fpIsAnime()\n            )\n            if (resolvedAudioLanguages != mpvPreferredAudioLanguages) {'),
])
edit(f'{P}/PlayerRuntimeControllerMetadata.kt', [
    ('        contentLanguage = meta.resolveContentLanguage()\n    }\n    val description = resolveDescription(meta)',
     '        contentLanguage = meta.resolveContentLanguage()\n    }\n    fpApplyAnimeAudio() // Fusion Pass\n    val description = resolveDescription(meta)'),
])
FP_ANIME = '''package com.nuvio.tv.ui.screens.player

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
'''
if not os.path.exists(f'{P}/FusionPassAnimeAudio.kt') or open(f'{P}/FusionPassAnimeAudio.kt', encoding='utf8').read() != FP_ANIME:
    open(f'{P}/FusionPassAnimeAudio.kt', 'w', encoding='utf8').write(FP_ANIME)
    changed.append('app/src/main/java/com/nuvio/tv/ui/screens/player/FusionPassAnimeAudio.kt')
S = f'{J}/ui/screens/settings/PlaybackAudioSettings.kt'
edit(S, [
    ('            AudioLanguageOption.DEFAULT -> stringResource(R.string.audio_lang_default)\n            AudioLanguageOption.DEVICE -> stringResource(R.string.audio_lang_device)\n            AudioLanguageOption.ORIGINAL -> stringResource(R.string.audio_lang_original)\n            else -> AVAILABLE_SUBTITLE_LANGUAGES',
     '            AudioLanguageOption.FP_AUTO -> FP_AUTO_LABEL\n            AudioLanguageOption.DEFAULT -> stringResource(R.string.audio_lang_default)\n            AudioLanguageOption.DEVICE -> stringResource(R.string.audio_lang_device)\n            AudioLanguageOption.ORIGINAL -> stringResource(R.string.audio_lang_original)\n            else -> AVAILABLE_SUBTITLE_LANGUAGES'),
    ('    val specialOptions = listOf(\n        AudioLanguageOption.DEFAULT to stringResource(R.string.audio_lang_default),',
     '    val specialOptions = listOf(\n        AudioLanguageOption.FP_AUTO to FP_AUTO_LABEL,\n        AudioLanguageOption.DEFAULT to stringResource(R.string.audio_lang_default),'),
])
s2 = open(S, encoding='utf8').read()
if 'FP_AUTO_LABEL =' not in s2:
    open(S, 'a', encoding='utf8').write('\n// Fusion Pass: the default audio setting\nprivate const val FP_AUTO_LABEL = "Auto (English, Japanese for anime)"\n')

# No debrid names anywhere (owner 2026-09-28): drop the Premiumize / TorBox credits from Licenses. Their
# settings (Connected Services) and cloud library are already unreachable (integrations hidden, no keys).
import re as _re
_L = f'{J}/ui/screens/settings/LicensesAttributionsScreen.kt'
_s = open(_L, encoding='utf8').read()
_n = _re.subn(r'    LicenseAttributionItem\(\n        title = stringResource\(R\.string\.licenses_attributions_(?:premiumize|torbox)_title\),.*?\n    \),\n', '', _s, flags=_re.S)
if _n[1]:
    open(_L, 'w', encoding='utf8').write(_n[0] + '// Fusion Pass: no debrid credits (rebrand.py)\n')
    changed.append(os.path.relpath(_L, ROOT))
elif 'Fusion Pass: no debrid credits' not in _s:
    sys.exit(f'rebrand: Premiumize/TorBox credits not found in {_L} (upstream changed; update rebrand.py)')

# In-app updates: compare the -fp<N> revision numerically (code review 2026-09-29, report 22 F2).
edit(f'{J}/updater/VersionUtils.kt', [('    private fun comparePrereleaseIdentifier(left: String, right: String): Int {\n', '    private fun comparePrereleaseIdentifier(left: String, right: String): Int {\n        // Fusion Pass: tags end in -fp<N>. Compare that revision as a number, or "fp10" sorts below\n        // "fp9" and every device stops updating at fp9 (code review 2026-09-29, report 22 F2).\n        val fpRev = Regex("^(.*?)fp(\\\\d+)$")\n        val fpLeft = fpRev.matchEntire(left)\n        val fpRight = fpRev.matchEntire(right)\n        if (fpLeft != null && fpRight != null && fpLeft.groupValues[1] == fpRight.groupValues[1]) {\n            return compareValues(fpLeft.groupValues[2].toLong(), fpRight.groupValues[2].toLong())\n        }\n')])

# Addon-install deep links do nothing: the pass manages the addons (code review 2026-09-29, report 22 F4).
edit(f'{J}/MainActivity.kt', [('                            is AppDeepLink.AddonInstall -> {\n                                navController.navigate(Screen.AddonManager.route) {\n                                    launchSingleTop = true\n                                }\n                                Toast.makeText(context, context.getString(R.string.addon_installing), Toast.LENGTH_SHORT).show()\n                                val installResult = deepLinkHandler.installAddon(deepLink.manifestUrl)\n                                if (pendingDeepLinkUrl.value == url) {\n                                    pendingDeepLinkUrl.value = null\n                                }\n                                Toast.makeText(context, installResult.message, Toast.LENGTH_LONG).show()\n                            }', '                            is AppDeepLink.AddonInstall -> {\n                                // Fusion Pass: addons are managed by the pass; a stremio:// or nuvio://<host> link\n                                // must not install one or open the hidden Addon Manager (review 22 F4).\n                                pendingDeepLinkUrl.value = null\n                            }')])
edit(f'{J}/MainActivity.kt', [('                        if (deepLink is AppDeepLink.AddonInstall && (needsEssentialAddonSetup || !layoutChosen)) {\n                            Toast.makeText(context, context.getString(R.string.addon_installing), Toast.LENGTH_SHORT).show()\n                            val installResult = deepLinkHandler.installAddon(deepLink.manifestUrl)\n                            if (pendingDeepLinkUrl.value == url) {\n                                pendingDeepLinkUrl.value = null\n                            }\n                            Toast.makeText(context, installResult.message, Toast.LENGTH_LONG).show()\n                        }', '                        if (deepLink is AppDeepLink.AddonInstall && (needsEssentialAddonSetup || !layoutChosen)) {\n                            // Fusion Pass: no addon installs from links, first-run setup included (review 22 F4).\n                            if (pendingDeepLinkUrl.value == url) {\n                                pendingDeepLinkUrl.value = null\n                            }\n                        }')])

print('rebrand: ok,', len(changed), 'files changed')
for c in changed[:60]:
    print('  ', c)
