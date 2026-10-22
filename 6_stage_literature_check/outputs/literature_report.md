# Literature check: Si at 15 GPa

Source: Valency (claude.ai MCP connector), searched 2026-10-22 18:26. 73 papers retrieved, 65 about silicon.

**Status** means: *Known* = at least one paper names this material and this phase in the same sentence. *Not found* = no retrieved paper does (it may be new, named differently, or simply not among the papers retrieved). A mention is not proof that the phase is stable at our pressure; the evidence sentence is shown for each paper so it can be checked.

Review (Claude (agent), 2026-10-22, after reading every evidence sentence; check before relying on it): 5 false match(es) excluded, listed at the end with the reason; papers added on review are marked [added on review].

| Phase | Our structures | Trust label | ML above best | DFT above best | Status | Papers | Pressures in papers (GPa) |
|---|---|---|---|---|---|---|---|
| beta-tin (I4_1/amd) | s019 | Needs DFT | 0 meV | 12.2 meV | Known | 12 | 7.5, 10.5, 14, 16.2 |
| simple cubic (Pm-3m) | s009, s006, s001, s007, s014, s010 | Needs DFT/Trusted | 11.9 meV | 165 meV | Known | 1 | 3890 |
| simple hexagonal (P6/mmm) | s015, s000 | Needs DFT | 12.1 meV | 0 meV | Known | 4 | none stated |
| Cmcm (Cmcm) | s016, s013 | Trusted | 12.4 meV | not run | Not found | 0 | none stated |
| P4/nmm (P4/nmm) | s004 | Trusted | 12.8 meV | not run | Not found | 0 | none stated |
| body-centered tetragonal (I4/mmm) | s003, s012 | Needs DFT | 59.8 meV | not run | Not found | 0 | none stated |
| face-centered cubic (Fm-3m) | s005, s011 | Needs DFT | 100 meV | not run | Known | 2 | 93, 389, 2870 |
| hexagonal close-packed (P6_3/mmc) | s017 | Needs DFT | 116.1 meV | not run | Known | 1 | 93, 389 |
| P6_3/m (P6_3/m) | s008 | Needs DFT | 117 meV | not run | Not found | 0 | none stated |
| P4_2/mmc (P4_2/mmc) | s002 | Needs DFT | 121.4 meV | not run | Not found | 0 | none stated |
| P6_322 (P6_322) | s018 | Needs DFT | 182.2 meV | not run | Not found | 0 | none stated |

## Most relevant papers per phase

**beta-tin (I4_1/amd)**
- [Phase transformation in Si from semiconducting diamond to metallic beta-Sn phase in QMC and DFT under hydrostatic and anisotropic stress](https://arxiv.org/abs/1006.3253) (2010)
  > Phase transformation in Si from semiconducting diamond to metallic beta-Sn phase in QMC and DFT under hydrostatic and anisotropic stress
- [Pressure-induced diamond to beta-tin transition in bulk silicon: a near-exact quantum Monte Carlo study](https://arxiv.org/abs/0908.4477) (2009)
  > Pressure-induced diamond to beta-tin transition in bulk silicon: a near-exact quantum Monte Carlo study
- [Kinetic origin of divergent decompression pathways in silicon and germanium.](https://pubmed.ncbi.nlm.nih.gov/23679617/) (2013)
  > Silicon and germanium transform from diamond to β-tin structure under compression, but upon decompression they turn into metastable BC8 Si and ST12 Ge phases, respectively, instead of returning to the lowest-enthalpy diamond structure.

**simple cubic (Pm-3m)**
- [Anharmonic and Anomalous Trends in the High-Pressure Phase Diagram of Silicon.](https://pubmed.ncbi.nlm.nih.gov/30978067/) (2019)
  > [added on review] predicts simple cubic silicon above 3.89 TPa (fcc -> bcc -> sc); the sentence does not repeat 'silicon' but the paper is about silicon

**simple hexagonal (P6/mmm)**
- [Predicting crystal structures: the Parrinello-Rahman method revisited.](https://pubmed.ncbi.nlm.nih.gov/12633242/) (2003)
  > We illustrate the power of the method by studying the pressure-induced diamond to simple hexagonal phase transition in a model of silicon.
- [Ab initio study of the beta$-tin->Imma->sh phase transitions in silicon and germanium](https://arxiv.org/abs/cond-mat/0308314) (2003)
  > Ab initio study of the beta$-tin->Imma->sh phase transitions in silicon and germanium
- [Structural Phase Trasformations via Ab-Initio Molecular Dynamics](https://arxiv.org/abs/cond-mat/9312014) (1993)
  > The validity of the method is demonstrated by simulating the metal-insulator transition in Silicon (from diamond structure to simple hexagonal structure) under high pressure.

**face-centered cubic (Fm-3m)**
- [Anharmonic and Anomalous Trends in the High-Pressure Phase Diagram of Silicon.](https://pubmed.ncbi.nlm.nih.gov/30978067/) (2019)
  > [added on review] predicts fcc silicon transforming to bcc at 2.87 TPa; the sentence does not repeat 'silicon' but the paper is about silicon
- [X-Ray Diffraction of Ramp-Compressed Silicon to 390 GPa.](https://pubmed.ncbi.nlm.nih.gov/36867795/) (2023)
  > Angle-dispersive x-ray scattering reveals that Si assumes an hexagonal close-packed (hcp) structure between 40 and 93 GPa and, at higher pressure, a face-centered cubic structure that persists to at least 389 GPa, the highest pressure for which the crystal structure of Si has been investigated.

**hexagonal close-packed (P6_3/mmc)**
- [X-Ray Diffraction of Ramp-Compressed Silicon to 390 GPa.](https://pubmed.ncbi.nlm.nih.gov/36867795/) (2023)
  > Angle-dispersive x-ray scattering reveals that Si assumes an hexagonal close-packed (hcp) structure between 40 and 93 GPa and, at higher pressure, a face-centered cubic structure that persists to at least 389 GPa, the highest pressure for which the crystal structure of Si has been investigated.

## Excluded after review

| Phase | Paper | Reason |
|---|---|---|
| Cmcm | [Mixed Coordination Silica at Megabar Pressure.](https://pubmed.ncbi.nlm.nih.gov/33543966/) | about Cmcm SiO3, a silicon oxide, not elemental silicon |
| body-centered tetragonal | [Kinetic origin of divergent decompression pathways in silicon and germanium.](https://pubmed.ncbi.nlm.nih.gov/23679617/) | its body-centred tetragonal phase has I4_1/a symmetry, not I4/mmm |
| face-centered cubic | [Order-Disorder in Fe-Si Alloys: Implications for Seismic Anisotropy and Thermal ](https://arxiv.org/abs/2511.22899) | about fcc Fe-Si alloys, not elemental silicon |
| hexagonal close-packed | [Order-Disorder in Fe-Si Alloys: Implications for Seismic Anisotropy and Thermal ](https://arxiv.org/abs/2511.22899) | about hcp Fe-Si alloys, not elemental silicon |
| hexagonal close-packed | [Beyond chemical accuracy: The pseudopotential approximation in diffusion Monte C](https://arxiv.org/abs/1501.03850) | the hcp phase is beryllium; silicon is only the motivation |
