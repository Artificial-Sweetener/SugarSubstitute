## [0.21.3](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.21.2...v0.21.3) (2026-08-21)


### Bug Fixes

* **releases:** qualify versioned historical installers ([2211e40](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/2211e4092282a2c6aeffb610a3e6abf0088be4e9))

## [0.21.2](https://github.com/Artificial-Sweetener/SugarSubstitute/compare/v0.21.1...v0.21.2) (2026-08-21)


### Bug Fixes

* **installer:** install managed nodepacks without system Git ([029de3d](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/029de3d421aba9f3fac36f9e9aef27c3cad1e01d))
* **releases:** restore reliable release links and titles ([da8df40](https://github.com/Artificial-Sweetener/SugarSubstitute/commit/da8df403d506fe9100bf7f9b92fcdb4add3ce1c4))

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
