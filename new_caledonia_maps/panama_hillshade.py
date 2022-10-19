import glob
import subprocess
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


def docker_run(command: str) -> int:
    return subprocess.call(
        'docker run --rm -it '
        '-v `pwd`:/root/mydata/ '
        '-w /root/mydata/ '
        'new-caledonia-maps-potrace '
        + command,
        shell=True,
        cwd=Path(__file__).parent.parent.as_posix()
    )


root_path = Path(__file__).parent.parent
full_tif_filename = 'data/ne_10m_shaded_relief/SR_HR.tif'
panama_tif_filename = 'data/panama_shaded_relief.tif'
panama_pnm_filename = 'data/panama_shaded_relief.pnm'
panama_svg_light_filename_match = 'data/panama_shaded_relief_light_*.svg'
panama_svg_light_filename = 'data/panama_shaded_relief_light_%.2f.svg'
panama_svg_dark_filename_match = 'data/panama_shaded_relief_dark_*.svg'
panama_svg_dark_filename = 'data/panama_shaded_relief_dark_%.2f.svg'
full_file_path = root_path.joinpath(full_tif_filename)
panama_tif_path = root_path.joinpath(panama_tif_filename)
panama_pnm_path = root_path.joinpath(panama_pnm_filename)

if not panama_tif_path.exists():
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

    transform_geotiff_to_crs_within_canvas(
        full_file_path,
        canvas_rect,
        builder,
        panama_tif_path
    )

if not panama_pnm_path.exists():
    docker_run(
        'tifftopnm %s > %s' % (panama_tif_filename, panama_pnm_filename)
    )

threshold_midpoint = 206 / 255

for threshold_delta in [0.05, 0.10, 0.15]:
    threshold = threshold_midpoint + threshold_delta
    docker_run(
        'potrace %s -o %s -b svg -k %f -i' % (
            panama_pnm_filename,
            panama_svg_light_filename % threshold,
            threshold
        )
    )

for threshold_delta in [0.05, 0.10, 0.15, 0.25, 0.40]:
    threshold = threshold_midpoint - threshold_delta
    docker_run(
        'potrace %s -o %s -b svg -k %f' % (
            panama_pnm_filename,
            panama_svg_dark_filename % threshold,
            threshold
        )
    )

for path in glob.glob(panama_svg_light_filename_match, root_dir=root_path):
    docker_run(
        'sed -i -e \'s/fill="#000000"/fill="#FFF" opacity="0.1"/\' %s' % path
    )

for path in glob.glob(panama_svg_dark_filename_match, root_dir=root_path):
    docker_run(
        'sed -i -e \'s/fill="#000000"/fill="#000" opacity="0.1"/\' %s' % path
    )
