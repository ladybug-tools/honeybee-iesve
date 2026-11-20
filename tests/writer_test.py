"""Test the functions in the writer module that create GEM files from Honeybee Models."""
from honeybee.model import Model
from honeybee_iesve.writer import model_to_gem


def test_model():
    in_file = './tests/assets/revit_sample_model.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)


def test_room_shades():
    in_file = './tests/assets/lab_building.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    assert 'TYPE\n4' in gem_str


def test_air_boundary():
    in_file = './tests/assets/room_with_air_boundary.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    ab_str = '4 2\n' \
        '   0.000000    3.000000\n' \
        '   0.000000    0.000000\n' \
        '   11.000000    0.000000\n' \
        '   11.000000    3.000000\n'
    assert ab_str in gem_str


def test_display_name_clean_up():
    in_file = './tests/assets/multiline_name_test.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    ab_str = 'IES first line second line [FR000000]\n'
    assert ab_str in gem_str


def test_0_shade_thickness():
    in_file = './tests/assets/single_face_shade.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    ab_str = 'IES Shade 13c9e [Shade_13c9e001]\n' \
        '4 1\n' \
        '   -1.500000    -3.000000    2.500000\n' \
        '   2.500000    -3.000000    2.500000\n' \
        '   2.500000    0.000000    2.500000\n' \
        '   -1.500000    0.000000    2.500000\n' \
        '4 1 2 3 4\n' \
        '0'
    assert ab_str in gem_str


def test_shade_with_holes():
    in_file = './tests/assets/shade_with_holes.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)


def test_model_with_holes():
    in_file = './tests/assets/model_with_holes.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    room_str = 'IES Room w holes [RM000001]\n44 20'
    assert room_str in gem_str


def test_model_with_pv():
    in_file = './tests/assets/pv.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    pv_str = 'LAYER\n1\nCOLOUR\n0\nCATEGORY\n3\nTYPE\n202\nSUBTYPE\n0\n' \
        'COLOURRGB\n32767\n' \
        'PVP PV Panel [PV000000]\n' \
        '0.0315 -25.9269 8.54 4.0 1.0 225.0 120.0'
    assert pv_str in gem_str


def test_model_with_tree():
    in_file = './tests/assets/tree.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
    tree_str = 'LAN Tree [TR000001]\n' \
        '2D Tree 2\n' \
        '0.0315 -30.9269 -0.0 1.0 1.0 1.0 60.0 0.0'
    assert tree_str in gem_str


def test_model_with_topo():
    in_file = './tests/assets/topographical_shade.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)

    topo_str = 'IES Missing Space [MS000000]\n' \
        '8 6\n' \
        '   -0.721300    20.133500    -0.017700\n' \
        '   9.303000    18.016400    -0.017700\n' \
        '   3.972000    13.144500    -0.017700\n' \
        '   -3.425000    16.664500    -0.017700\n' \
        '   9.303000    18.016400    3.682300\n' \
        '   -0.721300    20.133500    3.682300\n' \
        '   -3.425000    16.664500    3.682300\n' \
        '   3.972000    13.144500    3.682300\n' \
        '4 1 2 3 4\n' \
        '0\n' \
        '4 5 6 7 8\n' \
        '0\n' \
        '4 8 7 4 3\n' \
        '0\n' \
        '4 5 8 3 2\n' \
        '0\n' \
        '4 6 5 2 1\n' \
        '0\n' \
        '4 7 6 1 4\n' \
        '0'

    assert topo_str in gem_str


def test_model_with_translucent_shade():
    in_file = './tests/assets/translucent_shade.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)

    topo_str = 'IES Ground Floor [GR000000]\n' \
        '4 1\n' \
        '   9.175500    -0.018900    8.540000\n' \
        '   0.031500    -0.018900    8.540000\n' \
        '   0.031500    3.007600    8.540000\n' \
        '   9.175500    3.007600    8.540000\n' \
        '4 1 2 3 4\n' \
        '1\n' \
        '4 0\n' \
        '   9.175500    -0.018900    8.540000\n' \
        '   0.031500    -0.018900    8.540000\n' \
        '   0.031500    3.007600    8.540000\n' \
        '   9.175500    3.007600    8.540000'

    assert topo_str in gem_str


def test_model_with_shade_mesh():
    in_file = './tests/assets/shade_mesh_example.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)

    assert 'IES Tree_1' in gem_str
    assert 'IES Tree_2' in gem_str
    assert 'IES Tree_3' in gem_str
    assert '182 200' in gem_str


def test_model_non_ascii():
    in_file = './tests/assets/room_non_ascii.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)

    assert 'IES اتاق خواب [' in gem_str


def test_room_with_plenum():
    in_file = './tests/assets/room_with_plenum.hbjson'
    model = Model.from_hbjson(in_file)
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)

    floor_plenum_str = 'SUBTYPE\n' \
        '2002\n' \
        'COLOURRGB\n' \
        '16711680\n' \
        'IES 131-Corridor Floor Plenum [13000000]'

    room_str = 'SUBTYPE\n' \
        '2001\n' \
        'COLOURRGB\n' \
        '16711680\n' \
        'IES 131-Corridor [13000001]'

    ceiling_plenum_str = 'SUBTYPE\n' \
        '2002\n' \
        'COLOURRGB\n' \
        '16711680\n' \
        'IES 131-Corridor Ceiling Plenum [13000002]'

    assert floor_plenum_str in gem_str
    assert room_str in gem_str
    assert ceiling_plenum_str in gem_str
