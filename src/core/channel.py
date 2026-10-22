"""Distribution channel of this build.

Two channels exist:

- ``"direct"`` — every build except the Play Store AAB: the GitHub APK,
  Windows, Linux. Kiri License premium is offered here.
- ``"play"`` — the AAB that ships through the Play Store. Premium does
  not exist on this channel: no purchase UI, no license-worker requests,
  nothing for Play policy to look at. Users get the free tier with ads.

The committed default is ``direct``. The AAB job overwrites this file
with ``CHANNEL = "play"`` before packaging.
"""

CHANNEL = "direct"
