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


def docker_run(command: str):
    result = subprocess.call(
        'docker run '
        '--rm '
        '-t '
        '-v `pwd`:/root/mydata/ '
        '-w /root/mydata/ '
        'new-caledonia-maps-potrace '
        '/bin/sh -c '
        + "'" + command + "'",
        shell=True,
        cwd=Path(__file__).parent.parent.as_posix()
    )
    if result != 0:
        raise Exception('Failed to execute docker command')


world_tif_filename = 'data/ne_10m_shaded_relief/SR_HR.tif'
panama_filepath = 'data/panama_shaded_relief/'
panama_tif_filename = panama_filepath + 'projected.tif'
panama_pnm_filename = panama_filepath + 'projected.pnm'
panama_svg_filename_match = panama_filepath + '*.svg'
panama_svg_white_filename = panama_filepath + '%s_white_%.2f.svg'
panama_svg_black_filename = panama_filepath + '%s_black_%.2f.svg'
# In the world tif, flat slopes are this shade of gray.
threshold_midpoint = 206 / 255

root_path = Path(__file__).parent.parent
world_tif_path = root_path.joinpath(world_tif_filename)
panama_output_path = root_path.joinpath(panama_filepath)
panama_tif_path = root_path.joinpath(panama_tif_filename)
panama_pnm_path = root_path.joinpath(panama_pnm_filename)

# Generate the output directory if it doesn't exist.
panama_output_path.mkdir(parents=True, exist_ok=True)

# Reproject the world map hill-shade map from Natural Earth to a map of Panama.
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
        world_tif_path,
        canvas_rect,
        builder,
        panama_tif_path
    )

# Convert the TIFF to PNM.
if not panama_pnm_path.exists():
    docker_run(
        'tifftopnm %s > %s' % (panama_tif_filename, panama_pnm_filename)
    )

# Generate the **black** specs of the TIFF as an SVG at different brightness
# thresholds. We duplicate them, so we can have dark and light themes later.
for threshold_delta in [0.05, 0.10, 0.15]:
    threshold = threshold_midpoint + threshold_delta
    docker_run(
        'potrace %s -o %s -b svg -k %f -i' % (
            panama_pnm_filename,
            panama_svg_white_filename % ('dark', threshold),
            threshold
        )
    )
    docker_run(
        'cp %s %s' % (
                panama_svg_white_filename % ('dark', threshold),
                panama_svg_white_filename % ('light', threshold)
        )
    )

# Generate the **white** specs of the TIFF as an SVG at different brightness
# thresholds. We duplicate them, so we can have dark and light themes later.
for threshold_delta in [0.05, 0.10, 0.15, 0.25, 0.40]:
    threshold = threshold_midpoint - threshold_delta
    docker_run(
        'potrace %s -o %s -b svg -k %f' % (
            panama_pnm_filename,
            panama_svg_black_filename % ('dark', threshold),
            threshold
        )
    )
    docker_run(
        'cp %s %s' % (
            panama_svg_black_filename % ('dark', threshold),
            panama_svg_black_filename % ('light', threshold)
        )
    )

# Update the colors of the SVGs according to the theme and colors.
for path in glob.glob(panama_svg_filename_match, root_dir=root_path):
    color = None
    opacity = None
    if 'dark' in path:
        if 'black' in path:
            color = '#000'
            opacity = 0.1
        else:
            color = '#FFF'
            opacity = 0.1
    else:
        if 'black' in path:
            color = '#000'
            opacity = 0.1
        else:
            color = '#FFF'
            opacity = 0.2

    docker_run(
        'sed -i -e "s/fill=\\"#000000\\"/fill=\\"%s\\" opacity=\\"%f\\"/" %s' % (
            color, opacity, path
        )
    )
    docker_run(
        'sed -i -e "s/pt\\"/px\\"/g" %s' % path
    )
