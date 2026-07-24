"""Keyword knowledge base for classification.

Three vocabularies drive the relevance decision:

* ``PRIMARY_TERMS`` — photocatalysis-specific vocabulary. A paper must show
  strong evidence here to be indexed at all: this is the project's core rule,
  *photocatalysis as the primary subject*.
* ``SUPPORT_TERMS`` — materials, reactions, characterization, computational
  and data-driven methods that refine the score and assign categories.
* ``NEGATIVE_TERMS`` — signals the paper belongs to a neighbouring field
  (photovoltaics, LEDs, photodynamic therapy...).  ``penalty`` points.

Weights: 4 = unambiguous ("photocatal…", "photoredox"), 3 = strong,
2 = supportive, 1 = weak/generic.  Tags become the visible chips on paper
cards; categories group papers for browsing.
"""

from __future__ import annotations

from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Primary photocatalysis terms — required evidence
# ---------------------------------------------------------------------------
PRIMARY_TERMS: Dict[str, Tuple[int, str, str]] = {
    # phrase: (weight, tag, category)
    "photocatal": (4, "Photocatalysis", "General Photocatalysis"),
    "photo-cataly": (4, "Photocatalysis", "General Photocatalysis"),
    "photoredox": (4, "Photoredox", "Photoredox & Organic Synthesis"),
    "photoelectrochemical": (4, "Photoelectrochemistry", "Photoelectrochemistry"),
    "photoelectrocataly": (4, "Photoelectrochemistry", "Photoelectrochemistry"),
    "photoanode": (4, "Photoanodes", "Photoelectrochemistry"),
    "photocathode": (4, "Photocathodes", "Photoelectrochemistry"),
    "photodegradation": (4, "Photodegradation", "Pollutant Degradation"),
    "photo-degradation": (4, "Photodegradation", "Pollutant Degradation"),
    "photooxidation": (3, "Photooxidation", "Pollutant Degradation"),
    "photoreduction": (4, "Photoreduction", "CO2 Reduction"),
    "artificial photosynthesis": (4, "Artificial Photosynthesis", "Solar Fuels"),
    "solar fuel": (4, "Solar Fuels", "Solar Fuels"),
    "solar-to-hydrogen": (4, "Solar Hydrogen", "Water Splitting"),
    "solar hydrogen": (4, "Solar Hydrogen", "Water Splitting"),
    "solar water splitting": (4, "Water Splitting", "Water Splitting"),
    "photocatalytic water splitting": (4, "Water Splitting", "Water Splitting"),
    "z-scheme": (4, "Z-Scheme", "Z-Scheme & Heterojunctions"),
    "s-scheme": (4, "S-Scheme", "Z-Scheme & Heterojunctions"),
    "photofixation": (4, "N2 Photofixation", "Nitrogen Fixation"),
    "light-driven cataly": (4, "Light-Driven Catalysis", "General Photocatalysis"),
    "visible-light-driven": (4, "Visible Light", "General Photocatalysis"),
    "visible light driven": (4, "Visible Light", "General Photocatalysis"),
    "visible-light photocataly": (4, "Visible Light", "General Photocatalysis"),
    "sunlight-driven": (3, "Sunlight-Driven", "General Photocatalysis"),
    "light-mediated cataly": (3, "Light-Driven Catalysis", "Photoredox & Organic Synthesis"),
    "photoinduced electron transfer": (3, "Photoinduced ET", "Mechanism & Charge Dynamics"),
    "plasmonic photocataly": (4, "Plasmonic", "Plasmonic Photocatalysis"),
    "photothermal cataly": (3, "Photothermal Catalysis", "General Photocatalysis"),
}

# ---------------------------------------------------------------------------
# Support terms — materials, reactions, methods, characterization
# ---------------------------------------------------------------------------
SUPPORT_TERMS: Dict[str, Tuple[int, str, str]] = {
    # target reactions
    "water splitting": (4, "Water Splitting", "Water Splitting"),
    "hydrogen evolution": (4, "Hydrogen Evolution", "Hydrogen Evolution"),
    "h2 evolution": (4, "Hydrogen Evolution", "Hydrogen Evolution"),
    "hydrogen production": (3, "Hydrogen Production", "Hydrogen Evolution"),
    "oxygen evolution": (3, "Oxygen Evolution", "Water Splitting"),
    "co2 reduction": (4, "CO2 Reduction", "CO2 Reduction"),
    "co2 conversion": (3, "CO2 Reduction", "CO2 Reduction"),
    "carbon dioxide reduction": (4, "CO2 Reduction", "CO2 Reduction"),
    "nitrogen fixation": (4, "Nitrogen Fixation", "Nitrogen Fixation"),
    "n2 fixation": (4, "Nitrogen Fixation", "Nitrogen Fixation"),
    "ammonia synthesis": (3, "Ammonia Synthesis", "Nitrogen Fixation"),
    "dye degradation": (4, "Dye Degradation", "Pollutant Degradation"),
    "methylene blue": (3, "Dye Degradation", "Pollutant Degradation"),
    "rhodamine b": (3, "Dye Degradation", "Pollutant Degradation"),
    "pollutant": (3, "Pollutants", "Pollutant Degradation"),
    "wastewater": (2, "Wastewater", "Pollutant Degradation"),
    "antibiotic degradation": (4, "Antibiotic Degradation", "Pollutant Degradation"),
    "tetracycline": (3, "Antibiotic Degradation", "Pollutant Degradation"),
    "water purification": (3, "Water Purification", "Pollutant Degradation"),
    "air purification": (3, "Air Purification", "Pollutant Degradation"),
    "organic synthesis": (3, "Organic Synthesis", "Photoredox & Organic Synthesis"),
    "c-h functionalization": (3, "C-H Functionalization", "Photoredox & Organic Synthesis"),
    "cross-coupling": (3, "Cross-Coupling", "Photoredox & Organic Synthesis"),
    "radical": (2, "Radical Chemistry", "Photoredox & Organic Synthesis"),
    "selective oxidation": (3, "Selective Oxidation", "Photoredox & Organic Synthesis"),
    "h2o2 production": (4, "H2O2 Production", "Solar Fuels"),
    "hydrogen peroxide production": (4, "H2O2 Production", "Solar Fuels"),
    "methane conversion": (3, "Methane Conversion", "Solar Fuels"),
    # materials
    "tio2": (3, "TiO2", "Semiconductor Materials"),
    "titanium dioxide": (3, "TiO2", "Semiconductor Materials"),
    "titania": (3, "TiO2", "Semiconductor Materials"),
    "anatase": (3, "TiO2", "Semiconductor Materials"),
    "rutile": (2, "TiO2", "Semiconductor Materials"),
    "g-c3n4": (4, "g-C3N4", "g-C3N4 & Carbon Materials"),
    "graphitic carbon nitride": (4, "g-C3N4", "g-C3N4 & Carbon Materials"),
    "carbon nitride": (3, "Carbon Nitride", "g-C3N4 & Carbon Materials"),
    "graphene": (2, "Graphene", "g-C3N4 & Carbon Materials"),
    "carbon dots": (3, "Carbon Dots", "g-C3N4 & Carbon Materials"),
    "zno": (2, "ZnO", "Semiconductor Materials"),
    "zinc oxide": (2, "ZnO", "Semiconductor Materials"),
    "cds": (2, "CdS", "Semiconductor Materials"),
    "cadmium sulfide": (2, "CdS", "Semiconductor Materials"),
    "bivo4": (3, "BiVO4", "Semiconductor Materials"),
    "bismuth vanadate": (3, "BiVO4", "Semiconductor Materials"),
    "wo3": (2, "WO3", "Semiconductor Materials"),
    "znin2s4": (3, "ZnIn2S4", "Semiconductor Materials"),
    "srtio3": (3, "SrTiO3", "Semiconductor Materials"),
    "strontium titanate": (3, "SrTiO3", "Semiconductor Materials"),
    "semiconductor": (2, "Semiconductors", "Semiconductor Materials"),
    "quantum dot": (2, "Quantum Dots", "Semiconductor Materials"),
    "perovskite": (2, "Perovskites", "Perovskites"),
    "halide perovskite": (3, "Halide Perovskites", "Perovskites"),
    "metal-organic framework": (3, "MOFs", "MOFs & COFs"),
    "metal organic framework": (3, "MOFs", "MOFs & COFs"),
    "covalent organic framework": (3, "COFs", "MOFs & COFs"),
    "heterojunction": (3, "Heterojunctions", "Z-Scheme & Heterojunctions"),
    "heterostructure": (2, "Heterostructures", "Z-Scheme & Heterojunctions"),
    "cocatalyst": (4, "Co-catalysts", "Co-catalysts & Surface"),
    "co-catalyst": (4, "Co-catalysts", "Co-catalysts & Surface"),
    "single-atom": (3, "Single-Atom Catalysts", "Co-catalysts & Surface"),
    "oxygen vacanc": (3, "Oxygen Vacancies", "Co-catalysts & Surface"),
    "defect engineering": (3, "Defect Engineering", "Co-catalysts & Surface"),
    "doping": (2, "Doping", "Co-catalysts & Surface"),
    "plasmonic": (2, "Plasmonics", "Plasmonic Photocatalysis"),
    "localized surface plasmon": (3, "LSPR", "Plasmonic Photocatalysis"),
    # mechanism / characterization
    "charge separation": (3, "Charge Separation", "Mechanism & Charge Dynamics"),
    "charge transfer": (2, "Charge Transfer", "Mechanism & Charge Dynamics"),
    "charge carrier": (3, "Charge Carriers", "Mechanism & Charge Dynamics"),
    "electron-hole": (3, "Electron-Hole Pairs", "Mechanism & Charge Dynamics"),
    "photogenerated": (3, "Photogenerated Carriers", "Mechanism & Charge Dynamics"),
    "photoexcited": (2, "Photoexcitation", "Mechanism & Charge Dynamics"),
    "band gap": (2, "Band Gap", "Mechanism & Charge Dynamics"),
    "band structure": (2, "Band Structure", "Mechanism & Charge Dynamics"),
    "band alignment": (3, "Band Alignment", "Mechanism & Charge Dynamics"),
    "reactive oxygen species": (3, "ROS", "Mechanism & Charge Dynamics"),
    "singlet oxygen": (3, "Singlet Oxygen", "Mechanism & Charge Dynamics"),
    "superoxide": (2, "ROS", "Mechanism & Charge Dynamics"),
    "hydroxyl radical": (3, "Hydroxyl Radicals", "Mechanism & Charge Dynamics"),
    "transient absorption": (3, "Transient Absorption", "Mechanism & Charge Dynamics"),
    "photoluminescence": (2, "Photoluminescence", "Mechanism & Charge Dynamics"),
    "quantum yield": (2, "Quantum Yield", "Mechanism & Charge Dynamics"),
    "apparent quantum efficiency": (3, "Quantum Efficiency", "Mechanism & Charge Dynamics"),
    "visible light": (2, "Visible Light", "General Photocatalysis"),
    "solar light": (2, "Solar Light", "General Photocatalysis"),
    "light irradiation": (2, "Light Irradiation", "General Photocatalysis"),
    "simulated sunlight": (2, "Simulated Sunlight", "General Photocatalysis"),
    # computational & data-driven
    "dft": (2, "DFT", "Computational & DFT"),
    "density functional": (2, "DFT", "Computational & DFT"),
    "first-principles": (2, "First-Principles", "Computational & DFT"),
    "ab initio": (2, "Ab Initio", "Computational & DFT"),
    "molecular dynamics": (2, "Molecular Dynamics", "Computational & DFT"),
    "excited state": (2, "Excited States", "Computational & DFT"),
    "machine learning": (3, "Machine Learning", "Machine Learning for Photocatalysis"),
    "deep learning": (3, "Deep Learning", "Machine Learning for Photocatalysis"),
    "neural network": (2, "Neural Network", "Machine Learning for Photocatalysis"),
    "data-driven": (2, "Data-Driven", "Machine Learning for Photocatalysis"),
    "high-throughput screening": (3, "High-Throughput", "Machine Learning for Photocatalysis"),
    "bayesian optimization": (3, "Bayesian Optimization", "Machine Learning for Photocatalysis"),
    # engineering
    "photoreactor": (4, "Photoreactors", "Reactor Engineering & Scale-up"),
    "reactor design": (3, "Reactor Design", "Reactor Engineering & Scale-up"),
    "scale-up": (3, "Scale-up", "Reactor Engineering & Scale-up"),
    "flow chemistry": (3, "Flow Chemistry", "Reactor Engineering & Scale-up"),
    "immobilized": (2, "Immobilization", "Reactor Engineering & Scale-up"),
    "recyclability": (2, "Recyclability", "Reactor Engineering & Scale-up"),
}

# ---------------------------------------------------------------------------
# Negative signals — neighbouring fields that are NOT photocatalysis
# ---------------------------------------------------------------------------
NEGATIVE_TERMS: Dict[str, int] = {
    "solar cell": 10,
    "photovoltaic": 10,
    "dye-sensitized solar": 10,
    "perovskite solar cell": 12,
    "power conversion efficiency": 8,
    "light-emitting diode": 12,
    "light-emitting": 8,
    "oled": 12,
    "electroluminescen": 10,
    "photodetector": 10,
    "phototransistor": 12,
    "photodynamic therapy": 12,
    "photothermal therapy": 12,
    "bioimaging": 10,
    "fluorescence imaging": 8,
    "drug delivery": 8,
    "photolithography": 10,
    "optical fiber": 10,
    "display technology": 12,
}

# Journal-name fragments indicating a relevant venue (score bonus).
CHEM_VENUE_HINTS = (
    "photo", "catal", "sol", "energy", "environ", "chem", "mater",
    "surf", "nano", "carbon", "water",
)
