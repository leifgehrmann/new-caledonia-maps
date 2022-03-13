from pyproj import CRS, Transformer

ortho_transformer = Transformer.from_proj(
    CRS.from_epsg(4326),
    CRS.from_proj4('+proj=ortho +lat_0=10')
)

print(ortho_transformer.transform(0, 0))
print(ortho_transformer.transform(0, 90))
print(ortho_transformer.transform(0, -90))
print(ortho_transformer.transform(90, 0))
print(ortho_transformer.transform(-90, 0))
