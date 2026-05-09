---
title: 'Enlightened vTPM support for SVSM on SEV-SNP'
date: 2024-12-10
last_reply: 2025-01-23
message_count: 37
participants: ['Stefano Garzarella', 'Jason Gunthorpe', 'James Bottomley', 'Tom Lendacky', 'Jarkko Sakkinen', 'Jarkko Sakkinen', 'Dionna Amalie Glaze']
---

## [1] Stefano Garzarella — 2024-12-10

This series is based on the RFC sent by James last year [1].
In the meantime, the patches have been maintained and tested in the
Coconut Linux fork [2] along with the work to support the vTPM
emulation in Coconut SVSM.

The main changes Claudio and I made from the RFC are the following:
- Used SVSM_VTPM_QUERY to probe the TPM as Tom Lendacky suggested
- Changed references/links to TCG TPM repo since in the last year MS
  donated the reference TPM implementation to the TCG.
- Addressed Dov Murik's comments:
  https://lore.kernel.org/all/f7d0bd07-ba1b-894e-5e39-15fb1817bc8b@linux.ibm.com/
- Added a new patch with SVSM call macros for the vTPM protocol, following
  what we already have for SVSM_CORE and SVSM_ATTEST
- Rebased on v6.13-rc2

Since all sev-snp dependencies are now upstream, this series can be
applied directly to the Linus' tree.

The first patch is primarily designed to support an enlightened driver
for the AMD svsm based vTPM, but it could be used by any platform which
communicates with a TPM device.
The second and third patches, on the other hand, are specific to AMD SVSM.
They use SVSM_VTPM_QUERY call to probe for the vTPM device and
SVSM_VTPM_CMD call to execute vTPM operations as defined in the
"Secure VM Service Module for SEV-SNP Guests" [3] Publication # 58019
Revision: 1.00

These patches were tested in an AMD SEV-SNP guest running:
- a recent version of Coconut SVSM [4] containing an ephemeral vTPM
- a PoC [5] containing a stateful vTPM used for sealing/unsealing a LUKS key

Thanks,
Stefano

[1] https://lore.kernel.org/all/acb06bc7f329dfee21afa1b2ff080fe29b799021.camel@linux.ibm.com/
[2] https://github.com/coconut-svsm/linux/tree/svsm
[3] https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
[4] https://github.com/coconut-svsm/svsm/commit/6522c67e1e414f192a6f014b122ca8a1066e3bf5
[5] https://github.com/stefano-garzarella/snp-svsm-vtpm

James Bottomley (2):
  tpm: add generic platform device
  x86/sev: add a SVSM vTPM platform device

Stefano Garzarella (1):
  x86/sev: add SVSM call macros for the vTPM protocol

 arch/x86/include/asm/sev.h      |   4 +
 include/linux/tpm_platform.h    |  90 ++++++++++++++++++++
 arch/x86/coco/sev/core.c        |  64 +++++++++++++++
 drivers/char/tpm/tpm_platform.c | 141 ++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig        |   7 ++
 drivers/char/tpm/Makefile       |   1 +
 6 files changed, 307 insertions(+)
 create mode 100644 include/linux/tpm_platform.h
 create mode 100644 drivers/char/tpm/tpm_platform.c


base-commit: b8f52214c61a5b99a54168145378e91b40d10c90
prerequisite-patch-id: 95e8dd63b084c02fdfe348efa34781a0b74afb8d
prerequisite-patch-id: 562e39c3b9f951d505dbc05b37648b9bbd4386f3
prerequisite-patch-id: cc5511b814bbfe8eac62ee4461819874fe78063b
prerequisite-patch-id: 0bff1adbadf180086405120a5985a4cd67c1b7f5
prerequisite-patch-id: 1ec0a087ab0490c6e80a2f230b987a84f9eed524
prerequisite-patch-id: c22127c6217174c2164a00ec24294d6a5212f45c
prerequisite-patch-id: 43debb2c202f464334fdfe10e48b2c45b140126c
prerequisite-patch-id: c07e855fa49924cb1e027b216318f73da8d6c411
prerequisite-patch-id: a8f4c0894f898a6bc377b1c8a37754f958c84fc0
prerequisite-patch-id: a5511799158a1b1910d8afdedfb9e7edf728c0a8
prerequisite-patch-id: da66073f285179d73c5c2f08eb1eecfdd4807658
prerequisite-patch-id: 9f03269789347a15a67e15dd8c08e2607a91ddcf
prerequisite-patch-id: 7419dd222300dc3aa48d0c81f512474787f579d0
prerequisite-patch-id: 603aa385aef8e442726f3b732a3f9a0b63bfc5f7
prerequisite-patch-id: 9b15d1f577671f0e4d75d69565ea0691b38f471c
prerequisite-patch-id: fb3191af6783ede5bbcad3d868aeaf3cc90ff7ff
prerequisite-patch-id: 5fda5ee841e48b5f7ac9c1d6e4828c10455eced6
prerequisite-patch-id: e1cde7169faef9c4129f1f9ad8bccf9eaf6f211e
prerequisite-patch-id: 6f3f0bb50eb15bf615964727a6dffad68f4cead6
prerequisite-patch-id: 52fa9e1afe9914b81dda5214abc240a3248f48a1
prerequisite-patch-id: 1b728e64eb425a11f73f87d2fa1368d7d36d8657
prerequisite-patch-id: 366b0263fe31fa11db9791eee64ef97d843af80a
prerequisite-patch-id: 54104cd96f2891870a61335109dd2206d402c27f
prerequisite-patch-id: 24ee2965a654d36f03449ee3ce421b8927d043e7
prerequisite-patch-id: 037d0567ae81177ed282f3037a6bb8e833dfdf3d
prerequisite-patch-id: 9d79c95b05f4c611d8461965ca941ca960475b70
prerequisite-patch-id: e176bdfce858effcb79ff1b11e7a20a57ec4cc18
prerequisite-patch-id: 8ecd889a3ad8f5c737a69ae6e216a3e2eb3a114a
prerequisite-patch-id: a4fef48beab5d5ab1858bf40dc542bb1fbb42017
prerequisite-patch-id: 9b101918d6bdb3d8680022171f1ee25a28c3248d
prerequisite-patch-id: a512c92723cde3519e6c26c2816fbb4b708bf0b6
prerequisite-patch-id: 2dde60edf98a200d67bd8df69b46b21019be2ed2
prerequisite-patch-id: 02b11ff2886ed3b1a55661b90efbe47041c21ea1
prerequisite-patch-id: d3391b7c5a1af0ecd2bdbd051981707b3faa32f4
prerequisite-patch-id: 90813b319fb95b6c72a089d2e74da54782a24a27
prerequisite-patch-id: 518f728b831d855b5abc0a10c5985a5ee8a9c83e
prerequisite-patch-id: 07ce94fb0696a02befc5a092721303ce00873ef8
prerequisite-patch-id: 66b8f73f619cb74ddd682e32d57e7750b85febdd
prerequisite-patch-id: e70aa4172ef472645ca9960b3695e9f001a53fce
prerequisite-patch-id: c2c2c26506b2fff6c3d0d8b2b450a685ce03fb18
prerequisite-patch-id: aa16c93dadb90dc631432590983358bb75ba27aa
prerequisite-patch-id: b19cdd775175474fbf7a01140c18657db05c2407
prerequisite-patch-id: f59231fc95a6d92499fa560075f6f24e47277121
prerequisite-patch-id: 7fc55ba6258280eeb4ab42521be980428b57719d
prerequisite-patch-id: 787688510b08b12c9bd8b467a1b49e1ca0ab3f5e
prerequisite-patch-id: 6a2af85c68d66b3472a6debd2ef3191b68287e4b
prerequisite-patch-id: 9bebc718a3132f595e69e9714ae8d2023016756d
prerequisite-patch-id: db3c12a2f165e8a4724f4b0f7faab14f45528ae1
prerequisite-patch-id: 1ea04c3d13d9ca162ace68654b39186f30165947
prerequisite-patch-id: b83a79a4d039039c81a11d00c0549f6bfe56d78d
prerequisite-patch-id: 1ffc404864a007fcec9fee62e2ab1999a876382e
prerequisite-patch-id: fed3707bef1e516735946416a416ee50bbfa3d0e
prerequisite-patch-id: 626f4a7756165f2abcd88d5315d9a3348b68c361
prerequisite-patch-id: 07fcc622f2d8eb1040a8bf2a1d9b864413814925
prerequisite-patch-id: 06666eba9fe30d8adaaec27e38fa7342f68f8078
prerequisite-patch-id: e933816edb8b44c920bc512fae109543841e4a3c
prerequisite-patch-id: 16326503fba86075d6c8db4e88bff1fef260a59f
prerequisite-patch-id: bd6f14b6526ea1fb568856cb2c4a495e0de1a3b0
prerequisite-patch-id: b007f3e58a7cc9d86fb7625bc5af24320bf57d72
prerequisite-patch-id: 07ef994dacff3a872115f13308eea89ddf868860
prerequisite-patch-id: 03afd3daf1dbc523f4702db797924c7fce9b5363
prerequisite-patch-id: 3936f6ae3277276ec038a4f1ddac4efe0e68792f
prerequisite-patch-id: d89f512dc22e5ba119d7eef9dcce0029445b3553
prerequisite-patch-id: 0efd291fb6f06ba8721def39ccec3760d5a8b7b9
prerequisite-patch-id: 4324d1f2e902883a2bdcaec5bade163d51a5645e
prerequisite-patch-id: bc80a1e0bb8526e28311435ab8da4a0827aa7b85
prerequisite-patch-id: 4a619aa2c30b7cd0054eb3e6727bf321fb83d0a7
prerequisite-patch-id: f8365d4d92060912a7f10dc9bba3d92794cdc059
prerequisite-patch-id: 0251bf1dd83fd8cd13e6d32e41b6b0afeefe80f3
prerequisite-patch-id: 1def8af563a357166b3d101e280c4f158773b7c5
prerequisite-patch-id: 97ed9a2a5a07e3f55054296fc7f45699b48b53e1
prerequisite-patch-id: 7b227e22eff7112028576165ba5534de3cc3f112
prerequisite-patch-id: 767ae9a3ce4e94bff6b09c9645ac1c4ee9dfb8c4
prerequisite-patch-id: 6909d6b811bc73010b9cd651af2e9ba41865415a
prerequisite-patch-id: fed3b79d588528cd03babdcf24acf84b6f5c39e0
prerequisite-patch-id: 1358f9c39dd8bcd819b690373d121117072539ca
prerequisite-patch-id: ba6012740c1b0d3cefd6160efb973bc5f96eec35
prerequisite-patch-id: 63d1a4e72653ccce46f0eda00761d685b34226bd
prerequisite-patch-id: ebbc1aac33dbe217c8db6ccbaf04f18741e4162e
prerequisite-patch-id: 796081c09da24f9d0e76c07f08311eb81892f2fc
prerequisite-patch-id: 5d68aa911dba90fd44b5919a6c4f815b09784cba
prerequisite-patch-id: 0ace7958b54780e0da340d8b636fae8e3531328d
prerequisite-patch-id: f74d7c7e628eede4aaf6517043c6a671000b1fbf
prerequisite-patch-id: b8952585ec51ae807458c9077eb4400a25ad7b27
prerequisite-patch-id: fcc7c93f37b7722acbfb19695b3a8fb30b6e5a84
prerequisite-patch-id: 3bf566ccc9ee3bee26181ed7a9ed53b78bf8f5d1
prerequisite-patch-id: 35c7cf2a1e58e988913637639da07e11a87bc9d2
prerequisite-patch-id: e814feb8f90263b42881abfa3c9a0c8a95378ea2
prerequisite-patch-id: 55b92c661518843311f11ae401c279273dee8d75
prerequisite-patch-id: 3c11637e9bed75b01f2e4dc776c7bc6bcc999680
prerequisite-patch-id: ab2359fb36a6ece5bf847db74fc62e25305d9336
prerequisite-patch-id: fbd2586e1874389ca532c48ed652e52055f35bf4
prerequisite-patch-id: 25527bc2da2f368af37f0f3591d7ca2c0101c51d
prerequisite-patch-id: 33340f985b2775fad48b17188d63d253199e1acf
prerequisite-patch-id: b26b23b56d84661c342696bebcb4e46cebeb675a
prerequisite-patch-id: 1d5f3291b3d42b56bc8def073e24563974d5af15
prerequisite-patch-id: e60792810dff7795fd2cf4afb6b12d57139503a1
prerequisite-patch-id: 6dde39817ee40af91670c738691e2fa7c9f57139
prerequisite-patch-id: 4a3929c853e35761885311bf636217bbf14014e6
prerequisite-patch-id: 938cc488c9c45d841b6c1bd48581419001f559f2
prerequisite-patch-id: 4497a1cee56b2a42b117cbf84beab4cd33c33634
prerequisite-patch-id: c6bb659b17af9a96afdcd0e547cac98cb01f7a8f
prerequisite-patch-id: 5a3d249d134f68bdbf8c2cbf38aca3a3a9d8c56f
prerequisite-patch-id: a0cc6e292b1d7f490e1ea0b8d429c3404d9b1602
prerequisite-patch-id: 0811566ede59aaa224d36da0881eb1ea133a3a10
prerequisite-patch-id: 6e63b48bba6f9809770a3803f9384239c0ae1b76
prerequisite-patch-id: d3706dfe8a7c084b7b58f78546c604954dc8338c
prerequisite-patch-id: 4f4f0c2c0bb2ba9aae3bbb29cd65b9fd5c5aa699
prerequisite-patch-id: ff9915259f492458914d1a99f4cef0017caef306
prerequisite-patch-id: 74add493070b81d97259876ae39ab1cfb3ebb3a0
prerequisite-patch-id: f25bec82d9f1a3cc37bf63e2c3b342eb03d87d46
prerequisite-patch-id: 1d64819c65073070c01b34745cf635f9eee34a1d
prerequisite-patch-id: 9cc5f2449ba87827bbaace7107fe1bea5b159313
prerequisite-patch-id: 49f2e76cde57d8d5810c5b9d9ec0692e3655433a
prerequisite-patch-id: 75b729cdcfa6609476bedcf1c4e40bfe9f56dba5
prerequisite-patch-id: ed6b718a2f239ee3ef791ef12ce78f97ded9a291
prerequisite-patch-id: 9862b013b14d0b54ab5fee7bf4f06b8bfd0214e0
prerequisite-patch-id: 575ab5dceb5c42fa0d12fe79d50cfb9efbfbbf8b
prerequisite-patch-id: 604df1b88328faada4ee0b6b6c7563ed6dce469e
prerequisite-patch-id: 7975710aeefd128836b498f0ac4dedbe6b4068d8
prerequisite-patch-id: be0a697a84c0d9842ddee1f1e1560f1590ba915a
prerequisite-patch-id: 4e7ff453616c4168e907575998b086d38ecb407c
prerequisite-patch-id: acb038051122bc4fd2e4ab0be9450bc0c9d035a3
prerequisite-patch-id: b7bd97ddba2b4d83196a1cb7f2ab827c8c50aecb
prerequisite-patch-id: a7ec68be2db89de9a39aaff64792141c6d1529bf
prerequisite-patch-id: a11f4165f6e1445b74cf94a0125b4d2034e6290e
prerequisite-patch-id: 80eec4eec888f758003c5c3d6858fd5f0aa00727
prerequisite-patch-id: f725d08d6e95b600f2b0f9e965e70c5788f7a183
prerequisite-patch-id: 4704d9888723321256d511d3ac770e1e63e08775
prerequisite-patch-id: 1ef170065dc72a7576f95a9b45818fb5bcba6731
prerequisite-patch-id: 3dfea2a4fe6140102396f9dc4857d62d71ecbdb5
prerequisite-patch-id: d2aa746113ab7eb28ae4d596c5a72f35080bb2eb
prerequisite-patch-id: 73d2193911720abc83a6215ff554e60237bdf73f
prerequisite-patch-id: 97c1478023bb75a8e8bff20e0c15703a0195fd9d
prerequisite-patch-id: 67d1ea61a1ae24239654ad99d78601b0414c9ba1
prerequisite-patch-id: bce377617c5374ee599c1e0ae415da4902b76f3d
prerequisite-patch-id: 3c296327d4be4314a7853f6789c2e5454e4e1c14
prerequisite-patch-id: b825ac875ce36195e288ecbb0b5f5aa34aef3c5f
prerequisite-patch-id: fe5f451479f651e320c0d8d2d6a08dab5cbed948
prerequisite-patch-id: 2863bf682276e1a4590b3349242f27a6582664b6
prerequisite-patch-id: 3d62c79bd49338f16309e4f04247f4bbcfa2b6a4
prerequisite-patch-id: 30ca1ba984b9788fb1b525e0594f195d456eb00d
prerequisite-patch-id: 849083eed82ef0197a4be3ff7d75ef60ea7eda7c
prerequisite-patch-id: d88c4b834c27cec63123f322adc3b7585ae19af2
prerequisite-patch-id: c1cd04a0a220c50ac211eb521626a3ae08d06385
prerequisite-patch-id: adebf8b7f71339c1242b0071e5fc72646b497ec0
prerequisite-patch-id: 902d971b351a83a8693c87e5d931e51f3df69563
prerequisite-patch-id: c61fdd1ee7c9013140579b1eadba66b9c3618f49
prerequisite-patch-id: 6679facaf9992e375df36a4487efb1873cdcafaa
prerequisite-patch-id: ab8153866360e973d8624617f05627ef3cefd581
prerequisite-patch-id: a0fdb008db2fccc7d1b9093ab2f7d4601d9da561
prerequisite-patch-id: f35d881003fd88bbc86c76ce9d0f3d64c51495fa
prerequisite-patch-id: 6ac4400b52cbaba598c3d1f9d3b705d9ffc0662e
prerequisite-patch-id: 099943631e047356e42a83272345b764db64f079
prerequisite-patch-id: 557c46c50cf74807b4d03020eb10012c602140e6
prerequisite-patch-id: 4eb7632c1b95bef720115ccc06663d55d32f6cb7
prerequisite-patch-id: a57bb65f01478f97359a622275744dbe6947fb39
prerequisite-patch-id: 243c94721a58f28322ef00ae78135b3157f32bf8
prerequisite-patch-id: 31d75258e4a6364b2db5c331a2519c4c20d4383b
prerequisite-patch-id: c8f42d5280a92825df331d21d4da828f10f03865
prerequisite-patch-id: 716cbcceaa606b2d785d5face527c506be324047
prerequisite-patch-id: 86b83051c8ad033e1ebcf874e4a486158954f9e5
prerequisite-patch-id: cb8a8f87ae6796e88e66c6c25e88f85a139c0d43
prerequisite-patch-id: d31827f6bef0bbfdec40a63630f4c1aa6876ed34
prerequisite-patch-id: 3728677ea70297b5af4e175340f97c4238294c1c
prerequisite-patch-id: ffd916a933d55fb312ad03d3e50aff7364babe61
prerequisite-patch-id: f1dc2dd48bbaf7fb6ca93f69353180b733e0f0d5
prerequisite-patch-id: 2ddf5627a98373eaf096dbcb7759ba1b8182de5d
prerequisite-patch-id: 386cc5fd09a8a21d7e4d4499446b96de7d267c0b
prerequisite-patch-id: d119afbdf8659e7b30fefb256850b86f29ebbaee
prerequisite-patch-id: b0b9241e57cba965cf53b3aea73dd73b317d8c21
prerequisite-patch-id: 320e5aaa176fee06a08de42c76ee9d7362e13470
prerequisite-patch-id: f65814a8f6b81868f8bdb4c619741bd9ac5e900a
prerequisite-patch-id: 0b5bd4f23803ca71a3e01c57b99b1a64cb6e8ca1
prerequisite-patch-id: 13bb5b6ce2435f2f61f5532b4c93807df9d872f9
prerequisite-patch-id: f70cbdf6b574a127248ec13206e395f2ba964606
prerequisite-patch-id: 2b8208f48a83e5e3733ed1c3aaa53958b1c7de22
prerequisite-patch-id: 24f3d42a71addc4d035982fe836508a62d814b5b
prerequisite-patch-id: c8906a2a653dd3d4c34da9a8ab068591baeda197
prerequisite-patch-id: b462ddcee3dc93e308dc40a07a8fb2bd396316fe
prerequisite-patch-id: a884c0dffa1e91a3e652fbb25c45fb7c54c71fbd
prerequisite-patch-id: 871191529f426ccbcb577968f5418b43a8dbec43
prerequisite-patch-id: 6ed20db6f1bd13ac5bf8b938333417cae84fe9eb
prerequisite-patch-id: 2a1bd712eb2c8d0d489c168738088ce1ee9c6017
prerequisite-patch-id: c669eb214136b7b310bffb8355e75b35d67ed544
prerequisite-patch-id: d943a15e9ff80498367695110ca969c7c3dc1dde
prerequisite-patch-id: 22a82ca73b17f65dcb89366e79d749a708ecd8af
prerequisite-patch-id: 22b49704f98c14a8750bb257af45523e0397b8ab
prerequisite-patch-id: 0933e66f19f9799825d5223fecddd5cc58496207
prerequisite-patch-id: c4aee9495f9e91b89e3a2626e1d71c0b71de721e
prerequisite-patch-id: 3cffe3c9401acc7ba9d249d66d48ab6287bb8a8f
prerequisite-patch-id: 76b834a2b8274d3b8e712087545a69b6884cf083
prerequisite-patch-id: 317c79d67b7b1a8c314752599d7501499301b3d1
prerequisite-patch-id: d08cc0ecc791dc9ac3a07154a65c8f80f9483d34
prerequisite-patch-id: 23d1374614207c22ea72cfe3073e548165acb8e1
prerequisite-patch-id: 04ed94f8c62a7524db009938d564e5b2620fbb54
prerequisite-patch-id: 6e1b84c631d2b86514ead675d0f2bd7d8a26e09c
prerequisite-patch-id: 1b801583e4de13fc82d072371d6786abbcded031
prerequisite-patch-id: b15cfb413c6a9ba85cde93135eac4edb0121d8a5
prerequisite-patch-id: 3512538974e969c5c0b841477fc09ea4541c80d1
prerequisite-patch-id: cb3eb091ea423781ea3d77132763a57831c44dd5
prerequisite-patch-id: fcf4e8688158857c753a685fe050c1612e3d780c
prerequisite-patch-id: 0df4aac304c2909c76bb5cc4d90444fdfea0b4c8
prerequisite-patch-id: e4680a6b2e91ea77e4581e21f931f34641c502e9
prerequisite-patch-id: 5d7c0e895f765c59aff9ccff526544cab30b0b9e
prerequisite-patch-id: a5d104d14ba9a460133674971c6ef3db7dd75a56
prerequisite-patch-id: 048c6780830d7c4a7e163ecb72da94ae0316e4b5
prerequisite-patch-id: b6b9a08762c5c03a4e61afacfa741f7e429ddff1
prerequisite-patch-id: d295e56d1961147cf09bbb13b90ff1563624eaa7
prerequisite-patch-id: 02786bdbf29873049429973ae6a723662ae44d26
prerequisite-patch-id: 244b54ea6cf0dcc14923b4a62c6f8cc0067eb14b
prerequisite-patch-id: 96cde472042eae9ae97d86fca584c9a8e815eeec
prerequisite-patch-id: 9408551071c33d7cef53bd3b90e0046a5e6b0f97
prerequisite-patch-id: f59b552ac61999553987dc764d2c0c2329250e6d
prerequisite-patch-id: 2399623a1903e6dfca6966806f35206396c482d8
prerequisite-patch-id: 0cc9f7181d936daacdf021a56a53cec9b645e71e
prerequisite-patch-id: 889c36737da30c718f45da4028b72c1ab85082a2
prerequisite-patch-id: 515a939952707f2bc213bd570c13f7f291d2287e
prerequisite-patch-id: 30e597ccc6b2296c8342ed6e3260a01493959f12
prerequisite-patch-id: f85115c6506ed8ec3fe724c9814e7aea5d5e6f12
prerequisite-patch-id: e6ffcf08e2e62669d6579cf7b423014975d8d111
prerequisite-patch-id: dc151e6fb1e9a425aa4f5fcf1cc7e938fc47f0d3
prerequisite-patch-id: b6a5c08e376cc8d18994e5b3cde2d1a5ef90cea1

---

## [2] Stefano Garzarella — 2024-12-10
*Subject: [PATCH 1/3] tpm: add generic platform device*

From: James Bottomley <James.Bottomley@HansenPartnership.com>

This is primarily designed to support an enlightened driver for the
AMD svsm based vTPM, but it could be used by any platform which
communicates with a TPM device.  The platform must fill in struct
tpm_platform_ops as the platform_data and set the device name to "tpm"
to have the binding by name work correctly.  The sole sendrcv
function is designed to do a single buffer request/response conforming
to the MSSIM protocol.  For the svsm vTPM case, this protocol is
transmitted directly to the SVSM, but it could be massaged for other
function type platform interfaces.

Signed-off-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Signed-off-by: Claudio Carvalho <cclaudio@linux.ibm.com>
[SG] changed references/links to TCG TPM repo
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
 include/linux/tpm_platform.h    |  90 ++++++++++++++++++++
 drivers/char/tpm/tpm_platform.c | 141 ++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig        |   7 ++
 drivers/char/tpm/Makefile       |   1 +
 4 files changed, 239 insertions(+)
 create mode 100644 include/linux/tpm_platform.h
 create mode 100644 drivers/char/tpm/tpm_platform.c

diff --git a/include/linux/tpm_platform.h b/include/linux/tpm_platform.h
new file mode 100644
index 000000000000..95c17a75d59d
--- /dev/null
+++ b/include/linux/tpm_platform.h
@@ -0,0 +1,90 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 James.Bottomley@HansenPartnership.com
+ *
+ * Interface specification for platforms wishing to activate the
+ * platform tpm device.  The device must be a platform device created
+ * with the name "tpm" and it must populate platform_data with struct
+ * tpm_platform_ops
+ */
+
+/*
+ * The current MSSIM TPM commands we support.  The complete list is
+ * in the TcpTpmProtocol header:
+ *
+ * https://github.com/TrustedComputingGroup/TPM/blob/main/TPMCmd/Simulator/include/TpmTcpProtocol.h
+ */
+
+#define TPM_SEND_COMMAND		8
+#define TPM_SIGNAL_CANCEL_ON		9
+#define TPM_SIGNAL_CANCEL_OFF		10
+/*
+ * Any platform specific commands should be placed here and should start
+ * at 0x8000 to avoid clashes with the MSSIM protocol.  They should follow
+ * the same self describing buffer format below
+ */
+
+#define TPM_PLATFORM_MAX_BUFFER		4096 /* max req/resp buffer size */
+
+/**
+ * struct tpm_platform_ops - the share platform operations
+ *
+ * @sendrcv:	Send a TPM command using the MSSIM protocol.
+ *
+ * The MSSIM protocol is designed for a network, so the buffers are
+ * self describing.  The minimum buffer size is sizeof(u32).  Every
+ * MSSIM command defines its own transport buffer and the command is
+ * sent in the first u32 array.  The only modification we make is that
+ * the MSSIM uses network order and we use the endianness of the
+ * architecture.  The response to every command (in the same buffer)
+ * is a u32 size preceded array.  Most of the MSSIM commands simply
+ * return zero here because they have no defined response.
+ *
+ * The only command with a defined request/response size is TPM_SEND_COMMAND
+ * The definition is in the structures below
+ */
+struct tpm_platform_ops {
+	int (*sendrcv)(u8 *buffer);
+};
+
+/**
+ * struct tpm_send_cmd_req - Structure for a TPM_SEND_COMMAND
+ *
+ * @cmd:	The command (must be TPM_SEND_COMMAND)
+ * @locality:	The locality
+ * @inbuf_size:	The size of the input buffer following
+ * @inbuf:	A buffer of size inbuf_size
+ *
+ * Note that MSSIM expects @inbuf_size to be equal to the size of the
+ * specific TPM command, otherwise an TPM_RC_COMMAND_SIZE error is
+ * returned.
+ */
+struct tpm_send_cmd_req {
+	u32	cmd;
+	u8	locality;
+	u32	inbuf_size;
+	u8	inbuf[];
+} __packed;
+
+/**
+ * struct tpm_req - generic request header for single word command
+ *
+ * @cmd:	The command to send
+ */
+struct tpm_req {
+	u32	cmd;
+} __packed;
+
+/**
+ * struct tpm_resp - generic response header
+ *
+ * @size:	The response size (zero if nothing follows)
+ *
+ * Note: most MSSIM commands simply return zero here with no indication
+ * of success or failure.
+ */
+
+struct tpm_resp {
+	s32	size;
+} __packed;
+
diff --git a/drivers/char/tpm/tpm_platform.c b/drivers/char/tpm/tpm_platform.c
new file mode 100644
index 000000000000..b53d74344d61
--- /dev/null
+++ b/drivers/char/tpm/tpm_platform.c
@@ -0,0 +1,141 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Platform based TPM emulator
+ *
+ * Copyright (C) 2023 James.Bottomley@HansenPartnership.com
+ *
+ * Designed to handle a simple function request/response single buffer
+ * TPM or vTPM rooted in the platform.  This device driver uses the
+ * MSSIM protocol from the official TCG reference implementation
+ *
+ * https://github.com/TrustedComputingGroup/TPM
+ *
+ * to communicate between the driver and the platform.  This is rich
+ * enough to allow platform operations like cancellation The platform
+ * should not act on platform commands like power on/off and reset
+ * which can disrupt the TPM guarantees.
+ *
+ * This driver is designed to be single threaded (one call in to the
+ * platform TPM at any one time).  The threading guarantees are
+ * provided by the chip mutex.
+ */
+
+#include <linux/module.h>
+#include <linux/kernel.h>
+#include <linux/platform_device.h>
+#include <linux/tpm_platform.h>
+
+#include "tpm.h"
+
+static struct tpm_platform_ops *pops;
+
+static u8 *buffer;
+/*
+ * FIXME: before implementing locality we need to agree what it means
+ * to the platform
+ */
+static u8 locality;
+
+static int tpm_platform_send(struct tpm_chip *chip, u8 *buf, size_t len)
+{
+	int ret;
+	struct tpm_send_cmd_req *req = (struct tpm_send_cmd_req *)buffer;
+
+	if (len > TPM_PLATFORM_MAX_BUFFER - sizeof(*req))
+		return -EINVAL;
+	req->cmd = TPM_SEND_COMMAND;
+	req->locality = locality;
+	req->inbuf_size = len;
+	memcpy(req->inbuf, buf, len);
+
+	ret = pops->sendrcv(buffer);
+	if (ret)
+		return ret;
+
+	return 0;
+}
+
+static int tpm_platform_recv(struct tpm_chip *chip, u8 *buf, size_t len)
+{
+	struct tpm_resp *resp = (struct tpm_resp *)buffer;
+
+	if (resp->size < 0)
+		return resp->size;
+
+	if (len < resp->size)
+		return -E2BIG;
+
+	if (resp->size > TPM_PLATFORM_MAX_BUFFER - sizeof(*resp))
+		return -EINVAL;  // Invalid response from the platform TPM
+
+	memcpy(buf, buffer + sizeof(*resp), resp->size);
+
+	return resp->size;
+}
+
+static struct tpm_class_ops tpm_chip_ops = {
+	.flags = TPM_OPS_AUTO_STARTUP,
+	.send = tpm_platform_send,
+	.recv = tpm_platform_recv,
+};
+
+static struct platform_driver tpm_platform_driver = {
+	.driver = {
+		.name = "tpm",
+	},
+};
+
+static int __init tpm_platform_probe(struct platform_device *pdev)
+{
+	struct device *dev = &pdev->dev;
+	struct tpm_chip *chip;
+	int err;
+
+	if (!dev->platform_data)
+		return -ENODEV;
+
+	/*
+	 * in theory platform matching should mean this is always
+	 * true, but just in case anyone tries force binding
+	 */
+	if (strcmp(pdev->name, tpm_platform_driver.driver.name) != 0)
+		return -ENODEV;
+
+	if (!buffer)
+		buffer = kmalloc(TPM_PLATFORM_MAX_BUFFER, GFP_KERNEL);
+
+	if (!buffer)
+		return -ENOMEM;
+
+	pops = dev->platform_data;
+
+	chip = tpmm_chip_alloc(dev, &tpm_chip_ops);
+	if (IS_ERR(chip))
+		return PTR_ERR(chip);
+
+	/*
+	 * Setting TPM_CHIP_FLAG_IRQ guarantees that ->recv will be
+	 * called straight after ->send and means we don't need to
+	 * implement any other chip ops.
+	 */
+	chip->flags |= TPM_CHIP_FLAG_IRQ;
+	err = tpm2_probe(chip);
+	if (err)
+		return err;
+
+	err = tpm_chip_register(chip);
+	if (err)
+		return err;
+
+	dev_info(dev, "TPM %s platform device\n",
+		 (chip->flags & TPM_CHIP_FLAG_TPM2) ? "2.0" : "1.2");
+
+	return 0;
+}
+
+module_platform_driver_probe(tpm_platform_driver, tpm_platform_probe);
+
+MODULE_AUTHOR("James Bottomley <James.Bottomley@HansenPartnership.com>");
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Platform TPM Driver");
+MODULE_ALIAS("platform:tpm");
diff --git a/drivers/char/tpm/Kconfig b/drivers/char/tpm/Kconfig
index 0fc9a510e059..b162f59305ef 100644
--- a/drivers/char/tpm/Kconfig
+++ b/drivers/char/tpm/Kconfig
@@ -225,5 +225,12 @@ config TCG_FTPM_TEE
 	help
 	  This driver proxies for firmware TPM running in TEE.
 
+config TCG_PLATFORM
+	tristate "Platform TPM Device"
+	help
+	  This driver requires a platform implementation to provide the
+	  TPM function.  It will not bind if the implementation is not
+	  present.
+
 source "drivers/char/tpm/st33zp24/Kconfig"
 endif # TCG_TPM
diff --git a/drivers/char/tpm/Makefile b/drivers/char/tpm/Makefile
index 9bb142c75243..4b2c04e23bd3 100644
--- a/drivers/char/tpm/Makefile
+++ b/drivers/char/tpm/Makefile
@@ -44,3 +44,4 @@ obj-$(CONFIG_TCG_XEN) += xen-tpmfront.o
 obj-$(CONFIG_TCG_CRB) += tpm_crb.o
 obj-$(CONFIG_TCG_VTPM_PROXY) += tpm_vtpm_proxy.o
 obj-$(CONFIG_TCG_FTPM_TEE) += tpm_ftpm_tee.o
+obj-$(CONFIG_TCG_PLATFORM) += tpm_platform.o

---

## [3] Stefano Garzarella — 2024-12-10
*Subject: [PATCH 2/3] x86/sev: add SVSM call macros for the vTPM protocol*

Add macros for SVSM_VTPM_QUERY and SVSM_VTPM_CMD calls as defined
in the "Secure VM Service Module for SEV-SNP Guests"
Publication # 58019 Revision: 1.00

Link: https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
 arch/x86/include/asm/sev.h | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 91f08af31078..97dcc8d938a6 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -365,6 +365,10 @@ struct svsm_call {
 #define SVSM_ATTEST_SERVICES		0
 #define SVSM_ATTEST_SINGLE_SERVICE	1
 
+#define SVSM_VTPM_CALL(x)		((2ULL << 32) | (x))
+#define SVSM_VTPM_QUERY			0
+#define SVSM_VTPM_CMD			1
+
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 
 extern u8 snp_vmpl;

---

## [4] Stefano Garzarella — 2024-12-10
*Subject: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

From: James Bottomley <James.Bottomley@HansenPartnership.com>

If the SNP boot has a SVSM, probe for the vTPM device by sending a
SVSM_VTPM_QUERY call (function 8). The SVSM will return a bitmap with
the TPM_SEND_COMMAND bit set only if the vTPM is present and it is able
to handle TPM commands at runtime.

If a vTPM is found, register a platform device as "platform:tpm" so it
can be attached to the tpm_platform.c driver.

Signed-off-by: James Bottomley <James.Bottomley@HansenPartnership.com>
[CC] Used SVSM_VTPM_QUERY to probe the TPM
Signed-off-by: Claudio Carvalho <cclaudio@linux.ibm.com>
[SG] Code adjusted with some changes introduced in 6.11
[SG] Used macro for SVSM_VTPM_CALL
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
 arch/x86/coco/sev/core.c | 64 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 64 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index c5b0148b8c0a..ec0153fddc9e 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -21,6 +21,7 @@
 #include <linux/cpumask.h>
 #include <linux/efi.h>
 #include <linux/platform_device.h>
+#include <linux/tpm_platform.h>
 #include <linux/io.h>
 #include <linux/psp-sev.h>
 #include <linux/dmi.h>
@@ -2578,6 +2579,51 @@ static struct platform_device sev_guest_device = {
 	.id		= -1,
 };
 
+static struct platform_device tpm_device = {
+	.name		= "tpm",
+	.id		= -1,
+};
+
+static int snp_issue_svsm_vtpm_send_command(u8 *buffer)
+{
+	struct svsm_call call = {};
+
+	call.caa = svsm_get_caa();
+	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_CMD);
+	call.rcx = __pa(buffer);
+
+	return svsm_perform_call_protocol(&call);
+}
+
+static bool is_svsm_vtpm_send_command_supported(void)
+{
+	struct svsm_call call = {};
+	u64 send_cmd_mask = 0;
+	u64 platform_cmds;
+	u64 features;
+	int ret;
+
+	call.caa = svsm_get_caa();
+	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_QUERY);
+
+	ret = svsm_perform_call_protocol(&call);
+
+	if (ret != SVSM_SUCCESS)
+		return false;
+
+	features = call.rdx_out;
+	platform_cmds = call.rcx_out;
+
+	/* No feature supported, it must be zero */
+	if (features)
+		return false;
+
+	/* TPM_SEND_COMMAND - platform command 8 */
+	send_cmd_mask = 1 << 8;
+
+	return (platform_cmds & send_cmd_mask) == send_cmd_mask;
+}
+
 static int __init snp_init_platform_device(void)
 {
 	struct sev_guest_platform_data data;
@@ -2593,6 +2639,24 @@ static int __init snp_init_platform_device(void)
 		return -ENODEV;
 
 	pr_info("SNP guest platform device initialized.\n");
+
+	/*
+	 * The VTPM device is available only if we have a SVSM and
+	 * its VTPM supports the TPM_SEND_COMMAND platform command
+	 */
+	if (IS_ENABLED(CONFIG_TCG_PLATFORM) && snp_vmpl &&
+	    is_svsm_vtpm_send_command_supported()) {
+		struct tpm_platform_ops pops = {
+			.sendrcv = snp_issue_svsm_vtpm_send_command,
+		};
+
+		if (platform_device_add_data(&tpm_device, &pops, sizeof(pops)))
+			return -ENODEV;
+		if (platform_device_register(&tpm_device))
+			return -ENODEV;
+		pr_info("SNP SVSM VTPM platform device initialized\n");
+	}
+
 	return 0;
 }
 device_initcall(snp_init_platform_device);

---

## [5] Jason Gunthorpe — 2024-12-10
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Dec 10, 2024 at 03:34:23PM +0100, Stefano Garzarella wrote:

> +		if (platform_device_add_data(&tpm_device, &pops, sizeof(pops)))
> +			return -ENODEV;

This seems like an old fashioned way to instantiate a device. Why do
this? Just put the TPM driver here and forget about pops? Simple tpm
drivers are not very complex.

Jason

---

## [6] James Bottomley — 2024-12-10
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, 2024-12-10 at 10:40 -0400, Jason Gunthorpe wrote:
> On Tue, Dec 10, 2024 at 03:34:23PM +0100, Stefano Garzarella wrote:
> 

This driver may be for the AMD SEV SVSM vTPM module, but there are
other platforms where there's an internal vTPM which might be contacted
via a platform specific enlightenment (Intel SNP and Microsoft
OpenHCL).  This separation of the platform device from the contact
mechanism is designed to eliminate the duplication of having a platform
device within each implementation and to make any bugs in the mssim
protocol centrally fixable (every vTPM currently speaks this).

Regards,

James

---

## [7] Jason Gunthorpe — 2024-12-10
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Dec 10, 2024 at 09:55:41AM -0500, James Bottomley wrote:
> On Tue, 2024-12-10 at 10:40 -0400, Jason Gunthorpe wrote:
> > On Tue, Dec 10, 2024 at 03:34:23PM +0100, Stefano Garzarella wrote:

Sure, that's what TPM drivers are for, give those platforms TPM drivers
too.

Why put a mini driver hidden under an already mini driver?

> This separation of the platform device from the contact
> mechanism is designed to eliminate the duplication of having a platform

That makes sense, but that isn't really what I see in this series?

Patch one just has tpm_class_ops send() invoke pops sendrcv() after
re-arranging the arguments?

It looks to me like there would be mert in adding a new op to
tpm_class_ops for the send/recv type operating mode and have the core
code manage the buffer singleton (is a global static even *correct*??)

After that, there is no meaningful shared code here, and maybe the
TPM_CHIP_FLAG_IRQ hack can be avoided too.

Simply call tpm_chip_alloc/register from the sev code directly and
provide an op that does the send/recv. Let the tpm core code deal with
everything else. It is much cleaner than platform devices and driver
data..

Jason

---

## [8] Stefano Garzarella — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Dec 10, 2024 at 4:04 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Tue, Dec 10, 2024 at 09:55:41AM -0500, James Bottomley wrote:

IIUC you are proposing the following steps:
- extend tpm_class_ops to add a new send_recv() op and use it in
tpm_try_transmit()
- call the code in tpm_platform_probe() directly in sev

This would remove the intermediate driver, but at this point is it
worth keeping tpm_platform_send() and tpm_platform_recv() in a header
or module, since these are not related to sev, but to MSSIM?

As James mentioned, other platforms may want to reuse it.

Thanks,
Stefano

>
> Simply call tpm_chip_alloc/register from the sev code directly and

---

## [9] Jason Gunthorpe — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, Dec 11, 2024 at 09:19:04AM +0100, Stefano Garzarella wrote:

> > After that, there is no meaningful shared code here, and maybe the
> > TPM_CHIP_FLAG_IRQ hack can be avoided too.

Yes, that seems to be the majority of your shared code.

> - call the code in tpm_platform_probe() directly in sev

Yes

> This would remove the intermediate driver, but at this point is it
> worth keeping tpm_platform_send() and tpm_platform_recv() in a header

Reuse *what* exactly? These are 10 both line funtions that just call
another function pointer. Where exactly is this common MSSIM stuff?

Stated another way, by adding send_Recv() op to tpm_class_ops you have
already allowed reuse of all the code in tpm_platform_send/recv().

Jason

---

## [10] Stefano Garzarella — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, Dec 11, 2024 at 4:00 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Wed, Dec 11, 2024 at 09:19:04AM +0100, Stefano Garzarella wrote:

Thanks for confirming!

>
> > This would remove the intermediate driver, but at this point is it

Except for the call to pops->sendrcv(buffer) the rest depends on how
the TCG TPM reference implementation [1] expects the request/response
to be formatted (we refer to this protocol with MSSIM).

This format doesn't depend on sev, and as James said, OpenHCL for
example will have to use the same format (e.g. buffer defined by
struct tpm_send_cmd_req, filled with TPM_SEND_COMMAND, etc.), so
basically rewrite a similar function, because it also emulates the
vTPM using the TCG TPM reference implementation.

Now, I understand it's only 10 lines of code, but that code is
strictly TCG TPM dependent, so it might make sense to avoid having to
rewrite it for every implementation where the device is emulated by
TCG TPM.

>
> Stated another way, by adding send_Recv() op to tpm_class_ops you have

Partially, I mean the buffer format will always be the same for all
platforms (e.g. sev, OpenHCL, etc.), but how we read/write will be
different.
That is why I was saying to create a header with helpers that create
the request/parse the response as TCG TPM expects.

Thanks,
Stefano

[1] https://github.com/TrustedComputingGroup/TPM

---

## [11] Jason Gunthorpe — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, Dec 11, 2024 at 04:38:29PM +0100, Stefano Garzarella wrote:

> Except for the call to pops->sendrcv(buffer) the rest depends on how
> the TCG TPM reference implementation [1] expects the request/response

Make a small inline helper to do the reformatting? Much better than a
layered driver.

> That is why I was saying to create a header with helpers that create
> the request/parse the response as TCG TPM expects.

Yes helpers sound better

Jason

---

## [12] Tom Lendacky — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On 12/10/24 08:34, Stefano Garzarella wrote:
> From: James Bottomley <James.Bottomley@HansenPartnership.com>
> 

I think this check should be removed. The SVSM currently returns all
zeroes for the features to allow for future support. If a new feature is
added in the future, this then allows a driver that supports that
feature to operate with a version of an SVSM that doesn't have that
feature implemented. It also allows a version of the driver that doesn't
know about that feature to work with an SVSM that has that feature.

A feature added to the vTPM shouldn't alter the behavior of something
that isn't using or understands that feature.

> +
> +	/* TPM_SEND_COMMAND - platform command 8 */

s/VTPM/vTPM/g

Thanks,
Tom

> +	 */
> +	if (IS_ENABLED(CONFIG_TCG_PLATFORM) && snp_vmpl &&

---

## [13] Stefano Garzarella — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, Dec 11, 2024 at 4:54 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Wed, Dec 11, 2024 at 04:38:29PM +0100, Stefano Garzarella wrote:

Ack, I'll do in v2 (together with send_recv op) if there are no
objections or other ideas.

Thanks,
Stefano

---

## [14] Stefano Garzarella — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, Dec 11, 2024 at 5:31 PM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 12/10/24 08:34, Stefano Garzarella wrote:

I couldn't find much in the specification, but is a feature considered
additive only?

Let me explain, since there's no negotiation, the driver can't disable
features, so if these are just additive, it's perfectly fine to remove
this check, but if these can change the behavior of the device, then
it's risky.

I'll give an example, let's say a future version of TCG TPM changes
the format of requests for whatever reason, I guess in that case we
could use a feature to tell the driver to use the new format. What
happens if the driver is old and doesn't support it?

Maybe in this case we can define a new supported command, so if we are
sure that the features are just additive, we can remove this check.

>
> A feature added to the vTPM shouldn't alter the behavior of something

Okay, so this confirms that features are only additive.
BTW it wasn't perfectly clear from the specification, so if it can be
added it would be better IMHO.

>
> > +

I'll fix it!

Thanks for the review,
Stefano

---

## [15] James Bottomley — 2024-12-11
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, 2024-12-11 at 10:30 -0600, Tom Lendacky wrote:
> On 12/10/24 08:34, Stefano Garzarella wrote:
[...]
> > +static bool is_svsm_vtpm_send_command_supported(void)
> > +{

I actually don't think this matters, because I can't see any reason to
use the SVSM features flag for the vTPM.  The reason is that the TPM
itself contains a versioned feature mechanism that external programs
already use, so there's no real need to duplicate it.

That said, I'm happy with either keeping or removing this.

Regards,

James

---

## [16] Stefano Garzarella — 2024-12-12
*Subject: Re: [PATCH 1/3] tpm: add generic platform device*

On Tue, Dec 10, 2024 at 03:34:21PM +0100, Stefano Garzarella wrote:
>From: James Bottomley <James.Bottomley@HansenPartnership.com>
>

While reviewing Oliver's work for the driver in edk2[1], I noticed that
there wasn't this check and asked to add it, but talking to him and
looking in the code/spec, we realized that it's strange that
tpm_resp.size field is signed.

 From SVSM spec it looks like it can't be negative:

     Table 17: TPM_SEND_COMMAND Response Structure

     Byte     Size        Meaning
     Offset   (Bytes)
     0x000    4           Response size (in bytes)
     0x004    Variable    Variable Response

And also Coconut SVSM remap it to the `responseSize` of the TCG TPM
implementation which is unsigned:

     LIB_EXPORT void _plat__RunCommand(
         uint32_t        requestSize,   // IN: command buffer size
         unsigned char*  request,       // IN: command buffer
         uint32_t*       responseSize,  // IN/OUT: response buffer size
         unsigned char** response       // IN/OUT: response buffer
     )

@James, @Claudio, @Tom, should we use u32 for tpm_resp.size?

Thanks,
Stefano

[1] https://github.com/tianocore/edk2/pull/6527#discussion_r1880204144

>+
>+	if (len < resp->size)

---

## [17] James Bottomley — 2024-12-12
*Subject: Re: [PATCH 1/3] tpm: add generic platform device*

On Thu, 2024-12-12 at 10:51 +0100, Stefano Garzarella wrote:
> On Tue, Dec 10, 2024 at 03:34:21PM +0100, Stefano Garzarella wrote:
[...]
> > +static int tpm_platform_recv(struct tpm_chip *chip, u8 *buf,
> > size_t len)

The original idea was to allow the protocol to return an error (like
out of memory or something) before the command ever got to the TPM
rather than having to wrap it up in a TPM error.  However, that's done
in the actual return from the SVSM call, which the sendrecv routine
checks, so I agree this can be removed and a u32 done for the length. 
Dov did recommend we should check the returned length against the
maximum allowable:

https://lore.kernel.org/linux-coco/f7d0bd07-ba1b-894e-5e39-15fb1817bc8b@linux.ibm.com/

Regards,

James

---

## [18] Stefano Garzarella — 2024-12-12
*Subject: Re: [PATCH 1/3] tpm: add generic platform device*

On Thu, Dec 12, 2024 at 09:35:46AM -0500, James Bottomley wrote:
>On Thu, 2024-12-12 at 10:51 +0100, Stefano Garzarella wrote:
>> On Tue, Dec 10, 2024 at 03:34:21PM +0100, Stefano Garzarella wrote:

Thanks for the details!
I'll fix it in v2 and put a comment also in the edk2 PR.

>Dov did recommend we should check the returned length against the
>maximum allowable:

I added in this version the check he suggested:

	if (resp->size > TPM_PLATFORM_MAX_BUFFER - sizeof(*resp))
		return -EINVAL;  // Invalid response from the platform TPM

Were you referring to that?

Thanks,
Stefano

---

## [19] James Bottomley — 2024-12-12
*Subject: Re: [PATCH 1/3] tpm: add generic platform device*

On Thu, 2024-12-12 at 16:30 +0100, Stefano Garzarella wrote:
> On Thu, Dec 12, 2024 at 09:35:46AM -0500, James Bottomley wrote:
> > On Thu, 2024-12-12 at 10:51 +0100, Stefano Garzarella wrote:

Yes, the theory being that we're required to provide a buffer of this
length for the response, but if someone can inject a bogus response
they could induce us to copy beyond the end of the buffer we provided.

Regards,

James

---

## [20] Stefano Garzarella — 2024-12-12
*Subject: Re: [PATCH 1/3] tpm: add generic platform device*

On Thu, Dec 12, 2024 at 10:41:40AM -0500, James Bottomley wrote:
>On Thu, 2024-12-12 at 16:30 +0100, Stefano Garzarella wrote:
>> On Thu, Dec 12, 2024 at 09:35:46AM -0500, James Bottomley wrote:

I see, but we alread check that `len < resp->size` in
tpm_platform_recv(), so on second glance, for the current
implementation, maybe it's a duplicate check.

This because in tpm_platform_send() we return an error if `len >
TPM_PLATFORM_MAX_BUFFER - sizeof(*req)` and here, in
tpm_platform_recv(), we already return an error if `len < resp->size`.

IIUC buf/len are the same for send() and recv(), so the `resp->size >
TPM_PLATFORM_MAX_BUFFER - sizeof(*resp)` case would already be covered,
right?

Anyway this code will change a bit in v2 if we implement the send_recv() 
op for tpm_class_ops, so I'll be sure to take care of this case.

Thanks,
Stefano

---

## [21] Stefano Garzarella — 2024-12-13
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, Dec 11, 2024 at 12:02:49PM -0500, James Bottomley wrote:
>On Wed, 2024-12-11 at 10:30 -0600, Tom Lendacky wrote:
>> On 12/10/24 08:34, Stefano Garzarella wrote:

If we remove the check, should we print some warning if `feature` is not 
0 or just ignore it?

Thanks,
Stefano

---

## [22] Stefano Garzarella — 2024-12-19
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed, 11 Dec 2024 at 16:00, Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Wed, Dec 11, 2024 at 09:19:04AM +0100, Stefano Garzarella wrote:

I tried this, it's not bad, but I have a problem that I'm not sure how 
to solve. Basically, the functions used in tpm_platform_probe() (e.g. 
tpmm_chip_alloc, tpm2_probe, tpm_chip_register) are all defined in 
drivers/char/tpm/tpm.h
And in fact all users are in drivers/char/tpm.

So to use them directly in sev, we would have to move these definitions 
into include/linux/tpm.h or some other file in inlcude/. Is this 
acceptable for TPM maintainers?

Otherwise we need an intermediate module in drivers/char/tpm. Here we 
have 2 options:
1. continue as James did by creating a platform_device.
2. or we could avoid this by just exposing a registration API invoked by 
sev to specify the send_recv() callback to use. I mean something like 
renaming tpm_platform_probe() in tpm_platform_register(), and call it in 
snp_init_platform_device().

WDYT?

Thanks,
Stefano

---

## [23] Jarkko Sakkinen — 2024-12-19
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Thu Dec 19, 2024 at 5:35 PM EET, Stefano Garzarella wrote:
> So to use them directly in sev, we would have to move these definitions 
> into include/linux/tpm.h or some other file in inlcude/. Is this 

There's only me.

I don't know.

What you want to put to include/linux/tpm.h anyway? I have not followed
this discussion.

BR, Jarkko

---

## [24] Stefano Garzarella — 2024-12-19
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Thu, Dec 19, 2024 at 05:40:58PM +0200, Jarkko Sakkinen wrote:
>On Thu Dec 19, 2024 at 5:35 PM EET, Stefano Garzarella wrote:
>> So to use them directly in sev, we would have to move these definitions

At least tpmm_chip_alloc(), tpm2_probe(), and tpm_chip_register()

>I have not followed this discussion.

Let me try to summarize what we are doing: We are writing a small TPM
driver to support AMD SEV-SNP SVSM. Basically SVSM defines some sort of
hypercalls, which the guest OS can call to talk to the emulated vTPM.

In the current version of this series, based on James' RFC, we have an
intermediate module (tpm_platform) and then another small driver
(platform_device) in arch/x86/coco/sev/core.c that registers the
callback to use.

To avoid the intermediate driver (Jason correct me if I misunderstood),
we want to register the `tpm_chip` with its `tpm_class_ops` directly in
arch/x86/coco/sev/core.c where it's easy to use "SVSM calls" (i.e.
svsm_perform_call_protocol()).

And here I have this problem, so I was proposing to expose these APIs.
BTW, we do have an alternative though that I proposed in the previous 
email that might avoid this.

Thanks,
Stefano

---

## [25] Stefano Garzarella — 2025-01-14
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

Hi Jarkko,

On Thu, 19 Dec 2024 at 17:07, Stefano Garzarella <sgarzare@redhat.com> wrote:
>
> On Thu, Dec 19, 2024 at 05:40:58PM +0200, Jarkko Sakkinen wrote:

Any thought on this?

Thanks,
Stefano

---

## [26] Jason Gunthorpe — 2025-01-14
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Jan 14, 2025 at 11:42:34AM +0100, Stefano Garzarella wrote:
> Hi Jarkko,
> 

The intention was that tpm drivers would be under drivers/char/tpm/

Do you really need to put your tpm driver in arch code? Historically
drivers in arch code have not worked out so well.

Meaning that you'd export some of your arch stuff for the tpm driver
to live in its natural home

Jason

---

## [27] Stefano Garzarella — 2025-01-14
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Jan 14, 2025 at 09:07:20AM -0400, Jason Gunthorpe wrote:
>On Tue, Jan 14, 2025 at 11:42:34AM +0100, Stefano Garzarella wrote:
>> Hi Jarkko,

I think I misinterpreted your answer here: https://lore.kernel.org/linux-coco/20241211150048.GJ1888283@ziepe.ca/ when I asked about calling "the code in
tpm_platform_probe() directly in sev".

I totally agree that it's not a good idea, which is why I had proposed
this: https://lore.kernel.org/linux-coco/CAGxU2F7QjQTnXsqYeKc0q03SQCoW+BHbej9Q2Z8gxbgu-3O2fA@mail.gmail.com/

   Otherwise we need an intermediate module in drivers/char/tpm. Here we
   have 2 options:
   1. continue as James did by creating a platform_device.
   2. or we could avoid this by just exposing a registration API invoked by
   sev to specify the send_recv() callback to use. I mean something like
   renaming tpm_platform_probe() in tpm_platform_register(), and call it in
   snp_init_platform_device().

I'm thinking of sending an RFC implementing 2 so we can discuss there,
it should be a good compromise between your suggestions and James'
version.

>
>Meaning that you'd export some of your arch stuff for the tpm driver

@Tom do you think we can eventually expose sev API like
svsm_perform_call_protocol(), svsm_get_caa(), etc.?

Maybe option 2 that I proposed could avoid this and have sev register a
simple callback so that we avoid exposing these internal APIs.

Thanks,
Stefano

---

## [28] Jason Gunthorpe — 2025-01-14
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Jan 14, 2025 at 05:51:33PM +0100, Stefano Garzarella wrote:
>   Otherwise we need an intermediate module in drivers/char/tpm. Here we
>   have 2 options:

You should not layer things on top of things. If you have a clearly
defined driver write it in the natural logical way and export the
symbols you need.

Either export TPM stuff to arch code, or export arch code to
TPM. Don't make crazy boutique shims to avoid simple exports.

> > Meaning that you'd export some of your arch stuff for the tpm driver
> > to live in its natural home

We have lots of ways to make restricted exports now, you can use them
and export those symbols. There shouldn't be resistance to this.

Jason

---

## [29] Jarkko Sakkinen — 2025-01-15
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue Jan 14, 2025 at 12:42 PM EET, Stefano Garzarella wrote:
> Hi Jarkko,
>

A redundant super low-quality TPM stack driver implemtation to support
only single vendor's vTPM with speculative generalization.

It's a formula for destruction really.

I don't know if I event want to comment on this. Figure out a better
solution I guess that works together sound with existing stack.

If that helps we could make the main TPM driver only Y/N (instead of
tristate).

>
> Thanks,

[1] "could be used by any platform which communicates with a TPM device."

BR, Jarkko

---

## [30] Jarkko Sakkinen — 2025-01-15
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed Jan 15, 2025 at 12:46 AM EET, Jarkko Sakkinen wrote:
> On Tue Jan 14, 2025 at 12:42 PM EET, Stefano Garzarella wrote:
> > Hi Jarkko,

Also e.g. James' hmac encryption: not a single bug fixed by the author,
which does further reduce my ability to have any possible trust on this.

I do care quality over features, sorry.

BR, Jarkko

---

## [31] Jarkko Sakkinen — 2025-01-15
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed Jan 15, 2025 at 12:48 AM EET, Jarkko Sakkinen wrote:
> On Wed Jan 15, 2025 at 12:46 AM EET, Jarkko Sakkinen wrote:
> > On Tue Jan 14, 2025 at 12:42 PM EET, Stefano Garzarella wrote:

One more rant.

It's engineering problem to find **a fit** for the existing art. For
You can set the constraint here as "no two TPM stacks".

I know also almost nothing about SVSM. E.g. I don't understand why a
vTPM cannot be seen as fTPM by the guest, and why this needs user
space exported device (please do not answer here, do a better job
instead).

Even if I wanted to say how this should be changed, I could not
because it too far away to make any possible sense to begin with.
And I don't want to take the risk of those words being used as an
argument later on, when I don't even know what I'm looking.

BR, Jarkko

---

## [32] Dionna Amalie Glaze — 2025-01-22
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Tue, Jan 14, 2025 at 3:12 PM Jarkko Sakkinen <jarkko@kernel.org> wrote:
>
> On Wed Jan 15, 2025 at 12:48 AM EET, Jarkko Sakkinen wrote:

I can appreciate this viewpoint. It even surfaced Microsoft's fTPM
paper to me, which solves some interesting problems we need to solve
in SVSM too. So thanks for that.

Just to clarify, you're not asking for SVSM to implement the TIS-MMIO
interface instead, but rather to use the fTPM stack, which could make
SVSM calls a TEE device operation?

>
> Even if I wanted to say how this should be changed, I could not

---

## [33] Jarkko Sakkinen — 2025-01-23
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Wed Jan 22, 2025 at 11:29 PM EET, Dionna Amalie Glaze wrote:
> I can appreciate this viewpoint. It even surfaced Microsoft's fTPM
> paper to me, which solves some interesting problems we need to solve

I don't really know what I'm asking because this is barely even a
PoC, and I state it like this knowingly.

You should make the argument, and the case for the solution. Then
it is my turn to comment on that scheme.

That said, I would not give high odds for acceptance of a duplicate
TPM stack succeeding.

BR, Jarkko

---

## [34] Stefano Garzarella — 2025-01-23
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Thu, Jan 23, 2025 at 11:50:40AM +0200, Jarkko Sakkinen wrote:
>On Wed Jan 22, 2025 at 11:29 PM EET, Dionna Amalie Glaze wrote:
>> I can appreciate this viewpoint. It even surfaced Microsoft's fTPM

I'll check if I can use fTPM, in the meantime I had started to simplify
this series, avoiding the double stack and exposing some APIs from SEV
to probe the vTPM and to send the commands. The final driver in
drivers/char/tpm would be quite simple.

But I'll try to see if reusing fTPM is a feasible way, I like the idea.

>
>That said, I would not give high odds for acceptance of a duplicate

Got it ;-)

Thanks to everyone for the helpful feedbacks!

I've been a bit messy these days and I'm in FOSDEM next week, so I hope
not to take too long for the v2.

Stefano

---

## [35] Jarkko Sakkinen — 2025-01-23
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Thu Jan 23, 2025 at 12:09 PM EET, Stefano Garzarella wrote:
> On Thu, Jan 23, 2025 at 11:50:40AM +0200, Jarkko Sakkinen wrote:
> >On Wed Jan 22, 2025 at 11:29 PM EET, Dionna Amalie Glaze wrote:

Yeah, OK one thing that I want to say.

Nail the story. What is it about what is the problem what is the
motivation to solve it etc. If you have all that properly written
up then it is easier to forgive not that well nailed code and
give reasonable arguments.

And don't rush, I have all the time in the world ;-)

> Stefano

BR, Jarkko

---

## [36] Jarkko Sakkinen — 2025-01-23
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Thu Jan 23, 2025 at 1:46 PM EET, Jarkko Sakkinen wrote:
> On Thu Jan 23, 2025 at 12:09 PM EET, Stefano Garzarella wrote:
> > On Thu, Jan 23, 2025 at 11:50:40AM +0200, Jarkko Sakkinen wrote:

Here the point is that if I don't fully understand the context
(starting explaining the obvious like what is SVSM) I might 
give some ridiculously wrong advice.

Then people come back to me and start blaming me on saying
opposite arguments. I hope you see where I'm standing here.
I neither don't want you to do useless and unproductive
work.

BR, Jarkko

---

## [37] Stefano Garzarella — 2025-01-23
*Subject: Re: [PATCH 3/3] x86/sev: add a SVSM vTPM platform device*

On Thu, Jan 23, 2025 at 01:49:34PM +0200, Jarkko Sakkinen wrote:
>On Thu Jan 23, 2025 at 1:46 PM EET, Jarkko Sakkinen wrote:
>> On Thu Jan 23, 2025 at 12:09 PM EET, Stefano Garzarella wrote:

Yes, I completely understand your point and I admit that the cover
letter and the commits description were not very informative, I will
fix them putting more context.

>>
>> And don't rush, I have all the time in the world ;-)

;-)

>
>Here the point is that if I don't fully understand the context

I see it completely!

>I neither don't want you to do useless and unproductive
>work.

Thanks for that,
Stefano

---
