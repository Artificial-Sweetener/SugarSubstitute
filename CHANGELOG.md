## [0.23.4](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.23.3...v0.23.4) (2026-09-20)


### Bug Fixes

* **dependencies:** update every cube-required node pack ([6ad2ed1](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6ad2ed1c6faab44dacd96491cde5cdc85c53e73b))
* **startup:** accept newer SugarCubes while repairing cube dependencies ([3b06bf8](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3b06bf87f6347862b454fd5949c5180487098b6b))

## [0.23.3](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.23.2...v0.23.3) (2026-09-20)


### Bug Fixes

* **workflows:** preserve projects through Cube updates ([e5a4335](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e5a4335e1f936b66a733c8bdefc85c3b8c75deb4))

## [0.23.2](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.23.1...v0.23.2) (2026-09-20)


### Bug Fixes

* **cubes:** update node packs to cube-required versions ([785e0c1](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/785e0c1f76f2be999e04b516ad11ee75c51223c3))

## [0.23.1](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.23.0...v0.23.1) (2026-09-20)


### Bug Fixes

* **prompt-editor:** keep caret movement safe after token replacement ([fe3c0af](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fe3c0afdb886bb7fa2f16ee812b65b2d670ade85))
* **release:** finish managed update qualification promptly ([c56277b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c56277bb9d8067a52fe2cf4cf5d2af5f0ce8f5e4))
* **release:** ship reliable 0.23.1 upgrades ([#208](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/208)) ([c489624](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c4896246a8520c9fdcf7888b8ed51a2e1887f107))
* **updater:** complete 0.23 upgrades in managed Windows hosts ([b0682cc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b0682ccee7f18ab5cf0ce613981aa939030944ec))
* **updater:** complete 0.23 upgrades without repair ([570fb59](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/570fb595696f62270369337546b3da699372b85e))
* **updates:** keep one splash and retry interrupted releases ([3fa7c53](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3fa7c532b8b614594b145e809a9dbded969d783d))

# [0.23.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.22.0...v0.23.0) (2026-09-19)


### Bug Fixes

* **app:** preserve macOS singleton ownership under repeated launches ([79fa466](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/79fa466c2c0fb21f3e766ad504877f741cc9f802))
* **app:** release singleton ownership before relaunch ([765c3c0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/765c3c077782e266d9a386ed2405f174c36c6564))
* **app:** release singleton ownership synchronously ([2caa4c1](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2caa4c1b7bf2ed9a7da5246ac4bda6c3798f5442))
* **app:** retain fileless singleton fallback without Linux D-Bus ([d9ba48e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d9ba48e73a3854afbb5b958cac385d333656c36b))
* **canary:** keep startup recoverable and empty model pickers usable ([a9f734e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a9f734eb62cfb47c16342c2423a1e7871cb2fb4d))
* **canvas:** close output resources safely when the app exits ([d13bd81](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d13bd81d32c599f32c305aae82eacafd7eeaf372))
* **canvas:** keep output grids stable when undocking ([948ab89](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/948ab89790e1874378fa15f654bee525843f5ad8))
* **canvas:** preserve generated output event order ([66810f3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/66810f3125f0e21edb4182e29f85d30f5ca88991))
* **canvas:** preserve imported image precision in saved projects ([be219b1](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/be219b1902cce8282afb268a91960edab3d75f3e))
* **comfy:** build repaired environments at their final location ([38175db](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/38175dbb3b23ce028d089eb212ba6c10a58ad191))
* **comfy:** keep startup checks from blocking the server port ([fb975c2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fb975c2e0c94f16d591a93be5df73b2d43e8d609))
* **comfy:** restart managed Comfy after confirmed cleanup ([3d17b46](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3d17b462140b5c84aa4616bf45892392ea76423e))
* **cubes:** keep model badges legible on cube icons ([007fba0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/007fba0c2f733d2e821ba728998c5ba96fdb7cec))
* **diagnostics:** redact control credentials from error reports ([1647c4e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1647c4e8125e0cffb05ed8c62e36db953351e476))
* **editor:** edit emphasis and LoRA weights with native text controls ([aa8aadb](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/aa8aadb55868a34edfeace745b88cff22d7271b5))
* **editor:** keep prompt reordering safe across closing and font changes ([75cf4fe](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/75cf4fe26c349e37aca7c9010e6ea6028621c874))
* **installer:** close repair preparation without leaving workers running ([4f136fd](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4f136fdabd4fc65f30f9ed76e7e841a86057b228))
* **installer:** complete canary setup and shutdown reliably ([d094abb](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d094abb9086350942a62901a6512419d2131fadb))
* **installer:** complete canary setup handoff reliably ([0cf2029](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0cf20298ee4d97803043affeb68fa6096e1bb275))
* **installer:** complete macOS onboarding launch qualification ([e0170b7](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e0170b757dec511553cca58a279af033965ce6d0))
* **installer:** fit integration choices on every platform ([18942e9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/18942e9b7a96faad475ab53a0e3b3db75a783970))
* **installer:** keep Comfy repair activity visible while it runs ([e4570ea](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e4570ea70e13f79501149edbf2bd8693ee16a9b0))
* **installer:** keep fixed-resolution layouts portable ([7e91d91](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7e91d91086218f280050409721f2a295b8a3ef68))
* **installer:** keep model cards within the macOS viewport ([1bc3fea](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1bc3fea895453ecdc68f62aba1dc695cf1b68225))
* **installer:** keep setup choices coherent and contained ([fac898b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fac898b448e068a4ebd388ae7e17a01baec0eac7))
* **installer:** keep setup details usable and recommendations installable ([bb1735c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bb1735cc8a8bc4533692f8f0bfa5481deb9a04d6))
* **installer:** keep the close button in the title-bar corner ([438d604](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/438d604fce54872225a22c3085487041f6932936))
* **installer:** launch macOS setup from disk images ([1632e9f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1632e9ffa261e21b90d2c01091a87778c14f2805))
* **installer:** make canary setup complete installation reliably ([b4a6d1d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b4a6d1d3fb3f56b2bdedb0fd8763bf379a33fd3e))
* **installer:** optically center the title-bar wordmark ([2a3a9fd](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2a3a9fd1218beeaec8beef575a413bb9cafef9cb))
* **installer:** present advanced setup in two columns ([26f4bf8](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/26f4bf86e6bf80a40f54d13e9d5950e419dcff9a))
* **installer:** preserve Windows upgrades across launcher changes ([17e6d49](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/17e6d494b05df191bcc911ea37dfc1a8eb6d8490))
* **installer:** prevent false macOS crash reports after setup ([39788f3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/39788f393d31d007cf66fb749335369273cd086a))
* **installer:** qualify clean application shutdown without crash reports ([ee2714d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ee2714d7460116dfa5617858f9795d93b6c805c8))
* **installer:** recover managed nodepacks when Registry fails ([aecc507](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/aecc507136716a00c122d14333fb0d9ba07d2bfb))
* **installer:** remove redundant page eyebrow labels ([018c8ba](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/018c8bae638645c08626951d61ee35633d51eefc))
* **installer:** ship the onboarding wordmark ([6cd857b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6cd857ba0f19516b690706e0dadd0a85772b6e51))
* **installer:** show Fluent progress through installation stages ([58d120c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/58d120cd21394c60ba65ea190ce8d311183246db))
* **installer:** show repair preparation progress as files transfer ([6dc132a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6dc132a0efe7bf8449d2b5845e55f64f8e64b1a2))
* **installer:** show supervised setup windows on Windows ([60ae16c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/60ae16cdf68b3e89f8e932ba23335084ee1397c9))
* **launcher:** activate the existing splash during delegated startup ([8fd4dfc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8fd4dfc2ec545a095d5d9efa2248c87424a5ff69))
* **launcher:** keep installed apps usable when updates cannot run ([4725292](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4725292019133632b19e24bf02c84a9d9dbb4a9d))
* **launcher:** let automatic updates finish without opening repair ([8445db6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8445db6209ef13ba3ccce6435ff84309e196dc83))
* **launcher:** prevent updates from closing the app without restarting ([00b3854](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/00b3854b499a9539f6dd46eaa1c2cf70c646b465))
* **launcher:** recover automatically when an updated launcher cannot start ([8b7ffb2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8b7ffb2aa2ee567571592f8854bbdc9614c621da))
* **launcher:** recover crash reports without opening Repair ([48186bb](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/48186bb0eedfe8979401f3e945204a04fe41879c))
* **launcher:** reopen repaired and updated installations reliably ([523bba2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/523bba24cb83a1665a248a67b2104093b49caa90))
* **menus:** make action menus toggle reliably and show correct row states ([613b460](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/613b460b8307fbb9fd68cd6a42317d2e67e65733))
* **models:** finish discovery cleanup before reuse ([aca4a6c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/aca4a6c6af2eba38dd13f2117551f8ad53a26540))
* **models:** keep model discovery responsive on cold start ([c4eb97b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c4eb97bd7e67416ff0ea47dd5dae518106c11364))
* **models:** keep recommendation galleries responsive under repeated use ([773aada](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/773aadabcfda7b897763b80ddf2841b41b3567cc))
* **models:** keep repeated discovery browsing responsive ([a5dea64](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a5dea64851a80c03d1e7dc16a04da1b65c475362))
* **models:** retire discovery workers deterministically ([4c97a37](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4c97a37e335e96dabec05b5e0e64b2ec1604910a))
* **models:** show thumbnail pickers reliably as metadata loads ([27d07f7](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/27d07f7a17a80b7c545ff22b4b17a677af23944d))
* **previews:** restore streaming cube placeholders across outputs ([c9d102a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c9d102a87bb311a89d80e59a3956d35d5427b9c2))
* **recovery:** end frozen instances without leaving background processes ([35a9e7b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/35a9e7b47e290158dfc9ee0280886c6b22166579))
* **recovery:** keep frozen-instance recovery available after retries ([e3ae3b7](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e3ae3b744f11b74d3d2b7c4b512e087df4023467))
* **recovery:** recover stalled startup and repair without manual cleanup ([d5c58cc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d5c58cc12e8d5a3e70e17145a51833c4ecdd25aa))
* **recovery:** reopen the app when a frozen instance cannot be reached ([8ec8fae](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8ec8fae016ace949d942c0a13c0ce2a5f4dc5c62))
* **recovery:** show usable crash reports and restart reliably ([132d154](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/132d1540d3c813d2340d380d2caf4586853e0d7d))
* **release:** qualify Canary on the supported Windows target ([980b985](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/980b98523750baa09cb2436dfacb9cbd62d0f954))
* **release:** restore cross-platform Canary qualification ([f12aaf5](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f12aaf548025f2a423251cddccf6636988f9c34a))
* **releases:** keep qualification resilient to transient file access ([b0ceb4f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b0ceb4f9c004c158f0136c0e0857e5d598bf7af0))
* **reliability:** prevent emphasis crashes and include diagnostic logs ([1fd9c0b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1fd9c0be8b21b1fddd9adcf24cee338e7353316b))
* **repair:** preserve Cube libraries and model selection ([8f7be3f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8f7be3ff36dd767e5de0b75fb2cced5d491891ca))
* **repair:** rebuild the runtime without losing Comfy configuration ([5749d6d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5749d6d515170dc4efffac960b760ffedd470af7))
* **repair:** reliably complete worker and process cleanup ([685da9b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/685da9be3a0e27182081be6549243c0eaa09aef7))
* **repair:** resume interrupted rollback without losing original files ([ec71753](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ec717534b1370349f4b76217de7c237a3b0ee3d4))
* **runtime:** stabilize generation results, canvas previews, and shutdown ([573385b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/573385bb7cb905768f816ec1c2aadbe1fe336af9))
* **setup:** allow managed startup without optional Diffusers ([2fbd6af](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2fbd6af299f5db934facc92245cd3b173816f5f0))
* **setup:** guide recovery without deleting existing ComfyUI files ([194de10](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/194de1055850feb0f8d59aa4659515b8f45bf17c))
* **setup:** keep changing setup content readable and scrollable ([a06792d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a06792d247d7b694d0b433c19460da5fab45b6bf))
* **setup:** keep completed and failed setup status stable ([4112ef0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4112ef0001d5a00899e7ccd6531322fb012e13dd))
* **setup:** keep failure recovery responsive ([b19f6ea](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b19f6ea775f20aabb2884c44e3397e9a8669c92b))
* **setup:** keep installer pages accessible on smaller desktops ([49add82](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/49add82fe0968f04e3c4cfb23420b3eef0a1be66))
* **setup:** keep installer progress output responsive ([e42a934](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e42a934bf73ab8ea3e50030cc52ac3ab7ef5fb1b))
* **setup:** keep one owner when choosing an installation folder ([e9b31b6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e9b31b6c9288b71536fc6454020cc8766f3e6555))
* **setup:** prevent crashes when installation and repair finish ([0f56c3f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0f56c3f021e1f8a0f4e9c586439a01345ef471b9))
* **setup:** reclaim runtime helpers when commands stop ([8280b4b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8280b4bff605ca2a420ceda503bb3680774977c7))
* **setup:** recover interrupted Comfy environment preparation ([122109b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/122109be46435565b715eb19789fbb09e4d3f98d))
* **setup:** resume interrupted runtime setup on launch ([f3803f5](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f3803f5c022689149f504bcc553dc1e1e5d8e24c))
* **setup:** retain the chosen folder after interrupted installation ([776f787](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/776f7878ab99489562edb04b82d1c6fee511ceef))
* **setup:** show current ComfyUI preparation activity ([480f141](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/480f1417c4a8a336ad1f9735daec3d5eec66853c))
* **shutdown:** close notifications before Qt teardown ([3822a85](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3822a85d86f7d5211c419e213310d62251e4e357))
* **splash:** show clear startup progress and integrated console feedback ([d402c00](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d402c002f18212cc52c1b23ea7a9f27212b198cc))
* **startup:** acknowledge splash closure before shutdown ([c257c0e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c257c0ed892b729ad28d255d3a988544ec0dda95))
* **startup:** avoid false recovery failures when an instance exits ([5a6eb19](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5a6eb19c9d6dfc2189f8f3b186a079a8954b87ed))
* **startup:** avoid repair after a clean application close ([3444356](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3444356c4b8e233c98f36e673aad19f5a4bf6e47))
* **startup:** cancel loading when the splash window is closed ([2b0f2bc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2b0f2bcdbd528911e5c79196f14ea16151c5a7d3))
* **startup:** close cancelled launches without opening repair ([3d5fd75](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3d5fd75ec161c49409d6afe8fc37037cf591656c))
* **startup:** close failure reports without leaving the app running ([44a7c14](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/44a7c14e42e3bc8904f4b95bbe66058f6050183c))
* **startup:** finish background process cleanup before completing shutdown ([1926464](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/19264646854c292b65f5b4fc59ab4931f5073211))
* **startup:** keep app restarts responsive to repeated launches ([9b77f2b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9b77f2b46d531266fdd971ca23cc3c1fb9e052a7))
* **startup:** keep first-run and repair handoffs visibly usable ([96236a6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/96236a6b4ad6780045ef328ecb791b8b36348d92))
* **startup:** keep installation and relaunch visibly recoverable ([6f026a8](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6f026a8f988268cd21e28de0ef28fdfe38cb1750))
* **startup:** keep launches intact when application windows are replaced ([dd17d7e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/dd17d7ed15c1fffcac0cffa8fdc435895d43e72c))
* **startup:** keep one app instance across different launch environments ([9bfb319](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9bfb3193c4f6cdd65dde428e4de27b79b50bd4b5))
* **startup:** keep splash failures from blocking launch ([04c83ae](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/04c83ae232e29962340bd78fcbac89cbfc67c377))
* **startup:** make macOS instance election crash-free ([7cd3267](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7cd3267b0c52b02b0cc24f308664e29cbf027022))
* **startup:** make Windows release qualification deterministic ([227c389](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/227c389fc13b055deb36999bc510c2257604c71b))
* **startup:** preserve first-run readiness across handoffs ([2ef3592](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2ef3592b545097845c715c5225786a130610fbcf))
* **startup:** preserve owner identity and immediate relaunch ([42abe13](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/42abe131cc5ac78c69ff3bad4094f447324e321e))
* **startup:** preserve queued launches through interrupted registration ([5b20e8f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5b20e8f303df4be7414e91e650845141fe065cff))
* **startup:** preserve recovered app during simultaneous launches ([7730928](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/77309284b60d4201006822bb966a1194ecb7d4b6))
* **startup:** preserve waiting launches through application restart ([1993abe](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1993abe6a15c0ddf272573278b528916029c28f0))
* **startup:** recover Comfy startup and reliably retire owned processes ([80e0eab](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/80e0eabede7e996bc5d1eeca9bdf736886d078fc))
* **startup:** recover interrupted installations automatically ([2331f03](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2331f03b5154c689a4854e5b5d911455b3308870))
* **startup:** recover unresponsive instances without manual process controls ([88ca312](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/88ca3121d86372b6676097af8fe329fc28f29c29))
* **startup:** release instance ownership reliably during shutdown ([1964fdb](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1964fdb88d9731c1b522cb882e85c51cf8a63aa1))
* **startup:** remove frozen splash processes when the launcher exits ([d09488e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d09488e4ef8c8a0f809a36132773a83f9b6c0e71))
* **startup:** render splash controls in the selected Fluent theme ([e349d04](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e349d043f57dc2fd75bdcaebcd90a47a85e78849))
* **startup:** retry interrupted core nodepack downloads ([2dc2387](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2dc238747c9a7a0ceac27dae75d434ef48005bcb))
* **sugarcubes:** preserve nested defaults and hide consumed controls ([465562a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/465562a1dfd908d75fccc85d69f611a6c2927fab))
* **updater:** complete Windows upgrades across release generations ([ca5da94](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ca5da94724d66132dafd8cff42863567b2aa9f30))
* **updater:** keep silent Registry installs visibly active ([76d4d6f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/76d4d6f599396fe0d8ceb6c7a9fa2d6ddeca29ef))
* **updater:** launch the selected application generation cleanly ([c54bdec](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c54bdec3f491ae4269f0f2a7bdac1bf4c0e4e01e))
* **updates:** keep Canary compatible with existing installs ([208e4ab](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/208e4abee8809f599512a18bd9022b7ba639b20d))
* **updates:** ship the startup UI with Windows launcher updates ([7826680](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/782668026cef73be748faf78153fb74a8f94e256))
* **workflows:** keep Cube updates and stack navigation synchronized ([2479525](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/24795256ddf0db53deac40414a9a1e9dfb889e8c))
* **workflows:** show workflow names in unsaved-work warnings ([0a937e9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0a937e9f6313b28cb125c958d992e2f47c9cfd9b))
* **workspace:** preserve editor width when switching workflow modes ([bee6dfb](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bee6dfbe2d3ea4325575340ee70d283453535a16))


### Features

* **app:** deliver native single-instance launch and Canary improvements ([3ef2def](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3ef2defa18c3cec41c5585de23190478e6ddc717)), closes [#142](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/142) [#143](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/143) [#144](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/144)
* **canary:** improve startup and Cube workflow feedback ([d44ab1d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d44ab1d27ab3a631fedc3c46d47904ed9110c0ea))
* **comfy:** integrate server crash recovery ([92e13bd](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/92e13bd669303c318b49025d92c273e39501a709))
* **comfy:** recover from server crashes without disrupting work ([2c35db2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2c35db2eaa7cf8e321d4415da518f4ab8c1d0551))
* **editor:** surface field actions in node card menus ([e7b9323](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e7b9323a7499087a6cec03507050f6f6e7cfb0bd))
* **installer:** deliver a polished guided setup experience ([548fced](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/548fced4f4e21edf27a0fdb01535444c1b6fd9f7))
* **installer:** guide shared model setup and downloads ([22f782c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/22f782c8f2142d353e6d4e326f0090afd3e91302))
* **onboarding:** guide ComfyUI setup with live model recommendations ([8f1c90c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8f1c90cf3914dc1db8b332dba4a3cc951407cef1))
* **reliability:** add comprehensive crash recovery ([5a4cb05](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5a4cb05fabed1639355867546602dd9c8a859269))
* **reliability:** integrate comprehensive crash recovery ([740f72c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/740f72c12dd36b7a96f92466127462ae2a465fd9))
* **setup:** deliver repair and guided model onboarding ([220de1b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/220de1b41eb55ad87243cd2e1a029d2bbeb50b5a))
* **setup:** integrate repair and guided model onboarding ([190f528](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/190f528ac22a3960a333692435ef6181b67e23c1))
* **splash:** add Cass and four new poses ([7cb8135](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7cb81355516cc657d504b96aa7c169235d135bf3))
* **startup:** show Fluent progress while the application opens ([12a92d9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/12a92d9e8aa1da23eaaeb678ac6576a6fdc50078))
* **updater:** deliver resilient authenticated updates ([2a190a9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2a190a9b2a6b70601dde80537613c801e626cf05))
* **workflows:** make canonical graphs drive editing and generation ([5aa339d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5aa339dac9c39be6aaa89dd9ea79a894e954a217))

# [0.22.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.21.2...v0.22.0) (2026-08-30)


### Bug Fixes

* **canvas:** preserve generated images through memory contention ([5731441](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5731441494facb11b04d6149c1fc401a46093970))
* **ci:** report package cache restoration accurately ([8890965](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8890965de8e7de69a1e0b5ae865196401445c7dd))
* **comfy:** preserve managed runtime policy during recovery ([b4613e2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b4613e2418a971a689f505784cbd36d19765c8e6))
* **comfy:** prevent repeated connection reset errors ([fb34b9a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fb34b9a6a84b7b3c8ed2e54d9d15add83ba39e1e))
* **comfy:** restore reliable multi-stage generations ([b257e32](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b257e32b55da99cd84d2be384e9bf3c588faf7d1))
* **inputs:** load every declared image asset through Comfy ([ee72b6b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ee72b6b499574d8899b19eb409acce56c48e02c0))
* **inputs:** recover generation after Input surface changes ([0269bb0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0269bb0456d51a8e948528f2a6e460bf055f2291))
* **installer:** make app payload extraction deterministic ([f91392f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f91392f1d9a7ac9d57018fcf265e714d7316d7a7))
* **installer:** preserve reliable cross-platform launch migrations ([d041936](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d0419360325b84af59468dfcd619ee04667b837e))
* **installer:** prevent setup handoff stalls ([db0464d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/db0464dac9ef5836f55ab06bbbde8a6b258741b2))
* **launcher:** prevent false repair prompts after successful updates ([d42574b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d42574be758cd0c0a3c861300c66995b66950e01))
* **release:** preserve Stable version resolution during publication ([419b0b9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/419b0b935f5b8a3950920ab0dcd9565e283573f5))
* **startup:** make first managed launch deterministic ([3770429](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/37704295bad7a218b4690ef3cbad9a934b50b937))
* **startup:** prevent duplicate app and splash instances ([4a18a15](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4a18a153493bf279e64acf1424d6b669d2d3da32))
* **startup:** prevent rapid launches from starting duplicate instances ([3ce1765](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3ce1765f14f40ddf129e3d5a89530600d337a0fb))
* **startup:** publish readiness when the main shell appears ([d74b96f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d74b96f4fe09cd0326f5aa6d1636a9529149542b))
* **startup:** show the splash before application startup work ([1378109](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/13781094be2e8581d2d2d786c63bf534faf5cd6d))
* **updates:** apply managed nodepack pins after app updates ([b2fe321](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b2fe32111ddb3f0c9f996ba4ab969353a4286efe))
* **updates:** finish startup after managed nodepack repairs ([792da18](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/792da189cb98eefc3da7f2485199e417514eb74f))
* **updates:** recover failed upgrades and explain the rollback ([fb9cfda](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fb9cfda2e6e913d182b78f70955560713554497a))
* **updates:** restore reliable Windows automatic updates ([2f57864](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2f57864243119bc695892fe95001891838fd01cb))


### Features

* **comfy:** make managed workflows and releases self-contained ([b15aa4c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b15aa4c5b429051d0b99ce5893135c7f1abf9380))


### Performance Improvements

* **ci:** keep hosted dependency reuse lean and deterministic ([d89fddc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d89fddc184053c8a70d08d15ec48caebc4085b99))

## [0.21.2](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.21.1...v0.21.2) (2026-08-22)


### Bug Fixes

* **canvas:** preserve Input focus through transient projections ([9bb0668](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9bb0668923fdc02c2c229e1da12c068e5209508d))
* **canvas:** settle picker focus synchronously ([4e6ac9f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4e6ac9f62f1c37fcade49670d436758cb7356c05))
* **canvas:** verify picker focus after event dispatch ([1c9f2b6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1c9f2b68d6af72913c01dacc1abc72560b1dfc04))
* **installer:** install managed nodepacks without system Git ([029de3d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/029de3d421aba9f3fac36f9e9aef27c3cad1e01d))
* **releases:** preserve self-contained macOS history ([4200d4b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4200d4bf9dbad5e75b20b3d5e736d3981f5f2a3b))
* **releases:** publish only fully qualified builds ([e0fcadd](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e0fcaddec25754661e6333a66b9c7bad13869e6f))
* **releases:** qualify historical installers on every platform ([39c7a4a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/39c7a4affcc49fea862988e8a11f6c6a431c9e19))
* **releases:** qualify private Stable assets before publication ([aeb9dd8](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/aeb9dd88e867cd90badcca1cf744afef60008036))
* **releases:** qualify versioned historical installers ([2211e40](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2211e4092282a2c6aeffb610a3e6abf0088be4e9))
* **releases:** resolve Stable versions without write access ([14df3c7](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/14df3c7be0782ec33b999a3ab5d9f0be541bfba4))
* **releases:** restore reliable release links and titles ([da8df40](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/da8df403d506fe9100bf7f9b92fcdb4add3ce1c4))
* **releases:** show concise Canary version labels ([2413709](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2413709c6c56aff6a03af8b6bdf78e593cf724ee))

## [0.21.1](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.21.0...v0.21.1) (2026-08-16)


### Bug Fixes

* **releases:** publish existing Stable tags correctly ([#68](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/68)) ([d226fc8](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d226fc88f3f938a99e37d91f1ba2adaf83a6020f))

# [0.21.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.20.1...v0.21.0) (2026-08-16)


### Bug Fixes

* **cache:** keep compatible data reusable across upgrades ([fdf7e24](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fdf7e243b50070a028cf6928b671f8ae857c106d))
* **canvas:** make Canary focus and test execution deterministic ([#56](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/56)) ([3ac8f53](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3ac8f53e4eba2287070ea494498333aad221096b))
* **ci:** stabilize native canvas release checks ([#54](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/54)) ([3cd8934](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3cd8934f6f6966049187ba5b647843235a2d00f2))
* **comfy:** cleanly stop managed runtimes on macOS ([a87492e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a87492e09194c27c28dfe960ec84f1b2014d1747))
* **comfy:** launch CPU-only managed runtimes in CPU mode ([9034a04](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9034a04cb0748c949f788d81ac5cebbe171f5523))
* **execution:** publish detached completion after settlement ([b97a09d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b97a09df0a12c353ddb793e596ff8ff309ffca3d))
* **installer:** complete managed setup across supported platforms ([e877358](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e877358e6ccfb926b1b1235e2dedcd025d7f2440))
* **installer:** complete native install and update qualification ([56c0265](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/56c0265101a8789d166ceaed11ea7766e102dd23))
* **installer:** complete staged install qualification ([fe711a2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fe711a2512fc2210c95a08d3e34e242809eebf7e))
* **installer:** preserve CPU and portable update launches ([02b1849](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/02b1849bd33dc6af3d748d6c93e42bc4c0db09e2))
* **installer:** preserve trust and qualify existing runtimes ([5600b37](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5600b379ce903eef689a685d94007101db5b96a8))
* **installer:** qualify real installs and updates across platforms ([3333379](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3333379fde939c55049850b02d5634ff63b96b47))
* **installer:** qualify safe installs, updates, and startup ([6e77f76](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6e77f76b889bb735fb389f78c8f83b448039afce))
* **installer:** qualify updates with candidate installers ([df62251](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/df622514b411d6a8ca6cebe68b8b64c2c0276740))
* **launcher:** accept managed runtime symlinks ([9b19878](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9b19878b32b566ec0987ffdc78354a20e896407d))
* **launcher:** preserve installed POSIX launch routing ([fd95ac3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fd95ac3390ea3b71af4553c0960387bf84278a13))
* **launcher:** preserve packaged invocation routing ([6c20d9f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6c20d9f438d6115a43cd24ed9b10f7dfe8a38378))
* **launcher:** recover validated packaged install roots ([f65ec0e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f65ec0e7a3443486a6dd38864d891be0ab3bac82))
* **launcher:** retain packaged bootstrap failures ([cf37f96](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/cf37f962fbc2dc35a826a52f7a4eb0425d4aae78))
* **launcher:** route Linux from native process image ([05656c0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/05656c06b0dfafd14f1bba60026289ca1b9c9d7c))
* **release:** package installable macOS launchers ([882baa3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/882baa340613c80a85c73f75de5f05084a5553e1))
* **releases:** publish Canary through an unambiguous rolling feed ([#55](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/55)) ([108542b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/108542bc2d2db375e4b240499b82518810afd2ac))
* **startup:** allow installed applications to launch offline ([a2abf8a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a2abf8a6b388af59448d14b6891bf2dacd027589))
* **startup:** keep offline fallback from masking local failures ([7e82593](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7e8259332ab69ea24868eae8f2104d864f0f3b4f))
* **updater:** complete historical updates from the installer open action ([f6771e3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f6771e3cce298f3b5c1c4d579fb687b2939db88e))
* **updates:** qualify releases and roll back failed launches ([23d00b4](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/23d00b4e528ad77b5673c8445db98a1b87bf478a))


### Features

* **releases:** promote verified Canary changes to Stable ([#62](https://github.com/Artificial-Sweetener/SugarSubstitute/issues/62)) ([5424bd0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5424bd06696133c47fa5b48202dca111c689bc1c))
* **releases:** provide an isolated Canary install and update channel ([cfa4406](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/cfa4406a0b9a733be00ca5983b6c556450fa94ff))


### Performance Improvements

* **installer:** extract macOS managed runtime in one pass ([11d5c86](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/11d5c86308fdf616e44319b80ba412a905bfb330))
* **installer:** skip forced-CPU accelerator probes ([10f80b9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/10f80b936749583aa652df826173de2b5b295a62))

## [0.20.1](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.20.0...v0.20.1) (2026-08-12)


### Bug Fixes

* **nodepacks:** release git handles before migration ([6df5afd](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6df5afdda2c94f4c900fa719747626b772d7c86e))
* **windows:** avoid recursive path conversion ([c1737a0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c1737a01ac6876400a4701eb21c5e444e902fe66))
* **windows:** restore managed updates for relative paths ([637d4e0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/637d4e0ed9a67ecb7465aabf50c9213c52578d94))

# [0.20.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.19.2...v0.20.0) (2026-08-11)


### Bug Fixes

* **canvas:** prevent top-bar layout feedback loops ([eb87f65](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/eb87f6549b87d795197942b46872421b0994e45f))
* **canvas:** rebind previews to active output session ([a9b1d7d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a9b1d7de4c77ae256e2fb928d4e3f130b2a52759))
* **canvas:** release destroyed zoom indicators safely ([50ff9d9](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/50ff9d97312325c876073bb171de505d88036993))
* **ci:** stabilize serial canvas verification ([39c22af](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/39c22af6b1fb4f4125e8fbaf93aa0bc489cb9036))
* **deps:** update js-yaml security patch ([ee5866f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ee5866f5d3611d39f14efaa9fd6070973259af75))
* **inpaint:** restore local image and mask execution ([7fa67df](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7fa67df613cb3077ee6f0411a613fa42e9a5003e))
* **input:** unify canvas entry ownership and previews ([a813957](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a813957d0b559493ced1c9fce71c3e1c61897cd1))
* **nodepacks:** reconcile registry managed installations ([c2261e0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c2261e071e36345ec5245da6de0dffb4fb0b3945))
* **output:** reset navigation on first session result ([bb4b44b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bb4b44b0b99e40f60c7f64369d3baf67418c7929))
* **prompt-editor:** centralize decorated text mutations ([6d43caf](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6d43cafa0ae034c46435d1ad7f009bcb486daafb))
* **recipes:** serialize only authored cube inputs ([b1007dd](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b1007dd06539b796556aace5350dc3ff3ff913c7))
* **startup:** keep SugarCubes maintenance non-blocking ([ef790cc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ef790ccceee5d4db8b6abb4c2241383b493d4e7f))
* **wildcards:** honor effective workflow seed ([bb32443](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bb324430ba87a85be24c0f644f2d1625674b7e55))


### Features

* **canvas:** add contextual selection and mask editing ([b54f9a2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/b54f9a20db0e1bef42d0c2a008d8851390f08858))
* **canvas:** add extensible input tool strip ([0e6a507](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0e6a507219f5265b98abe58c825344672f9f5f70))
* **canvas:** replace pivot with selector and brush settings ([37f97aa](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/37f97aa0d664e5cca339401497240cc6f33e0470))
* **cubes:** preserve widget-backed subgraph inputs ([2105e69](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2105e6977c1bea5064656529bd0e5b14e6f82049))
* **execution:** add resource-aware canvas admission ([f03c782](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f03c782d270befafa6cbc0193b12b9c71296166c))
* **input-canvas:** add live editable document workflows ([ef2c0ee](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ef2c0eef6f0b19fde6bc1d39302174d5bfa4da32))
* **input-canvas:** integrate edit sessions and restore safety ([0e5cd9d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0e5cd9d4e89878b014ac8fb3be521c8ade8cba18))
* **lifecycle:** finalize session persistence before teardown ([376bcbc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/376bcbc45e7fe8150eb9f2b8ab2fdceccc18a20b))
* **output:** add captured image transfer workflows ([6297c17](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6297c17066d0df0838ca5e3802f0e7800e8a11a7))
* **prompt-editor:** add context-aware sep conditioning ([bbd13da](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bbd13da31100b8926271a16c989884bbb5e57f13))
* **regions:** author synthetic regional workflows ([bd3d239](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bd3d239039a7b5d4d979943bd0388d11fe77b2e9))
* **regions:** integrate ordered mask workflows ([3f638c6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3f638c6f52137ca60a3cb666a972bc00210abacf))


### Performance Improvements

* **ui:** cache packaged icon paths ([a32ba28](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a32ba28ffc4e80fe4c671f1eb525b68fce62d24a))

## [0.19.2](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.19.1...v0.19.2) (2026-08-03)


### Bug Fixes

* **windows:** centralize long-path boundaries ([68d94e3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/68d94e3ec38e5d807e8977c3950d5b88d7aea88c))

## [0.19.1](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.19.0...v0.19.1) (2026-07-31)


### Bug Fixes

* **comfy:** authorize local image sources ([f142d16](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f142d16d91ebda4fab9dd49e81e8b65c839d2f3a))

# [0.19.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.18.1...v0.19.0) (2026-07-27)


### Bug Fixes

* **controls:** render portable binding labels ([1616dec](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1616decf6e573eb97f8aaf86ab03b4e61bb6ab85))
* **generation:** synchronize randomized seed requests ([a72fc2b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a72fc2bb57d4cce215baea8da6e91b579aea60dc))
* **launcher:** enforce single application launch ([329d0eb](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/329d0ebf905df2f5dd1a8aabe4514a8c54e36bb6))
* **prompt-editor:** ignore stale render-frame cache probes ([7bd2cca](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7bd2cca91f75542af916c7478feb7b7837965c80))
* **prompt-editor:** preserve separator boundary deletions ([2148f9d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2148f9d67cc7268f802e4692956bdaeaeefadab7))
* **prompt-editor:** restore cache identity typing ([757c001](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/757c0014d1b86bf5694f655b702b3b230fb1ca77))
* **prompt-editor:** stabilize cross-platform gates ([066193d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/066193d50ccf787fb728cfeab9466f78c1fc5d55))
* **prompt-editor:** stabilize keyboard reorder preview ([9e0fa0f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9e0fa0facf32abed144721700e05b5e9a11729bf))
* **prompt-editor:** stabilize separator edits and transient feedback ([e315310](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e31531087fd94faca967ebbf3867db7fe669e160))
* **settings:** support prefix search ([1b6e764](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1b6e7644201f2122101f41a492c8b3e05743eb89))
* **splash:** center launch splash on cursor display ([cc633b0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/cc633b055176dd32c6ec158340542701eb9f9f0c))


### Features

* **controls:** add configurable generation bindings ([01c481c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/01c481c1c830fad95383cd49ea830b517aff5a8c))
* **localization:** add Spanish support ([934aa6b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/934aa6b1aa95ef7c854d5d4687db7338a26e774e))
* **prompt-editor:** add regional separator editing ([bc6c6a7](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/bc6c6a7bb9157f9e39bf32034e9cab8e7f06d4f5))
* **shell:** request attention for unfocused completions ([c8316ed](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c8316ed6e8867e11a597acdfda5b784eebc259ea))


### Reverts

* **prompt-editor:** preserve separator boundary deletions ([a5b286c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a5b286ce9a8575eecf99ecc20bd7ef85273c6a97))

## [0.18.1](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.18.0...v0.18.1) (2026-07-22)


### Bug Fixes

* **launcher:** check for updates on every startup ([94774e5](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/94774e571ceeec49ef26945bd5dcf91c609253f4))

# [0.18.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.17.0...v0.18.0) (2026-07-22)


### Bug Fixes

* **installer:** preserve attached virtualenv identity ([aacf327](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/aacf32705bb557144d4e0fde0994a9ae6085d138))
* **installer:** preserve virtualenv interpreter identity ([9451894](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9451894784795cf4b94ad60104c4d810c678291a))
* **installer:** reconcile updated ComfyUI contracts ([2bcc504](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2bcc504748aa301740039ad4ff1ddac41c272f42))
* **installer:** support ComfyUI 0.15 manager contracts ([d73a5e5](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d73a5e51a36ba72ceff6afe7a79b86927509421f))


### Features

* **installer:** support ComfyUI 0.15+ and Windows long paths ([3317235](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/33172356bf84122b3c502d7fb7a9584dc0dd7253))
* **integration:** merge Comfy compatibility and long paths ([eef66d8](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/eef66d8cadac5225c3f1dff6ab917b4c67b1cb19))
* **integration:** merge main v0.17.0 ([1bf5232](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1bf523283ed9728a350e8dfbfec55d51602b702e))
* **windows:** support long application paths ([5993879](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/59938792b5d4c680cbd73a96b38a5987112b18a2))

# [0.17.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.16.0...v0.17.0) (2026-07-21)


### Features

* **integration:** require versioned SugarCubes host API ([049b5e1](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/049b5e1f1ae1325e54a8b341884c1bd57a839c83))

# [0.16.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.15.0...v0.16.0) (2026-07-21)


### Bug Fixes

* **ci:** install Linux multimedia runtime ([68cf466](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/68cf466c8e163997a6f748a22780ece9d8b5139b))
* **editor:** render native Comfy workflow widgets safely ([56eb6f3](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/56eb6f378b5708fe56cdb294200da6d9600954b0))
* **launcher:** bundle localization resources ([247af4f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/247af4fccc53d9802e29338410b09d94d1eb132d))
* **model-picker:** preserve search text during refresh ([062b967](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/062b967802099464550a97d4bf12eb578977e2f7))
* **prompt-editor:** harden abuse-tested editing invariants ([0d50267](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/0d502670e552f78dcd8a9ba5e7d3664897e1e272))
* **prompt-editor:** harden bounded reflow probes ([531ceb6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/531ceb695e6abda4b82fb1a46f4d46ec0fd6e63e))
* **prompt-editor:** harden cross-platform projection behavior ([1e9c155](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1e9c1557d8bbc9c659c2633b512cbc520ec769dd))
* **prompt-editor:** keep scene title edits incremental ([fd92392](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fd92392853ffd1eba105fe21f0a0f535a90f470d))
* **prompt-editor:** preserve exact reflow and reorder animation ([6355078](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/6355078e08b7e411dce554f91fc8d0f2b9ed27fc))
* **startup:** wait safely for managed ComfyUI ([9e1ca36](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9e1ca36869203467c6df287893a2acf2967c3cb8))


### Features

* **editor:** integrate localization and node validation ([f56c58c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f56c58c761b9292aa4dd0d6d6f90789f6df0d501))
* **integration:** merge localization and prompt editor work ([46b008b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/46b008b610180a05557b103e23f75efd234e703d))
* **localization:** add Chinese and Japanese support ([367ff0e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/367ff0e149d2ddb793600c7f4510b7f29571ab57))
* **localization:** add Korean support ([a07c87f](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/a07c87f3b58e9dbe371f124a60614ba26d75b9c8))
* **prompt-editor:** add structured document semantics ([4d3d91b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/4d3d91b03041d90c5eecbe1b6a79e77ae20eddc8))
* **prompt-editor:** optimize interactive editing ([3b06226](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3b06226b02c000cbaa0535ea8987f4ccc8fc974a))
* **wildcards:** enable full prompt editing workflow ([eba867c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/eba867cf2ebfa712bfb579fd3b62cc0c5be9956c))

# [0.15.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.14.0...v0.15.0) (2026-07-19)


### Features

* **settings:** group JPEG and generation preview options ([9623952](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9623952378da86c459c4856f0f962816c41d2a83))

# [0.14.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.13.0...v0.14.0) (2026-07-19)


### Bug Fixes

* **canvas:** preserve exact output source and batch identity ([71a5cc6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/71a5cc6ffe843a8e86eb8d439281cb4723ece2c2))


### Features

* **generation:** add configurable output persistence ([3e6f23a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3e6f23a2d451238ab1815c18979668e01166a917))
* **prompts:** add managed autocomplete lists ([1d09681](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/1d096811b7cd47e59bdaecf5a9637af9d64e0701))
* **shell:** integrate workflow and preference services ([f4ec2d6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f4ec2d61fd55082f3efee9b35e55c543473c39b6))
* **workflows:** load Comfy workflows from PNG metadata ([28e181d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/28e181d71ce366520a04c3b9081a70a69bc5d810))

# [0.13.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.12.4...v0.13.0) (2026-07-18)


### Bug Fixes

* **tests:** resolve live prompt field registry ([ef57a0c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ef57a0cfc357a8ea44a2ea68e988c97bc1216cd1))


### Features

* **workflows:** support direct Comfy workflows ([f691bf2](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f691bf2f65bf8d862314f3a1f42ef99947703926))

## [0.12.4](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.12.3...v0.12.4) (2026-07-18)


### Bug Fixes

* **deps:** pin verified dependencies and automate audits ([925434a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/925434a5a27b736e5dd83ef65d137194a410577f))

## [0.12.3](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.12.2...v0.12.3) (2026-07-18)


### Bug Fixes

* **release:** replace unverified 0.12.2 build ([5028b2e](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/5028b2e92fa10d6a79d7a8e378cea6228060d794))

## [0.12.2](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.12.1...v0.12.2) (2026-07-18)


### Bug Fixes

* **ci:** make cross-platform tests portable ([8aa70bc](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/8aa70bc6c0a908a3505dc7bbbbee93470c7b6e87))
* **ci:** resolve remaining unix test contracts ([15a3742](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/15a3742d6b831e5a2bd42a0d0d38e5c8bfffa1b6))
* **ci:** stabilize cross-platform Qt contracts ([3b6a2b0](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3b6a2b03f4b694ea2e2b16cf4b89208a54624779))
* **filesystem:** remove read-only app-owned paths ([76fe068](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/76fe0682d7900e6ca00dbf97ab59251a9156b746))
* **launcher:** keep headless startup Qt-free ([ea5e943](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/ea5e9430641a723f04057f142d7cb26634c7514c))
* **launcher:** stabilize setup handoff shutdown ([15ff98c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/15ff98ced6ebea9d5c4e5aea31c6335da0ea0f9a))
* **launcher:** use host certificate trust ([33b6cb4](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/33b6cb4e956d846877b834d82527a58f4367171a))
* **linux:** preserve installed launcher executable mode ([9197d98](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/9197d98e54463c176b1ed03fabd596afd7313cfd))
* **network:** unify system trust across downloads ([fbbafc1](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/fbbafc127b1cee731a27bd57d9e33767ac30692e))
* **release:** isolate asset assembly dependencies ([7992f80](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/7992f80cccf1365e45b49c915bc10a9ebd9a89d7))
* **settings:** keep claimant labels shrinkable ([e45eb1d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e45eb1dbc960ffbda0e331e66d6af3573396828c))
* **tests:** stabilize isolated Qt execution ([e9dad1b](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e9dad1b5f3524e2313ae0ea06006f9aea8befb7c))

## [0.12.1](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.12.0...v0.12.1) (2026-07-17)


### Bug Fixes

* **comfy:** remove system git dependency ([c7abf46](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/c7abf46f0ab52fb5f40ae86494c2ee8715c2a084))

# [0.12.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.11.0...v0.12.0) (2026-07-17)


### Features

* **installer:** guide Comfy environment setup ([cb9633a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/cb9633a99ce01bf588dbf9a6723791b17d9341d8))

# [0.11.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.10.0...v0.11.0) (2026-07-17)


### Bug Fixes

* **ci:** isolate release version analysis ([29e660a](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/29e660a39f8c8177de3e947b0e517c9728e1aeeb))
* **installer:** enforce launcher-safe release versions ([f101e06](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/f101e062602d039b4189e1dec652267d11d7d683))


### Features

* **comfy:** support integrated manager runtimes ([26fa314](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/26fa314356d9279883e632d0a44e801b5dab65b1))
* **launcher:** add automatic launcher updates ([cba2ae6](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/cba2ae63d6be4c62c7bc39a1cf1474a8cd2b29f5))
* **setup:** discover attached Comfy Python environments ([213c4db](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/213c4dbeeea6be50b42c57fa20e1f7b909da4a09))

# [0.10.0](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.9.0...v0.10.0) (2026-07-16)


### Bug Fixes

* **deps:** pin Substitute BackEnd 1.7.0 ([d3df042](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/d3df0427af785b8e52a2d37858f815fd038aabd9))
* **editor:** reconcile live model choices in place ([0981641](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/09816416250b537700e895217d1fb06c32d88166))


### Features

* **comfy:** delegate model roots to Substitute BackEnd ([3757b5c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/3757b5c437832ccb497095279756d580be186e3b))
* **setup:** manage SeedVR2 acceleration dependencies ([e54787c](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/e54787c804fa2b8630c1e41d3c958e41faef08fb))

# Changelog

All notable changes to SugarSubstitute are recorded here from the Conventional Commits included in each release.

## 0.9.0 (2026-07-14)

The 0.9.0 public beta is the flattened baseline for the automated changelog. Later releases are generated from conventional commits made after this tag.
