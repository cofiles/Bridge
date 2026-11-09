from pathlib import Path
from PIL import Image, ImageDraw

size = 1024
im = Image.new("RGBA", (size,size), (0,0,0,0))
draw = ImageDraw.Draw(im)
draw.rounded_rectangle((32,32,992,992), radius=220, fill=(247,248,243,255))
# Same bridge geometry as the interface, rendered at application-icon resolution.
scale = size / 42
offset = 5 * scale
def points(coords):
    return [(round(x*scale+offset),round(y*scale+offset)) for x,y in coords]
def stroke(coords):
    xy = points(coords)
    width = round(2*scale)
    draw.line(xy,fill="black",width=width,joint="curve")
    for x,y in (xy[0],xy[-1]):
        r=width/2
        draw.ellipse((x-r,y-r,x+r,y+r),fill="black")
stroke([(3,24),(3,17),(6,16.5),(9,15),(12,11),(16,5),(20,11),(23,15),(26,16.5),(29,17),(29,24)])
for coords in [[(3,20),(29,20)],[(10,15),(10,20)],[(16,5),(16,20)],[(22,15),(22,20)]]:
    stroke(coords)
target=Path("assets")
im.save(target/"bridge-icon.png")
im.save(target/"bridge.ico",sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
im.save(target/"bridge.icns")
