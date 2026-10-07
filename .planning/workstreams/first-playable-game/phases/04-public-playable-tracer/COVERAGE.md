# API Coverage — Libretro core ABI

> Full coverage by default. Opt-outs are explicit, reasoned decisions for Phase 04's public fixture; this matrix is also the Phase 04 `04-COVERAGE.md` decision record.

| capability | decision | reason |
|---|---|---|
| `retro_api_version` | INTEGRATE | |
| `retro_set_environment` | INTEGRATE | |
| `retro_set_video_refresh` | INTEGRATE | |
| `retro_set_audio_sample` | INTEGRATE | |
| `retro_set_audio_sample_batch` | INTEGRATE | |
| `retro_set_input_poll` | INTEGRATE | |
| `retro_set_input_state` | INTEGRATE | |
| `retro_init` | INTEGRATE | |
| `retro_deinit` | INTEGRATE | |
| `retro_get_system_info` | INTEGRATE | |
| `retro_get_system_av_info` | INTEGRATE | |
| `retro_set_controller_port_device` | INTEGRATE | |
| `retro_reset` | INTEGRATE | |
| `retro_run` | INTEGRATE | |
| `retro_load_game` | INTEGRATE | |
| `retro_unload_game` | INTEGRATE | |
| `retro_load_game_special` | OPT-OUT | One original content artifact uses the ordinary load path; multi-content subsystems are outside this phase. |
| `retro_serialize_size` | OPT-OUT | Public snapshots are a separate later contract; return unsupported size. |
| `retro_serialize` | OPT-OUT | Public snapshots are a separate later contract; report unsupported. |
| `retro_unserialize` | OPT-OUT | Public snapshots are a separate later contract; report unsupported. |
| `retro_get_region` | INTEGRATE | |
| `retro_get_memory_data` | OPT-OUT | Raw memory exposure is outside the public fixture contract; return null. |
| `retro_get_memory_size` | OPT-OUT | Raw memory exposure is outside the public fixture contract; return zero. |
| `retro_cheat_reset` | OPT-OUT | Cheat support is outside the selected workload; safe no-op. |
| `retro_cheat_set` | OPT-OUT | Cheat support is outside the selected workload; safe no-op. |

Source surface: canonical `libretro.h` from libretro-common revision `2b96a82bd8479bb3547d271e1eefadc82dd2161e`. Required ABI stubs for opted-out capabilities still export with safe unsupported semantics. `retro_run` may deliver zero audio frames under API-05; this does not establish audible output.
