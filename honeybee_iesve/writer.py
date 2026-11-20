# coding=utf-8
"""Methods to write Honeybee core objects to GEM."""
from __future__ import division
import re
import math

from ladybug_geometry.geometry3d import Vector3D, Plane, Face3D, Polyface3D, Mesh3D
from ladybug.location import Location
from honeybee.facetype import AirBoundary
from honeybee.door import Door
from honeybee.shade import Shade
from honeybee.shademesh import ShadeMesh

from .config import IESVE_TOLERANCE, IMPORT_IGNORE
from .types import GEM_TYPES


def _gen_ve_id(display_name):
    """Generate the VE identifier based on the name of the room.

    VE takes the first two alphanumerical values except for vowels from the display name.
    Then it adds an integer. For instance "Room" will be translated to "RM000000".
    "1st floor" will be translated to "1S000000". If there is already another
    room with the same 2 characters then it adds to the number. RM000001, RM000002,
    and so on.

    This method only returns the first 2 characters.
    """
    # Match any vowel character (case-insensitive), any whitespace, or any \
    # non-alphanumeric character
    pattern = r"[aeiouAEIOU\s\W]+"
    # Replace matched characters with an empty string
    identifier = re.sub(pattern, '', display_name).upper()
    if len(identifier) < 2:
        print(
            'Unable to generate a valid GEM identifier from this name "{}". '
            'Room display names must retain at least two characters after removing '
            'vowels.'.format(display_name)
        )
        return 'ZZ'
    return identifier[:2]


def _convert_room_ids(model):
    """Convert room identifiers to a valid VE identifier.

    This method updates the model directly, and returns a dictionary that maps the
    original identifier to the new VE identifier. The mapper is useful to find the
    rooms by ID from inside IES VE python editor.
    """
    id_mapper = {}
    id_counter = {}
    for room in model.rooms:
        identifier = room.identifier
        ve_identifier = _gen_ve_id(room.display_name)
        if ve_identifier not in id_counter:
            id_counter[ve_identifier] = -1
        id_counter[ve_identifier] += 1
        full_ve_id = '{}{:06d}'.format(ve_identifier, id_counter[ve_identifier])
        full_ve_fallback_id = 'RM{:06d}'.format(id_counter[ve_identifier])
        try:
            room.identifier = full_ve_id
            id_mapper[identifier] = full_ve_id
        except AssertionError:
            room.identifier = full_ve_fallback_id
            id_mapper[identifier] = full_ve_fallback_id

    return id_mapper


def _opening_to_gem(parent_geo, opening_geos, opening_type=0):
    """Translate an opening to GEM format.

    Args:
        parent_geo: Geometry of the parent Face as a Face3D.
        opening_geos: A list of Face3D geometries for the openings (corresponding
            to Apertures and Doors).
        opening_type: An integer between 0-2. 0 is for Apertures, 1 is for Doors
            and 2 is for AirBoundary holes.

    Returns:
        A formatted string for the opening.
    """
    if parent_geo.max.z - parent_geo.min.z < IESVE_TOLERANCE:  # perfectly horizontal in IESVE
        clean_plane = Plane(n=Vector3D(0, 0, 1), o=parent_geo[0], x=Vector3D(1, 0, 0))
        parent_geo = Face3D(parent_geo.boundary, clean_plane, parent_geo.holes)
        origin, flip = parent_geo.upper_right_corner, True
    else:  # sloped roof or vertical wall
        origin, flip = parent_geo.lower_left_corner, False
    openings = []
    for opening in opening_geos:
        verts_2d = parent_geo.polygon_in_face(opening, origin, flip)
        openings.append('{} {}'.format(len(verts_2d), opening_type))
        # round to 6 decimal places for consistency with how IESVE exports GEM files
        openings.append(
            '\n'.join('   {:.6f}    {:.6f}'.format(v.x, v.y) for v in verts_2d)
        )
    return '\n'.join(openings)


def _vertices_to_gem(vertices):
    """Get a GEM string for a list of Point3D vertices.

    Vertices are rounded to 6 decimal places for consistency with how GEM files
    are exported from IESVE. However, the native absolute tolerance of IESVE
    is 0.1 mm, effectively meaning that the last two decimal places have no bearing
    on how the GEM file is interpreted by IESVE.
    """
    vertices = '\n'.join(
        '   {:.6f}    {:.6f}    {:.6f}'.format(v.x, v.y, v.z)
        for v in vertices
    )
    return vertices


def shade_to_gem(shade):
    """Translate a Honeybee Shade or ShadeMesh to GEM format.

    Args:
        shade: A Honeybee Shade or ShadeMesh object to be converted into a
            GEM string. This can also be a list of Shade objects in which case
            the geometries of the Shade will be joined together into a single
            shade group in the output GEM string.

    Returns:
        A formatted string for the input shade.
    """
    # process the inputs
    if isinstance(shade, (Shade, ShadeMesh)):
        geometry = shade.geometry
        name, identifier = shade.display_name, shade.identifier
        is_detached, user_data = shade.is_detached, shade.user_data
    else:  # assume that it is a list of Shade objects
        geometry = Polyface3D.from_faces(
            [s.geometry for s in shade], tolerance=IESVE_TOLERANCE
        )
        name, identifier = shade[0].display_name, shade[0].identifier
        is_detached, user_data = shade[0].is_detached, shade[0].user_data
    name = ' '.join(name.split())

    # process the user data into a GEM TYPE
    gem_type = GEM_TYPES.from_user_data(user_data)
    if not gem_type:  # it is a shade or a context building
        gem_type = GEM_TYPES.ContextBuilding if is_detached else GEM_TYPES.Shade
    elif not isinstance(geometry, Face3D) and gem_type in (GEM_TYPES.PV, GEM_TYPES.Tree):
        # Mesh3D and Polyface3D cannot be written to PV or Tree
        gem_type = GEM_TYPES.ContextBuilding if is_detached else GEM_TYPES.Shade

    # process the special cases of Face PV and Tree
    if gem_type == GEM_TYPES.PV:
        # calculate the bounds of the geometry based and translate it back to
        # GEM format
        w, h = geometry.boundary_polygon2d.max - geometry.boundary_polygon2d.min
        base = geometry.lower_right_corner
        yz_rotation = abs(90 - round(math.degrees(geometry.plane.altitude), 6))
        xy_rotation = abs(360 - round(math.degrees(geometry.plane.azimuth), 6))
        pv_info = '{x} {y} {z} {w} {h} {alt} {azimuth}'.format(
                x=round(base.x, 4), y=round(base.y, 4), z=round(base.z, 4),
                w=round(w, 4), h=round(h, 4),
                alt=round(xy_rotation, 4), azimuth=round(yz_rotation, 4)
            )
        return gem_type.to_gem(name=name, identifier=identifier, vertices=pv_info)
    elif gem_type == GEM_TYPES.Tree:
        # TODO: create objects for every IES object to remove duplicate values
        # like the scales here
        x_scale, y_scale, z_scale = 3, 3, 8
        tree_type = user_data.get('__gem_tree_type__', 1)
        w, h = geometry.boundary_polygon2d.max - geometry.boundary_polygon2d.min
        base = (geometry.lower_right_corner + geometry.lower_left_corner) / 2
        # this logic won't work for values larger than 180 but that's for later
        xy_rotation = abs(90 - round(math.degrees(geometry.plane.azimuth), 6))
        yz_rotation = round(math.degrees(geometry.plane.altitude), 6)
        tree_info = \
            '2D Tree {tree_type}\n' \
            '{x} {y} {z} {wx} {wy} {h} {alt} {azimuth}'.format(
                tree_type=tree_type,
                x=round(base.x, 4), y=round(base.y, 4), z=round(base.z, 4),
                wx=round(w / x_scale, 4), wy=round(w / y_scale, 4), h=round(h / z_scale, 4),
                alt=round(xy_rotation, 4), azimuth=round(yz_rotation, 4)
            )
        return gem_type.to_gem(name=name, identifier=identifier, vertices=tree_info)

    # process the geometry as a ContextBuilding or Shade
    faces = []
    if isinstance(geometry, Polyface3D):
        # Polyface3D
        unique_vertices = geometry.vertices
        vertices = _vertices_to_gem(unique_vertices)
        for face_i, face in zip(geometry.face_indices, geometry.faces):
            index = [str(v + 1) for v in face_i[0]]
            face_str = '%d %s\n' % (len(index), ' '.join(index))
            faces.append('%s%d' % (face_str, 0))
        face_count = len(geometry.faces)
    elif isinstance(geometry, Mesh3D):
        # Mesh3D
        unique_vertices = geometry.vertices
        vertices = _vertices_to_gem(unique_vertices)
        for face in geometry.faces:
            index = [str(v + 1) for v in face]
            face_str = '%d %s\n' % (len(index), ' '.join(index))
            faces.append('%s%d' % (face_str, 0))
        face_count = len(geometry.faces)
    else:
        # Face3D
        unique_vertices = geometry.lower_left_counter_clockwise_vertices
        vertices = _vertices_to_gem(unique_vertices)
        index = [str(v + 1) for v in range(len(unique_vertices))]
        face_str = '%d %s\n' % (len(index), ' '.join(index))
        faces.append('%s%d' % (face_str, 0))
        face_count = 1

    if len(unique_vertices) < 3:
        # a check for line-like mesh faces
        print('Invalid line-like shade object found and removed.')
        return ''

    return gem_type.to_gem(
        name=name, identifier=identifier,
        vertices_count=len(unique_vertices),
        vertices=vertices,
        faces='\n'.join(faces),
        face_count=face_count
    )


def shades_to_gem(shades):
    """Convert a list of Honeybee Shades and/or ShadeMesh to a GEM string.

    Args:
        shades: A list of Honeybee Shade or ShadeMesh objects. If input shades
            have a user_data key named __group_id__, they will be written into
            the GEM string as a single shade group rather than an individual
            shade face.

    Returns:
        A formatted string that represents the inputs shades in GEM format.
    """
    # organize the shades into groups
    shade_groups = {}
    no_groups = []
    for shade in shades:
        user_data = shade.user_data
        if user_data and IMPORT_IGNORE in user_data \
                and user_data[IMPORT_IGNORE]:
            continue  # ignore the shade with __ies_import__ key
        if isinstance(shade, ShadeMesh):
            no_groups.append(shade)
            continue  # always treat ShadeMesh as its own shade group
        try:
            group_id = shade.user_data['__group_id__']
        except (TypeError, KeyError):
            no_groups.append(shade)
            continue
        else:
            try:
                shade_groups[group_id].append(shade)
            except KeyError:  # first shade in the group
                shade_groups[group_id] = [shade]

    # create the GEM strings of the shades
    single_keys = [key for key, value in shade_groups.items() if len(value) == 1]
    for key in single_keys:
        v = shade_groups.pop(key)
        no_groups.append(v[0])
    single_shades = '\n'.join([shade_to_gem(shade) for shade in no_groups])
    group_shades = '\n'.join([shade_to_gem(shades) for shades in shade_groups.values()])
    return '\n'.join((single_shades, group_shades))


def room_to_ies(room):
    """Convert a Honeybee Room to a GEM string.

    Args:
        room: A Honeybee Room.

    Returns:
        A formatted string that represents the room in GEM format.
    """
    # remove new lines from the name
    room.display_name = ' '.join(room.display_name.split())

    unique_vertices = room.geometry.vertices
    vertices = _vertices_to_gem(unique_vertices)
    face_count = len(room.faces)
    faces = []
    air_boundary_count = 0
    for face_i, face in zip(room.geometry.face_indices, room.faces):
        # ensure that the face_i have the same order as the face vertices
        # they can be reversed if original Face3D used to make Polyface3D point inwards
        boundary = tuple(unique_vertices[i] for i in face_i[0])
        rebuilt_face = Face3D(boundary)
        if not face.geometry.plane.n.angle(rebuilt_face.plane.n) <= math.radians(1):
            # face indices are reversed from Face3D objects
            face_i = [list(reversed(pt_i)) for pt_i in face_i]

        # create the initial string of the Face from the Room vertices
        fg = face.geometry
        index = [str(v + 1) for v in face_i[0]]
        face_str = '%d %s\n' % (len(index), ' '.join(index))
        open_count, openings = 0, []

        # write the air boundary as an IESVE opening
        if isinstance(face.type, AirBoundary):
            # add the face itself as the hole
            sub_faces = [Face3D(fg.boundary, fg.plane)]
            openings.append(_opening_to_gem(fg, sub_faces, 2))
            open_count += 1

        # write the apertures and doors as openings
        window_geos, door_geos = [], []
        for sf in face.sub_faces:
            if isinstance(sf, Door) and not sf.is_glass:
                door_geos.append(sf.geometry)
            else:
                window_geos.append(sf.geometry)
            open_count += 1
        if len(window_geos) != 0:
            openings.append(_opening_to_gem(fg, window_geos, 0))
        if len(door_geos) != 0:
            openings.append(_opening_to_gem(fg, door_geos, 1))

        # create the final string for the face
        open_str = '\n' + '\n'.join(openings) if len(openings) != 0 else ''
        faces.append('%s%d%s' % (face_str, open_count, open_str))

    # create the final GEM string for the space
    is_void = room.exclude_floor_area
    if is_void:
        space = GEM_TYPES.UnconditionedSpace.to_gem(
            name=room.display_name, identifier=room.identifier,
            vertices_count=len(unique_vertices),
            face_count=face_count - air_boundary_count,
            vertices=vertices, faces='\n'.join(faces)
        )
    else:
        space = GEM_TYPES.Space.to_gem(
            name=room.display_name, identifier=room.identifier,
            vertices_count=len(unique_vertices),
            face_count=face_count - air_boundary_count,
            vertices=vertices, faces='\n'.join(faces)
        )
    return space


def model_to_gem(model, project_info=None, convert_room_ids=True):
    """Generate an IES GEM string representation of a Model.

    Args:
        model: A honeybee model.
        project_info: An optional ladybug ProjectInfo object that describes criteria
            about the project site. When specified, this will result in the location
            and north_angle into the GEM. (Default: None).
        convert_room_ids: A boolean to indicate wether the room IDs should be converted
            to IESVE format as part of the translation. Only change this option to False
            if you have already converted the rooms IDs before passing the model to
            this function.(Default: True)

    Returns:
        Text string representation of the contents of a GEM file derived from
        the input model.
    """
    # duplicate model to avoid mutating it as we edit it for GEM export
    original_model = model
    model = model.duplicate()
    # scale the model if the units are not meters
    if model.units != 'Meters':
        model.convert_to_units('Meters')
    # remove degenerate geometry within native IESVE tolerance of 0.0001 meters
    try:
        model.remove_degenerate_geometry(0.0001)
    except ValueError:
        error = 'Failed to remove degenerate Rooms.\nYour Model units system is: {}. ' \
            'Is this correct?'.format(original_model.units)
        raise ValueError(error)
    # split all room faces through their holes as they are not allowed in IES-VE
    model.split_rooms_through_holes()
    # ensure model has identifiers that are acceptable for GEM
    if convert_room_ids:
        _convert_room_ids(model)

    # create and return the GEM file string
    header = 'COM GEM data file exported by Pollination\nANT'
    if project_info is not None:
        default_location = Location(
            city='London Heathrow', country='United Kingdom',
            latitude=51.48, longitude=-0.45, time_zone=0, elevation=25
        )
        location = default_location if project_info.location is None \
            else project_info.location
        site = '\nSITE\n{lat:.3f}  {long:.3f} {tz:.3f} {north:.3f}'.format(
            lat=location.latitude, long=-location.longitude,
            tz=location.time_zone, north=project_info.north
        )
        header = header + site
    rooms_data = [room_to_ies(room) for room in model.rooms]
    context_shades = shades_to_gem(model.shades + list(model.shade_meshes))
    gem_data = [header] + rooms_data + [context_shades]
    return '\n'.join(gem_data)
