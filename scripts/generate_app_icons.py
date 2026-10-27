"""Package the existing logo as standard and maskable application icons."""
from pathlib import Path
from PIL import Image
root = Path(__file__).resolve().parents[1]
target = root/'static/pwa/icons'
target.mkdir(parents=True, exist_ok=True)
logo = Image.open(root/'static/logo-que-hay-live.png').convert('RGBA')
for name, size in [('icon-192.png',192),('icon-512.png',512),('maskable-512.png',512)]:
    icon=Image.new('RGB',(size,size),'#080f19')
    mark=logo.copy();mark.thumbnail((int(size*.55),int(size*.55)),Image.Resampling.LANCZOS)
    icon.paste(mark,((size-mark.width)//2,(size-mark.height)//2),mark)
    icon.save(target/name,optimize=True)
