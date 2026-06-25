# FLUKA Delayed Source Identity Gate

- status: `FLUKA_SOURCE_IDENTITY_GATE_PASS`
- dummy `HI-PROPE` ZA: `53128`
- source override checked: true
- selected histories: `6`
- selected targets: `Cu-64, Cu-62, I-128, Na-22, Na-24, Al-28`
- elapsed_s: `5.480`
- validation_csv: `/home/ubuntu/Fluka_TES_511_Balloon/engineering/crosscode_delayed_closure_20260625/00_manifest/fluka_source_identity_gate/runtime_identity_validation.csv`

## Interpretation

The production-style dummy HI-PROPE 53/128 card is not the observed source identity for these histories; the source routine overrides it with the source-v2 isotope Z/A/isomer before set_primary.
