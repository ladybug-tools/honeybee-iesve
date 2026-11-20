import math
import re
import uuid

from ladybug_geometry.geometry3d import Vector3D, Point3D, Plane, Face3D, Mesh3D
from ladybug_geometry.geometry2d import Point2D, Polygon2D
from ladybug_geometry.intersection2d import closest_point2d_on_line2d
from honeybee.model import Model, Shade, Room, Face, Aperture, Door, \
    AirBoundary, ShadeMesh
from honeybee.boundarycondition import Outdoors, Ground
from honeybee.typing import clean_string, clean_and_id_ep_string

from .config import IESVE_TOLERANCE, OPENING_OFFSET, IMPORT_IGNORE
from .types import GEM_TYPES


def _gem_object_type(info, keyword='IES'):
    """Get GEM object type from info.

    Args:
        info: Text string for the file contents to search.
        keyword: Text for the keyword to be used. (Default: IES).
    """
    type_ = int(re.findall(r'^TYPE\n(\d*)', info, re.MULTILINE)[0])
    subtype = int(re.findall(r'^SUBTYPE\n(\d*)', info, re.MULTILINE)[0])
    category = int(re.findall(r'^CATEGORY\n(\d*)', info, re.MULTILINE)[0])
    return GEM_TYPES.from_info(
        category=category, type_=type_, subtype=subtype, keyword=keyword
    )


def _add_user_data(hb_obj, user_data=None):
    """Add user data to any Honeybee object (including Face and Shade)."""
    if not user_data:
        return
    if hb_obj.user_data:  # the dictionary exists
        hb_obj.user_data.update(user_data)
    else:
        hb_obj.user_data = user_data


def _get_id(display_name):
    """Extract an id from display name. Will be None if no ID is found.

    Note that, in IESVE version 2023, the ID is included in the GEM file as
    inside [] at the end of the name.
    """
    id_ = re.findall(r'\s\[(.*)\]$', display_name, re.MULTILINE)
    if id_:
        return id_[0]
    else:
        return None


def _update_name(hb_obj, display_name, count=None):
    """Add display_name, identifier, and __group_id__ in user_data to any Honeybee object."""
    if not isinstance(hb_obj, Room):
        identifier = clean_string(display_name) if count \
            else clean_string('{}-{}'.format(display_name, count))
        _add_user_data(hb_obj=hb_obj, user_data={'__group_id__': identifier})

    id_ = _get_id(display_name)
    if id_:
        hb_obj.identifier = '{}-{}'.format(id_, count) if count else id_
        hb_obj.display_name = display_name.replace(' [{}]'.format(id_), '')
    else:
        hb_obj.display_name = display_name


def _create_shade(boundary, holes=None, is_detached=True, user_data=None):
    """Create a Honeybee Shade object.

    Args:
        boundary: A list of Point3D for the boundary of the Shade.
        holes: A list of lists of Point3D for the holes in the Shade geometry.
        is_detached: Boolean for whether the Shade is detached.
        user_data: Optional dictionary of user_data for the Shade
    """
    geometry = Face3D(boundary, holes=holes)
    shade = Shade(str(uuid.uuid4()), geometry=geometry, is_detached=is_detached)
    _add_user_data(shade, user_data)
    return shade


def _opening_from_ies(parent_geo, content):
    """Translate an opening from GEM format.

    Args:
        parent_geo: Face3D for the geometry of the parent object.
        content: A list of GEM strings containing child openings. Each item in the
            list is a line of the GEM file.

    Returns:
        A tuple with four elements.

        -   opening_type: An integer for the type of opening. 0 is Aperture, 1 is
            Door, 2 is AirBoundary hole.

        -   opening_vertices: A list of Point3D for the opening geometry.

        -   opening_vertices_2d: A list of Point2D for the opening geometry.

        -   opening_area: A number for the area of the opening.
    """
    if parent_geo.max.z - parent_geo.min.z < IESVE_TOLERANCE:  # perfectly horizontal in IESVE
        origin = parent_geo.upper_right_corner
    else:
        origin = parent_geo.lower_left_corner

    # This is how the next line looks
    # 5 2
    ver_count, opening_type = [int(float(v)) for v in next(content).split()]

    # calculate the vertices from X, Y values
    # 0.000000     0.906100
    # 0.000000     0.000000
    # 10.373100     0.000000
    tolerance = OPENING_OFFSET
    boundary_2d = parent_geo.boundary_polygon2d
    offset_boundary_2d = boundary_2d.offset(tolerance)
    origin_2d = parent_geo.plane.xyz_to_xy(origin)

    # create vertices in 2D
    opening_vertices = []
    opening_vertices_2d = []
    for _ in range(ver_count):
        cnt = next(content).split()
        if len(cnt) == 2:
            x_m, y_m = [float(v) for v in cnt]
        elif len(cnt) == 3:
            # Translucent shade
            x_m, y_m, opacity = [float(v) for v in cnt]
        vertex_2d = Point2D(origin_2d.x - x_m, origin_2d.y - y_m)
        vertex = parent_geo.plane.xy_to_xyz(vertex_2d)
        on_segments = []
        for segment in boundary_2d.segments:
            close_pt = closest_point2d_on_line2d(vertex_2d, segment)
            if vertex_2d.distance_to_point(close_pt) <= tolerance:
                on_segments.append((segment, close_pt))

        if not on_segments or opening_type == 2:
            # for AirBoundary holes don't move the vertex
            pass
        elif len(on_segments) == 1:
            # it is an edge
            vector = on_segments[0][0].v
            v1 = vector.rotate(math.pi / 2).normalize() * tolerance
            v2 = vector.rotate(-math.pi / 2).normalize() * tolerance
            v = vertex_2d.move(v1)
            if boundary_2d.is_point_inside_check(v):
                vertex_2d = v
            else:
                v = vertex_2d.move(v2)
                if boundary_2d.is_point_inside_check:
                    vertex_2d = v
        elif len(on_segments) == 2:
            # The point is adjacent to a corner. Find the closest point to the offset boundary
            dist_col = []
            for seg in offset_boundary_2d.segments:
                cp = seg.closest_point(vertex_2d)
                dist = cp.distance_to_point(vertex_2d)
                dist_col.append([dist, cp])

            points_sorted = sorted(dist_col, key=lambda x: x[0])
            vertex_2d = points_sorted[0][1]
        else:  # this should not happen!
            print('{} is adjacent to more than 2 edges of the same polygon.'.format(vertex))

        vertex = parent_geo.plane.xy_to_xyz(vertex_2d)
        opening_vertices.append(vertex)
        opening_vertices_2d.append(vertex_2d)

    org_pl = Polygon2D(opening_vertices_2d)
    opening_area = org_pl.area

    return opening_type, opening_vertices, opening_vertices_2d, opening_area


def _create_tree(info, tree_type=1):
    """Create two Honeybee Shades from a GEM Tree string.

    The two shades are each rectangles that define tree along the X and Y world
    axes respectively. The user_data attached to these Shades is formatted such
    that they will be exported back to GEM as a single Tree object.

    Args:
        info: Text string for the file contents of the Tree.
        tree_type: Integer for the type of Tree. This will be stored in the
            Honeybee Shade user_data for export back to GEM.
    """
    values = [float(v) for v in info.strip().split()]
    assert len(values) == 8, 'Length of data for tree is not 8 segments.'
    # calculate tree geometry
    x, y, z, x_scale, y_scale, z_scale, xy_rotation, yz_rotation = values
    x_scale *= 3
    y_scale *= 3
    z_scale *= 8
    base = Point3D(x, y, z)
    # move the base plane for half the x_scale
    x_base = Plane(o=base, n=Vector3D(0, -1, 0), x=Vector3D(1, 0, 0))
    x_base = x_base.move(Vector3D(-x_scale / 2, 0, 0))
    y_base = Plane(o=base, n=Vector3D(1, 0, 0), x=Vector3D(0, 1, 0))
    y_base = y_base.move(Vector3D(0, -y_scale / 2, 0))
    geometries = [
        Face3D.from_rectangle(x_scale, z_scale, x_base),
        Face3D.from_rectangle(y_scale, z_scale, y_base)
    ]
    geos = []
    for geometry in geometries:
        if yz_rotation:
            axis = Vector3D(-1, 0, 0)
            geometry = geometry.rotate(axis, math.radians(yz_rotation), base)
        if xy_rotation:
            geometry = geometry.rotate_xy(math.radians(xy_rotation), base)
        geos.append(geometry)

    tree_0 = _create_shade(
        geos[0].lower_left_counter_clockwise_vertices,
        user_data={
            '__gem_type__': 'tree',
            '__gem_tree_type__': tree_type,
            IMPORT_IGNORE: True
        }
    )

    tree_1 = _create_shade(
        geos[1].lower_left_counter_clockwise_vertices,
        user_data={
            '__gem_type__': 'tree',
            '__gem_tree_type__': tree_type
        }
    )

    return tree_0, tree_1


def _create_pv(info):
    """Create a Honeybee Shade from a GEM PV string.

    The user_data attached to the Shade is formatted such that it will be
    exported back to GEM as a PV object.

    Args:
        info: Text string for the file contents of the PV.
    """
    values = [float(v) for v in info.strip().split()]
    assert len(values) == 7, 'Length of data for PV is not 7 segments.'
    # calculate PV geometry
    x, y, z, width, height, xy_rotation, yz_rotation = values
    base = Point3D(x, y, z)
    base_plane = Plane(o=base)
    geometry = Face3D.from_rectangle(width, -height, base_plane)
    if yz_rotation:
        axis = Vector3D(-1, 0, 0)
        geometry = geometry.rotate(axis, math.radians(yz_rotation), base)
    if xy_rotation:
        geometry = geometry.rotate_xy(math.radians(xy_rotation), base)

    pv = _create_shade(
        geometry.lower_left_counter_clockwise_vertices,
        user_data={'__gem_type__': 'pv'}
    )

    return pv


def _parse_gem_segment(segment, ignore_shade_mesh=False):
    """Parse a segment of a GEM file.

    Args:
        segment: Text for the segment of a GEM file. A segment is defined as a
            unit of the file contents that contains a complete Room, Shade or
            ShadeMesh object.
        ignore_shade_mesh: Boolean for wether the segments containing shade groups
            should be returned as a joined ShadeMesh object. If True, shade
            groups will be returned as a list of Honeybee Shade objects instead
            of a single ShadeMesh.

    Returns:
        Either a Honeybee Room, a Honeybee ShadeMesh, or a list of Honeybee Shades
        derived from the input segment.
    """
    for keyword in ['IES', 'LAN', 'PVP']:
        if keyword in segment:
            info, segments = re.split('\n{} '.format(keyword), segment)
            break
    else:
        raise ValueError(
            'There is a segment with an unsupported type in the input GEM file. '
            'Reach out to us with a copy of the GEM file and the information below:\n'
            '{}'.format(segment)
        )

    gem_type = _gem_object_type(info=info, keyword=keyword)

    # remove empty lines if any
    content = iter(lin for lin in segments.split('\n') if lin.strip())
    display_name = next(content)
    cleaned_display_name = clean_string(display_name)
    identifier = clean_and_id_ep_string(cleaned_display_name)
    if gem_type == GEM_TYPES.PV:
        pv_info = next(content)
        face = _create_pv(pv_info)
        _update_name(face, display_name)
        return [face]
    elif gem_type == GEM_TYPES.Tree:
        tree_type = next(content)
        assert tree_type.startswith('2D Tree'), \
            '{} is not currently supported.'.format(tree_type)
        tree_type = int(tree_type.split()[-1])
        tree_info = next(content)
        faces = _create_tree(tree_info, tree_type=tree_type)
        for count, face in enumerate(faces):
            _update_name(face, display_name, count)
        return faces

    faces = []
    # everything else
    ver_count, face_count = [int(v) for v in next(content).split()]
    vertices = [
        Point3D(*[float(v) for v in next(content).split()])
        for _ in range(ver_count)
    ]

    # create a shade mesh for shades with multiple faces
    if not ignore_shade_mesh and gem_type == GEM_TYPES.ContextBuilding and face_count > 1:
        faces = []
        for _ in range(face_count):
            boundary = tuple(int(i) - 1 for i in next(content).split()[1:])
            opening_count = int(next(content))  # pass the line for the opening count
            if opening_count > 0 or len(boundary) > 4:
                # there is a hole in the shade or the face has more than 4 edges
                # use the old method of using faces instead
                return _parse_gem_segment(segment, True)
            faces.append(boundary)
        mesh_geometry = Mesh3D(vertices=vertices, faces=faces)
        mesh = ShadeMesh(identifier=identifier, geometry=mesh_geometry, is_detached=True)
        _update_name(mesh, display_name)
        return mesh

    # create faces
    for _ in range(face_count):
        apertures = []
        doors = []
        holes = []
        holes_2d = []
        boundary = [vertices[int(i) - 1] for i in next(content).split()[1:]]
        boundary_geometry = Face3D(boundary, enforce_right_hand=False)
        boundary_geometry_polygon2d = boundary_geometry.boundary_polygon2d
        boundary_area = boundary_geometry.area
        holes_area = 0
        opening_count = int(next(content))
        for _ in range(opening_count):
            opening_type, opening_vertices, opening_vertices_2d, opening_area = \
                _opening_from_ies(boundary_geometry, content)
            if opening_type == 0:
                # create an aperture
                aperture_geo = Face3D(opening_vertices)
                aperture = Aperture(str(uuid.uuid4()), aperture_geo)
                apertures.append(aperture)
            elif opening_type == 1:
                # create a door
                door_geo = Face3D(opening_vertices)
                door = Door(str(uuid.uuid4()), door_geo)
                doors.append(door)
            elif opening_type == 2:
                # create a hole
                holes_area += opening_area
                holes.append(opening_vertices)
                holes_2d.append(Polygon2D(opening_vertices_2d))
            else:
                raise ValueError('Unsupported opening type: {}'.format(opening_type))

        if gem_type == GEM_TYPES.Space or gem_type == GEM_TYPES.UnconditionedSpace:
            # A model face
            geometry = Face3D(boundary)
            face = Face(str(uuid.uuid4()), geometry=geometry)
            if apertures or doors:
                # change the boundary condition if it is set to ground
                if isinstance(face.boundary_condition, Ground):
                    print(
                        'Changing boundary condition from Ground to Outdoors for '
                        '{} in {} [{}].'.format(face.display_name, display_name, identifier)
                    )
                    face.boundary_condition = Outdoors()
            face.add_apertures(apertures)
            face.add_doors(doors)
            if holes:
                # add an AirBoundary to cover the hole
                if holes_area >= 0.98 * boundary_area:
                    # the face is mostly created from holes
                    # replace the parent face with an face from type AirBoundary
                    if len(holes) == 1:
                        # the entire face is created from holes
                        face.type = AirBoundary()
                        faces.append(face)
                        continue
                    # there are multiple air boundaries. create an AirBoundary for each.
                    for hole in holes_2d:
                        hole = boundary_geometry_polygon2d.snap_to_polygon(hole, OPENING_OFFSET)
                        # map the hole back to 3D
                        hole = [boundary_geometry.plane.xy_to_xyz(ver) for ver in hole]
                        hole_geo = Face3D(hole)
                        hole_face = Face(
                            str(uuid.uuid4()), geometry=hole_geo, type=AirBoundary()
                        )
                        faces.append(hole_face)
                    continue

                # only part of the face is created from holes.
                # 1. try to snap them to the face
                # 2. separate holes from side air boundaries
                holes_2d_snapped = [
                    boundary_geometry_polygon2d.snap_to_polygon(hole, OPENING_OFFSET)
                    for hole in holes_2d
                ]
                holes_3d_snapped = [
                    Face3D([boundary_geometry.plane.xy_to_xyz(v) for v in hole])
                    for hole in holes_2d_snapped
                ]

                base_faces = boundary_geometry.coplanar_difference(
                    holes_3d_snapped, tolerance=IESVE_TOLERANCE, angle_tolerance=0.01
                )
                if isinstance(base_faces, Face3D):
                    # change the base face to a list if the difference is a single face
                    base_faces = [base_faces]
                base_faces_holes = [[] for _ in base_faces]
                holes_tracker = []
                for hole_count, hole_geo in enumerate(holes_3d_snapped):
                    for count, base_face in enumerate(base_faces):
                        if not base_face.holes:
                            continue
                        for f_hole in base_face.holes:
                            f_hole_geo = Face3D(f_hole)
                            h_dist = hole_geo.center.distance_to_point(f_hole_geo.center)
                            if h_dist <= OPENING_OFFSET:
                                # this hole is inside the face
                                base_faces_holes[count].append(f_hole_geo)
                                holes_tracker.append(hole_count)
                                break
                    else:
                        if hole_count in holes_tracker:
                            continue
                        # the hole is not inside any of the faces
                        hole_face = Face(
                            str(uuid.uuid4()), geometry=hole_geo, type=AirBoundary()
                        )
                        faces.append(hole_face)

                # create holes
                holes_flattened = [h for holes in base_faces_holes for h in holes]
                for hole_geo in holes_flattened:
                    hole_face = Face(
                        str(uuid.uuid4()), geometry=hole_geo, type=AirBoundary()
                    )
                    # add a key to user data to skip the face when translating
                    # back from HBJSON to GEM
                    hole_face.user_data = {IMPORT_IGNORE: True}
                    faces.append(hole_face)

                # add base faces
                for base_face in base_faces:
                    face = Face(str(uuid.uuid4()), geometry=base_face)
                    faces.append(face)
                continue

        elif gem_type in (
                GEM_TYPES.ContextBuilding, GEM_TYPES.Shade, GEM_TYPES.Shade_2):
            is_detached = True if gem_type == GEM_TYPES.ContextBuilding else False
            face = _create_shade(boundary, holes, is_detached)
            _update_name(face, display_name)
        elif gem_type == GEM_TYPES.TranslucentShade:
            # ignore the hole. GEM has a strange way of building translucent shades
            face = _create_shade(
                boundary=boundary, is_detached=False,
                user_data={'__gem_type__': 'translucent_shade'}
            )
            _update_name(face, display_name)
        elif gem_type == GEM_TYPES.Topography:
            # Topography
            face = _create_shade(
                boundary=boundary, holes=holes, is_detached=True,
                user_data={'__gem_type__': 'topography'}
            )
            _update_name(face, display_name)

        faces.append(face)

    if gem_type == GEM_TYPES.Space or gem_type == GEM_TYPES.UnconditionedSpace:
        room = Room(identifier, faces=faces)
        _update_name(room, display_name)
        if gem_type == GEM_TYPES.UnconditionedSpace:
            room.exclude_floor_area = True
        return room
    else:
        return faces


def model_from_gem(gem_str, model_id='Unnamed', model_name=None):
    """Create a Honeybee Model from the string contents of an IESVE GEM file.

    Args:
        gem_str: Text string representation of the contents of a GEM file.
        model_id: Text string to be applied as the Model identifier. Typically,
            this is derived from the GEM file name. (Default: Unnamed).
        model_name: Optional text string to be applied as the Model identifier.
            If None, this will be the same as the model_id. (Default: None).

    Returns:
        A Honeybee Model derived from the GEM file contents.
    """
    # parse the Rooms, Shades and ShadeMeshes
    segments = gem_str.split('\nLAYER')[1:]
    parsed_objects = [_parse_gem_segment(segment) for segment in segments]
    rooms = []
    shades = []
    shade_meshes = []
    for r in parsed_objects:
        if isinstance(r, Room):
            rooms.append(r)
        elif isinstance(r, ShadeMesh):
            shade_meshes.append(r)
        else:
            shades.extend(r)

    # create the Model
    model = Model(
        clean_string(model_id), rooms=rooms, orphaned_shades=shades,
        shade_meshes=shade_meshes, units='Meters', tolerance=IESVE_TOLERANCE
    )
    if model_name is not None:
        model.display_name = model_name
    return model
