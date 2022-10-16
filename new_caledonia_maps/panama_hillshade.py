from pathlib import Path

from map_engraver.canvas.canvas_bbox import CanvasBbox
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit as Cu
from map_engraver.data.canvas_geometry.rect import rect
from map_engraver.data.geo.geo_coordinate import GeoCoordinate
from map_engraver.data.geo_canvas_ops.geo_canvas_transformers_builder import \
    GeoCanvasTransformersBuilder
from map_engraver.data.geotiff.canvas_transform import \
    transform_geotiff_to_crs_within_canvas
from pyproj import CRS

canvas_width = Cu.from_px(720)
canvas_height = Cu.from_px(500)
canvas_bbox = CanvasBbox(
    CanvasCoordinate.origin(),
    canvas_width,
    canvas_height
)
canvas_rect = rect(canvas_bbox)
crs = CRS.from_proj4('+proj=utm +zone=17')
wgs84_crs = CRS.from_epsg(4326)
builder = GeoCanvasTransformersBuilder()
builder.set_scale_and_origin_from_coordinates_and_crs(
    crs,
    GeoCoordinate(9, -83.5, wgs84_crs),
    GeoCoordinate(9, -76.5, wgs84_crs),
    CanvasCoordinate.from_px(0, canvas_height.px / 2),
    CanvasCoordinate.from_px(canvas_width.px, canvas_height.px / 2)
)
builder.set_data_crs(wgs84_crs)

data_path = Path(__file__).parent.parent.joinpath('data')
input_file = data_path.joinpath('ne_10m_shaded_relief/SR_HR.tif')
output_file = data_path.joinpath('panama_shaded_relief.tif')

transform_geotiff_to_crs_within_canvas(
    input_file,
    canvas_rect,
    builder,
    output_file
)

