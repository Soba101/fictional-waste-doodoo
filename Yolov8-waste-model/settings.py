from pathlib import Path
import sys

file_path = Path(__file__).resolve()
root_path = file_path.parent
if root_path not in sys.path:
    sys.path.append(str(root_path))
ROOT = root_path.relative_to(Path.cwd())

# ML Model config
MODEL_DIR = ROOT / 'pi5_optimized' / 'waste_detection' / 'weights'
DETECTION_MODEL = MODEL_DIR / 'best.pt'
# Webcam
WEBCAM_PATH = 0

# Updated class lists to match data.yaml
RECYCLABLE = [
    'Aluminium foil', 'Clear plastic bottle', 'Corrugated carton', 'Drink can', 'Drink carton',
    'Egg carton', 'Food Can', 'Glass bottle', 'Glass jar', 'Magazine paper', 'Metal bottle cap',
    'Metal lid', 'Normal paper', 'Other plastic bottle', 'Other plastic container',
    'Paper bag', 'Paper cup', 'Pizza box', 'Plastic bottle cap', 'Plastic lid', 'Plastic straw',
    'Plastic utensils', 'Pop tab', 'Scrap metal', 'Toilet tube', 'Tupperware', 'Wrapping paper'
]

HAZARDOUS = [
    'Battery', 'Aerosol', 'Broken glass', 'Cigarette', 'Glass cup', 'Plastic glooves',
    'Shoe', 'Single-use carrier bag'
]

# Dynamically assign remaining to NON_RECYCLABLE
ALL_CLASSES = [
    'Aerosol', 'Aluminium blister pack', 'Aluminium foil', 'Battery', 'Broken glass',
    'Carded blister pack', 'Cigarette', 'Clear plastic bottle', 'Corrugated carton', 'Crisp packet',
    'Disposable food container', 'Disposable plastic cup', 'Drink can', 'Drink carton', 'Egg carton',
    'Foam cup', 'Foam food container', 'Food Can', 'Food waste', 'Garbage bag', 'Glass bottle',
    'Glass cup', 'Glass jar', 'Magazine paper', 'Meal carton', 'Metal bottle cap', 'Metal lid',
    'Normal paper', 'Other carton', 'Other plastic bottle', 'Other plastic container',
    'Other plastic cup', 'Other plastic wrapper', 'Other plastic', 'Paper bag', 'Paper cup',
    'Paper straw', 'Pizza box', 'Plastic bottle cap', 'Plastic film', 'Plastic glooves',
    'Plastic lid', 'Plastic straw', 'Plastic utensils', 'Polypropylene bag', 'Pop tab',
    'Rope - strings', 'Scrap metal', 'Shoe', 'Single-use carrier bag', 'Six pack rings',
    'Spread tub', 'Squeezable tube', 'Styrofoam piece', 'Tissues', 'Toilet tube',
    'Tupperware', 'Unlabeled litter', 'Wrapping paper'
]

NON_RECYCLABLE = sorted(list(set(ALL_CLASSES) - set(RECYCLABLE) - set(HAZARDOUS)))