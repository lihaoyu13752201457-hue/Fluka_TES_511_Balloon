# Geant4/MEGAlib Decay-Kernel Smoke

- status: `GEANT4_MEGALIB_DECAY_KERNEL_SMOKE_PASS`
- histories_per_isotope: `20000`
- targets: `Cu-64, Na-24, Al-28, I-128`
- particle_yields_csv: `engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/particle_yields.csv`
- gamma_line_yields_csv: `engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/gamma_line_yields.csv`
- geometry: `/home/ubuntu/TES_511_Balloon/outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy/DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo.setup`

## Key Line Checks

| nuclide | line | event fraction | photon yield per parent |
|---|---|---:|---:|
| Cu-64 | Cu-64 1346 keV | `0.0043` | `0.0043` |
| Na-24 | Na-24 1369 keV | `0.99995` | `0.99995` |
| Na-24 | Na-24 2754 keV | `0.9988` | `0.9988` |
| Na-24 | Na-24 1369+2754 same-parent coincidence | `0.9988` | `` |
| Al-28 | Al-28 1779 keV | `1` | `1` |

## Boundary

- This is an independent EventList source run, not a replay of a prior `.sim.gz`.
- The parsed records are `IA DECA` decay-emission records; detector selected-rate logic is not applied here.
- The run uses the installed MEGAlib/Geant4 decay implementation and the TES fix5 geometry only as a valid simulation world.
- Raw Cosima simulation products are excluded from the public handoff; tracked outputs are summaries and bounded samples.
- Smoke statistics are sufficient for high-yield line sanity checks but not final production closure.
