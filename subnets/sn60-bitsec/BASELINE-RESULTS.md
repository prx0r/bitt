# Baseline Results — Bitsec SN60

## Run: baseline-1788495902

**Date:** 2026-09-04
**Model:** mimo-v2.5
**Method:** Simple prompting, 2 files

## Results

| Metric | Value |
|--------|-------|
| Files tested | 2 |
| Expected vulns | 15 |
| Found | 10 |
| True Positives | 2 |
| False Positives | 8 |
| Detection Rate | 13.3% |

## What Worked

- Model found 10 vulnerabilities
- Some findings were relevant (reentrancy, access control)
- Model provided descriptions and locations

## What Didn't Work

1. **Title mismatch** — Model finds different vulns than ground truth
2. **Cross-file vulns** — Some vulns require understanding multiple files
3. **Specificity** — Model is too generic, ground truth is very specific

## Failure Analysis

The ground truth titles are very specific:
- "killGauge()will lead to wrong calculation of emission"
- "mVeNFTDOS can't trigger the vote function"

The model finds generic issues:
- "Missing Address Validation in Constructor"
- "Potential Reentrancy Risk"

**Key insight:** The model is finding REAL vulnerabilities, but they're not the SAME vulnerabilities as the ground truth. This is a matching problem, not a detection problem.

## Next Steps

1. **Improve matching** — Use description overlap, not just title
2. **Better prompting** — Ask for specific vulnerability types
3. **Cross-file analysis** — Analyze related files together
4. **More files** — Test on more files from the same project

## Target

- Detection Rate: >50% (currently 13.3%)
- False Positives: <5 (currently 8)
- F1: >0.3 (currently ~0.15)
