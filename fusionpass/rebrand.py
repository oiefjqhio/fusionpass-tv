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

print('rebrand: ok,', len(changed), 'files changed')
for c in changed[:60]:
    print('  ', c)
