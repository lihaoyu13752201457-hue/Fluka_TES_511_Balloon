# FLUKA Vacuum Decay-Kernel Production

- status: `FLUKA_DECAY_KERNEL_PRODUCTION_PASS`
- histories_per_isotope: `1000000`
- targets: `Cu-64, Na-24, Al-28, I-128`
- particle_yields_csv: `/home/ubuntu/Fluka_TES_511_Balloon/engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/particle_yields.csv`
- gamma_line_yields_csv: `/home/ubuntu/Fluka_TES_511_Balloon/engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/gamma_line_yields.csv`

## Key Line Checks

| nuclide | line | event fraction | photon yield per parent |
|---|---|---:|---:|
| Cu-64 | Cu-64 1346 keV | `0.004785` | `0.004785` |
| Na-24 | Na-24 1369 keV | `0.999939` | `0.999939` |
| Na-24 | Na-24 2754 keV | `0.998547` | `0.998547` |
| Na-24 | Na-24 1369+2754 same-parent coincidence | `0.998547` | `` |
| Al-28 | Al-28 1779 keV | `1` | `1` |

## Limitations

- FLUKA side only; the Geant4/MEGAlib side remains open.
- This satisfies the FLUKA-side `1e6` production-statistics target.
- Raw crossing dumps are excluded from the public handoff; use the bounded samples only to audit the schema.
- Use this to validate scorer/runtime behavior and to choose the next production run, not as final closure.
